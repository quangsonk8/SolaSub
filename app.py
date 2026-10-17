"""
SolaSub — tao phu de tu audio + van ban goc.

    python app.py
    python app.py --audio story.mp3 --text story.txt --lang ja
"""
import sys


# ─────────────────────────────────────────────────────────────────────────────
# PHAI chay TRUOC moi import khac.
# Chay bang pythonw.exe (hoac ban dong goi PyInstaller --windowed) thi khong co
# console -> sys.stdout/stderr la None. tqdm trong stable-ts ghi thanh tien do ra
# stderr -> AttributeError: 'NoneType' object has no attribute 'write'.
# Thay bang bo ghi rong de thu vien nao cung chay duoc.
class _NullIO:
    def write(self, *a, **k): return 0
    def flush(self): pass
    def isatty(self): return False
    def readable(self): return False
    def writable(self): return True
    def seekable(self): return False
    def close(self): pass
    @property
    def encoding(self): return "utf-8"
    def fileno(self): raise OSError("khong co console")


if sys.stdout is None:
    sys.stdout = _NullIO()
if sys.stderr is None:
    sys.stderr = _NullIO()
# ─────────────────────────────────────────────────────────────────────────────

import argparse          # noqa: E402
import io                # noqa: E402
import os                # noqa: E402

from solasub.paths import (ensure_ffmpeg_on_path,          # noqa: E402
                           hide_subprocess_windows)

# whisper goi thang "ffmpeg" tu PATH; may nguoi dung thuong khong co nen phai
# tro vao ban di kem TRUOC khi bat ky thu vien nao chay.
ensure_ffmpeg_on_path()
hide_subprocess_windows()

from PyQt6.QtCore import QUrl          # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from solasub.ui.main_window import MainWindow  # noqa: E402


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--audio")
    ap.add_argument("--text")
    ap.add_argument("--lang")
    args = ap.parse_args()

    # Khong co dong nay thi Windows gop cua so vao nhom "pythonw.exe" va lay
    # icon con ran cua Python tren thanh tac vu.
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "SOLATECH.SolaSub")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("SolaSub")
    from solasub.ui.icon import app_icon
    _ic = app_icon()
    if _ic:
        app.setWindowIcon(_ic)
    w = MainWindow()

    # Mo san file neu duoc truyen vao — tien khi thu nghiem
    if args.audio and os.path.exists(args.audio):
        w.audio_path = args.audio
        w.btn_audio.setText(os.path.basename(args.audio))
        w.player.setSource(QUrl.fromLocalFile(os.path.abspath(args.audio)))
    if args.text and os.path.exists(args.text):
        w.raw_text = io.open(args.text, encoding="utf-8-sig").read()
        w.text_path = args.text
        w.btn_text.setText(os.path.basename(args.text))
        w.text_view.setPlainText(w.raw_text)
    if args.lang:
        i = w.cb_lang.findData(args.lang)      # tim theo MA, khong theo nhan hien thi
        if i >= 0:
            w.cb_lang.setCurrentIndex(i)
    w._update_ready()

    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
