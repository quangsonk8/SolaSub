"""
Bao trang thai khoi dong cho man hinh khoi dong cua SolaSub.exe (build/launcher.cs).

Launcher chay app.py voi bien moi truong SOLASUB_SPLASH=1 va doc stdout:
    @@STATUS <chu>   -> doi dong trang thai tren man hinh khoi dong
    @@READY          -> cua so chinh da hien -> launcher mo dan man hinh khoi dong roi thoat

Chay thang `python app.py` (khong qua launcher) thi khong in gi.
File nay CHI dung thu vien chuan, import gan nhu tuc thi — phai bao duoc trang thai truoc khi nap Qt.
"""
import os
import sys

_ON = os.environ.get("SOLASUB_SPLASH") == "1"


def status(text: str) -> None:
    if not _ON:
        return
    try:
        sys.stdout.write("@@STATUS " + text + "\n")
        sys.stdout.flush()
    except Exception:
        pass


def ready() -> None:
    """
    Bao launcher la xong, roi CHUYEN stdout/stderr sang NUL.
    Launcher thoat ngay sau @@READY -> pipe bi dong; neu khong chuyen thi lan sau thu vien nao ghi ra
    stdout/stderr (tqdm cua stable-ts ghi tien do ra stderr luc can chinh) se loi "broken pipe".
    Chuyen ca muc file descriptor (dup2) de tien trinh con (ffmpeg) cung khong ghi vao pipe cu.
    """
    global _ON
    if not _ON:
        return
    _ON = False
    try:
        sys.stdout.write("@@READY\n")
        sys.stdout.flush()
    except Exception:
        pass
    try:
        null_fd = os.open(os.devnull, os.O_WRONLY)
        for fd in (1, 2):
            try:
                os.dup2(null_fd, fd)
            except OSError:
                pass
        os.close(null_fd)
    except OSError:
        pass
    try:
        sink = open(os.devnull, "w", encoding="utf-8")
        sys.stdout = sink
        sys.stderr = sink
    except Exception:
        pass
