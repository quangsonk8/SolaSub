"""
Tien trinh rieng chay Whisper:  python -m solasub.engine

Vi sao tach khoi giao dien:
- Chay xong tien trinh thoat -> Windows thu hoi TOAN BO RAM + VRAM. Giu model trong app giu ~1-2 GB RAM + ~600 MB VRAM
  toi khi dong app; del model + empty_cache chi tra duoc VRAM, RAM gan nhu khong giam (da do).
- Nut Dung kill duoc ngay: stable-ts khong co hook huy, trong cung tien trinh thi khong dung duoc.
- Whisper hong ca tien trinh (het RAM, loi driver) thi giao dien van song va bao loi duoc.
- Tien trinh chay o uu tien thap (worker dat luc tao) de may van dung duoc.

Giao thuc (ASCII JSON, moi dong 1 thong diep):
    stdin : 1 dong job {audio, text, lang, model, device, cpu_threads, parent_pid}.
    stdout: {"type": "progress", "msg"} | {"type": "device", ...} | {"type": "done", cues, stats, duration}
            | {"type": "failed", "msg"}
"""
import ctypes
import json
import os
import sys
import threading

from .hw import cpu_limit, physical_cores, thread_env
from .paths import ensure_ffmpeg_on_path, hide_subprocess_windows


def _watch_parent(pid: int):
    """
    App chet / bi kill -> thoat ngay, khong de Whisper mo coi an CPU. Cho tren handle tien trinh, KHONG doc stdin:
    tren Windows, 1 luong dang ReadFile tren stdin lam LoadLibrary o luong khac treo vinh vien (khoi tao CRT cua DLL
    goi GetFileType(stdin)) — da gap: import numpy dung im.
    """
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    handle = k32.OpenProcess(0x00100000, False, pid)    # SYNCHRONIZE
    if handle:
        k32.WaitForSingleObject(handle, 0xFFFFFFFF)     # INFINITE
    os._exit(3)


def limit_cpu(torch, n: int) -> None:
    torch.set_num_threads(n)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:            # chi dat duoc truoc khi torch chay phep tinh song song dau tien
        pass


def pick_device(torch, requested: str = "auto"):
    if requested == "cpu":
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def is_gpu_error(e: Exception) -> bool:
    """Loi cua GPU (het VRAM, loi driver CUDA luc chay) -> chuyen CPU duoc; loi khac thi bao len nhu thuong."""
    s = f"{type(e).__name__} {e}".lower()
    return "outofmemory" in s or "out of memory" in s or "cuda" in s or "cudnn" in s or "cublas" in s


def run_job(job: dict, emit) -> None:
    from .align import align_words, build_cues, load_model, transcribe_words
    from .problems import detect
    from .srt import audio_duration
    from .subtitle import normalize

    text = normalize(job["text"])
    audio, lang = job["audio"], job["lang"]
    # Khong co van ban goc -> chuyen sang che do PHIEN AM (chu do Whisper nghe ra)
    transcribe_mode = not text

    emit(type="progress", msg="Đang đo thời lượng audio…")
    dur = audio_duration(audio)
    if dur <= 0:
        emit(type="failed", msg="Không đọc được audio (ffmpeg lỗi?).")
        return

    emit(type="progress", msg=f"Đang nạp model {job['model']}…")
    import torch
    threads = int(job["threads"])
    limit_cpu(torch, threads)
    requested = job.get("device") or "auto"
    device = pick_device(torch, requested)
    cuda_ok = bool(torch.cuda.is_available())
    gpu_name = torch.cuda.get_device_name(0) if device == "cuda" else ""
    emit(type="device", device=device, cuda_available=cuda_ok, gpu=gpu_name, threads=threads)
    where = gpu_name or "GPU" if device == "cuda" else f"CPU {threads} luồng"

    def work(model, where):
        if transcribe_mode:
            emit(type="progress", msg=f"Đang phiên âm ({dur/60:.0f} phút audio, {where})… chậm hơn căn chỉnh nhiều")
            stream, heard = transcribe_words(model, audio, lang)
            if not heard.strip():
                return None, ""
            return stream, normalize(heard)
        emit(type="progress", msg=f"Đang căn chỉnh ({dur/60:.0f} phút audio, {where})…")
        status = lambda m: emit(type="progress", msg=m)
        return align_words(model, audio, text, lang, status=status), text

    try:
        model, _ = load_model(job["model"], device)
        stream, final_text = work(model, where)
    except Exception as e:      # noqa: BLE001 — chi nuot loi GPU, con lai raise
        # GPU qua it VRAM (dang choi game, card 2 GB...) / driver loi -> chay CPU thay vi bao loi
        if device != "cuda" or not is_gpu_error(e):
            raise
        emit(type="progress", msg="GPU không dùng được — chuyển sang CPU…")
        emit(type="device", device="cpu", cuda_available=True, gpu="", threads=threads, fallback=True)
        model = None
        torch.cuda.empty_cache()
        model, _ = load_model(job["model"], "cpu")
        stream, final_text = work(model, f"CPU {threads} luồng")

    if stream is None:
        emit(type="failed", msg="Không nghe được chữ nào từ audio.")
        return

    emit(type="progress", msg="Đang chia cue và áp luật phụ đề…")
    cues = build_cues(stream, final_text, dur)
    for c in cues:
        c["transcribed"] = transcribe_mode
    stats = detect(cues, dur)
    stats["_che_do"] = "phiên âm" if transcribe_mode else "căn chỉnh"
    stats["_thieu"] = stream.missing_regions()      # doan kich ban khong co trong audio (UI bao rieng)
    emit(type="done", cues=cues, stats=stats, duration=dur)


def main():
    out = sys.stdout
    sys.stdout = sys.stderr         # thu vien print() khong duoc lan vao kenh giao thuc

    def emit(**msg):
        out.write(json.dumps(msg, default=float) + "\n")
        out.flush()

    try:
        job = json.loads(sys.stdin.buffer.readline())
        # TRUOC moi import numpy/torch (xem hw.thread_env)
        job["threads"] = cpu_limit(physical_cores(), int(job.get("cpu_threads") or 0))
        os.environ.update(thread_env(job["threads"]))
        threading.Thread(target=_watch_parent, args=(int(job["parent_pid"]),), daemon=True).start()
        ensure_ffmpeg_on_path()
        hide_subprocess_windows()
        run_job(job, emit)
    except Exception as e:          # noqa: BLE001 — bao loi len UI
        import traceback
        emit(type="failed", msg=f"{type(e).__name__}: {e}\n\n{traceback.format_exc()[-800:]}")
    # Thoat NGAY: khong cho doc lai torch/CUDA, tra RAM + VRAM cho may
    out.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
