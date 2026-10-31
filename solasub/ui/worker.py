"""
Dieu khien tien trinh Whisper (solasub/engine.py) tu mot luong rieng — khong dong bang giao dien.
Bản thân giao dien KHONG nap torch/model: xong viec tien trinh thoat la tra het RAM + VRAM cho may.
"""
import json
import os
import subprocess
import sys

from PyQt6.QtCore import QThread, pyqtSignal

from ..settings import APP_DIR

# Uu tien thap: Windows nhuong CPU cho app nguoi dung dang mo. ffmpeg do tien trinh nay goi cung thua huong.
BELOW_NORMAL = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ENGINE_LOG = os.path.join(APP_DIR, "engine.log")


def explain_exit(code, log_tail: str) -> str:
    """Tien trinh chet ma khong bao ket qua: het RAM / loi driver GPU / crash trong thu vien C++."""
    msg = (f"Tiến trình xử lý bị dừng đột ngột (mã {code}).\n\n"
           "Thường do thiếu RAM hoặc lỗi driver GPU. Hãy đóng bớt ứng dụng rồi chạy lại.")
    return msg + (f"\n\n{log_tail[-500:]}" if log_tail.strip() else "")


class AlignWorker(QThread):
    progress = pyqtSignal(str)            # thong bao tien do
    device = pyqtSignal(dict)             # thiet bi that dang dung: device, cuda_available, gpu, threads
    done = pyqtSignal(list, dict, float)  # cues, stats, duration
    failed = pyqtSignal(str)
    stopped = pyqtSignal()                # nguoi dung bam Dung

    def __init__(self, audio, text, lang="ja", model="base", device="auto", cpu_threads=0):
        super().__init__()
        self.job = {"audio": audio, "text": text, "lang": lang, "model": model,
                    "device": device, "cpu_threads": cpu_threads, "parent_pid": os.getpid()}
        self._proc = None
        self._cancelled = False

    def cancel(self):
        """Dung ngay: kill ca cay tien trinh (Whisper + ffmpeg no goi). Goi tu luong giao dien."""
        self._cancelled = True
        p = self._proc
        if p is None or p.poll() is not None:
            return
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True,
                           timeout=10, creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            pass
        if p.poll() is None:
            p.kill()

    def _command(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return [sys.executable, "-m", "solasub.engine"], root

    def run(self):
        finished = False
        log_tail = ""
        try:
            os.makedirs(APP_DIR, exist_ok=True)
            cmd, root = self._command()
            with open(ENGINE_LOG, "wb") as log:
                self._proc = subprocess.Popen(cmd, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                              stderr=log, creationflags=BELOW_NORMAL | NO_WINDOW)
            if self._cancelled:             # bam Dung dung luc dang tao tien trinh
                self.cancel()
            self._proc.stdin.write((json.dumps(self.job) + "\n").encode("ascii"))
            self._proc.stdin.close()

            for line in self._proc.stdout:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                kind = m.get("type")
                if kind == "progress":
                    self.progress.emit(m["msg"])
                elif kind == "device":
                    self.device.emit(m)
                elif kind == "done":
                    finished = True
                    self.done.emit(m["cues"], m["stats"], float(m["duration"]))
                elif kind == "failed":
                    finished = True
                    self.failed.emit(m["msg"])
            code = self._proc.wait()
            if self._cancelled:
                self.stopped.emit()
            elif not finished:
                try:
                    with open(ENGINE_LOG, encoding="utf-8", errors="replace") as f:
                        log_tail = f.read()[-2000:]
                except OSError:
                    pass
                self.failed.emit(explain_exit(code, log_tail))
        except (OSError, ValueError) as e:  # pipe da dong vi bi kill -> coi nhu Dung
            if self._cancelled:
                self.stopped.emit()
            else:
                self.failed.emit(f"Không chạy được tiến trình xử lý: {type(e).__name__}: {e}")
        finally:
            p = self._proc
            if p is not None:
                try:
                    p.stdout.close()
                except OSError:
                    pass
