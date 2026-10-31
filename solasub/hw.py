"""
Phan cung: gioi han CPU + tinh trang GPU. File nay KHONG nap torch — giao dien goi duoc ngay, va
giao dien khong nap torch thi khong giu RAM / khong khoa DLL khi cai goi GPU.
"""
import ctypes
import importlib.metadata
import os
import shutil
from dataclasses import dataclass

# Trang thai GPU
READY = "ready"            # co goi CUDA + driver NVIDIA -> du kien chay GPU
NEED_PACK = "need_pack"    # may co NVIDIA nhung dang la torch ban CPU -> cai them goi GPU
NO_NVIDIA = "no_nvidia"    # khong co driver NVIDIA (AMD/Intel/khong card) -> chi chay CPU
BROKEN = "broken"          # co goi CUDA nhung torch khong dung duoc card (driver cu / card qua cu)
FORCED_CPU = "forced_cpu"  # nguoi dung dat "device": "cpu" trong settings.json


@dataclass(frozen=True)
class GpuStatus:
    state: str
    label: str      # chu ngan o thanh trang thai
    detail: str     # giai thich day du (tooltip)


_TEXT = {
    READY: ("GPU sẵn sàng", "Có gói tăng tốc CUDA và driver NVIDIA — SolaSub sẽ chạy bằng GPU."),
    NEED_PACK: ("Đang dùng CPU — bấm để cài gói GPU",
                "Máy có card NVIDIA nhưng chưa có gói tăng tốc CUDA nên đang chạy bằng CPU (chậm hơn ~10 lần). "
                "Bấm để tải gói GPU (~2,4 GB)."),
    NO_NVIDIA: ("Đang dùng CPU",
                "Không tìm thấy driver NVIDIA. Tăng tốc GPU chỉ hỗ trợ card NVIDIA; card AMD / Intel chạy bằng CPU."),
    BROKEN: ("Đang dùng CPU — GPU không chạy được",
             "Đã có gói CUDA nhưng không dùng được card NVIDIA: hãy cập nhật driver NVIDIA "
             "(card quá cũ thì không hỗ trợ CUDA 12.6)."),
    FORCED_CPU: ("Đang dùng CPU (theo cài đặt)", "settings.json đặt \"device\": \"cpu\"."),
}


def status_of(state: str) -> GpuStatus:
    return GpuStatus(state, *_TEXT[state])


def physical_cores() -> int:
    """So nhan THAT (khong tinh hyper-threading). Hoi Windows truc tiep: phai biet TRUOC khi nap numpy/torch."""
    try:
        k32 = ctypes.WinDLL("kernel32")
        size = ctypes.c_ulong(0)
        k32.GetLogicalProcessorInformationEx(0, None, ctypes.byref(size))  # 0 = RelationProcessorCore
        buf = ctypes.create_string_buffer(size.value)
        if k32.GetLogicalProcessorInformationEx(0, buf, ctypes.byref(size)):
            raw, i, cores = buf.raw, 0, 0
            while i < size.value:                                          # ban ghi dai ngan khac nhau, Size o byte 4
                i += int.from_bytes(raw[i + 4:i + 8], "little")
                cores += 1
            if cores:
                return cores
    except (OSError, AttributeError):
        pass
    return max(1, (os.cpu_count() or 2) // 2)


def cpu_limit(cores: int, configured: int = 0) -> int:
    """
    So luong CPU cho Whisper. Mac dinh chi dung MOT NUA so nhan that: may yeu chay het nhan hang chuc phut voi file
    dai se qua nhiet / khoi dong lai. configured > 0 (settings.json "cpu_threads") -> theo cau hinh, khong vuot so nhan.
    """
    cores = max(1, cores)
    if configured > 0:
        return min(configured, cores)
    return max(1, (cores + 1) // 2)


# Moi thu vien co be luong RIENG, tu mo theo so nhan may. torch.set_num_threads CHI gioi han torch: do that 1.1.4 voi
# file 43 phut tien trinh len 100 luong, ca may 100% (dat cac bien nay: cao nhat 55%, thoi gian khong doi).
_POOL_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
              "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS")


def thread_env(n: int) -> dict:
    """Bien moi truong gioi han moi be luong. PHAI dat TRUOC khi import numpy/torch — sau do thu vien bo qua."""
    env = {k: str(n) for k in _POOL_VARS}
    env["KMP_BLOCKTIME"] = "0"      # luong OpenMP ranh thi ngu ngay, khong quay vong ton CPU
    return env


def torch_build() -> str:
    """Ban torch dang cai, vd '2.14.1+cu126'. Doc metadata, khong import torch. Khong co -> ''."""
    try:
        return importlib.metadata.version("torch")
    except importlib.metadata.PackageNotFoundError:
        return ""


def has_nvidia() -> bool:
    """Driver NVIDIA cai vao la co nvidia-smi.exe trong System32."""
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    return os.path.exists(os.path.join(root, "System32", "nvidia-smi.exe")) or bool(shutil.which("nvidia-smi"))


def classify(build: str, nvidia: bool, cuda_available=None, requested: str = "auto") -> str:
    """
    Tinh trang GPU. cuda_available: ket qua that tu torch.cuda.is_available() (tien trinh xu ly bao ve);
    None = chua chay lan nao, chi doan tu ban cai dat.
    """
    if requested == "cpu":
        return FORCED_CPU
    has_pack = "+cu" in build
    if cuda_available is True:
        return READY
    if not nvidia:
        return NO_NVIDIA
    if not has_pack:
        return NEED_PACK
    return BROKEN if cuda_available is False else READY


def current_status(requested: str = "auto", cuda_available=None) -> GpuStatus:
    return status_of(classify(torch_build(), has_nvidia(), cuda_available, requested))
