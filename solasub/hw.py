"""
Phan cung: gioi han CPU + tinh trang GPU. File nay KHONG nap torch — giao dien goi duoc ngay, va
giao dien khong nap torch thi khong giu RAM / khong khoa DLL khi cai goi GPU.
"""
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


def cpu_limit(default_threads: int, configured: int = 0) -> int:
    """
    So luong CPU cho Whisper. default_threads = so torch tu chon (so nhan that cua may). Mac dinh chi dung MOT NUA:
    may yeu chay het nhan hang chuc phut voi file dai se qua nhiet / khoi dong lai. configured > 0 (settings.json
    "cpu_threads") -> theo cau hinh, khong vuot qua default_threads.
    """
    default_threads = max(1, default_threads)
    if configured > 0:
        return min(configured, default_threads)
    return max(1, (default_threads + 1) // 2)


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
