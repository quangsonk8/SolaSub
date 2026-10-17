"""
Tim tai nguyen di kem (assets, tools) — chay tu source lan tu ban dong goi.

Ban dong goi co dang:
    SolaSub\
        app.py
        python\pythonw.exe
        assets\solasub.ico
        tools\ffmpeg.exe
        solasub\...
nen thu muc goc phai do ra tu nhieu moc khac nhau: argv[0] (app.py), vi tri
goi nay, va thu muc chua python.exe (len 1 cap vi python nam trong python\).
"""
import os
import shutil
import sys


def app_roots():
    """Cac thu muc co the la goc cua ban cai, xep theo do tin cay."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe = os.path.dirname(os.path.abspath(sys.executable))
    roots = [
        os.path.dirname(os.path.abspath(sys.argv[0])),
        here,
        os.path.join(exe, ".."),
        exe,
    ]
    out, seen = [], set()
    for r in roots:
        r = os.path.normpath(r)
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out


def resource(*parts):
    """Tim mot file di kem, vd resource('assets', 'solasub.ico')."""
    for r in app_roots():
        p = os.path.normpath(os.path.join(r, *parts))
        if os.path.exists(p):
            return p
    return None


def ffmpeg_exe():
    """Ban di kem trong tools\\ truoc, khong co thi lay trong PATH."""
    return resource("tools", "ffmpeg.exe") or shutil.which("ffmpeg") or "ffmpeg"


def ensure_ffmpeg_on_path():
    """
    whisper va stable-ts goi thang chuoi "ffmpeg" qua subprocess, tuc la bat
    buoc phai co trong PATH. Nguoi dung thuong khong cai ffmpeg, nen them thu
    muc chua ban di kem vao dau PATH cua tien trinh nay.
    """
    exe = ffmpeg_exe()
    if not os.path.isabs(exe) or not os.path.exists(exe):
        return False
    d = os.path.dirname(exe)
    cur = os.environ.get("PATH", "")
    if d.lower() not in [x.strip().lower() for x in cur.split(os.pathsep)]:
        os.environ["PATH"] = d + os.pathsep + cur
    return True


def hide_subprocess_windows():
    """
    Chay bang pythonw thi moi lan whisper goi ffmpeg se nhay mot cua so den.
    whisper/stable-ts goi subprocess.run khong kem creationflags nen khong
    chinh tu ngoai duoc — vay nen boc lai ham mac dinh.
    """
    if os.name != "nt":
        return
    import subprocess
    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if not flag or getattr(subprocess, "_solasub_quiet", False):
        return
    orig = subprocess.Popen.__init__

    def patched(self, *a, **kw):
        kw["creationflags"] = kw.get("creationflags", 0) | flag
        return orig(self, *a, **kw)

    subprocess.Popen.__init__ = patched
    subprocess._solasub_quiet = True
