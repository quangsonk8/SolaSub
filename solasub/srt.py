"""Doc/ghi SRT + do thoi luong audio bang ffmpeg."""
import io
import re
import subprocess

from .paths import ffmpeg_exe

_DUR = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d+)")
# Dung CREATE_NO_WINDOW de chay bang pythonw khong nhay cua so den
_NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def audio_duration(path: str, ffmpeg: str = None) -> float:
    out = subprocess.run([ffmpeg or ffmpeg_exe(), "-hide_banner", "-nostats",
                          "-i", path, "-f", "null", "-"],
                         capture_output=True, text=True, errors="ignore",
                         creationflags=_NO_WIN).stderr
    m = _DUR.search(out)
    if not m:
        return 0.0
    return (int(m.group(1)) * 3600 + int(m.group(2)) * 60
            + int(m.group(3)) + float("0." + m.group(4)))


def ts(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600); m = int(sec % 3600 // 60)
    s = int(sec % 60); ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000:
        ms = 0; s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(cues, path: str, wrap=True):
    from .subtitle import wrap_lines
    buf = []
    n = 1
    for c in cues:
        text = c["text"].strip()
        if not text:
            continue
        buf.append(str(n))
        buf.append(f"{ts(c['start'])} --> {ts(c['end'])}")
        buf.append(wrap_lines(text) if wrap else text)
        buf.append("")
        n += 1
    io.open(path, "w", encoding="utf-8").write("\n".join(buf) + "\n")
    return n - 1


def read_srt(path: str):
    cues = []
    raw = io.open(path, encoding="utf-8-sig").read().strip()
    for blk in raw.split("\n\n"):
        lines = [x for x in blk.strip().split("\n") if x.strip()]
        tm = [x for x in lines if "-->" in x]
        if not tm:
            continue
        a, b = tm[0].split("-->")
        body = lines[lines.index(tm[0]) + 1:]
        cues.append({"start": _sec(a), "end": _sec(b), "text": "\n".join(body)})
    return cues


def parse_ts(s: str):
    """Doc nguoc '00:01:23,450' -> giay. Tra None neu sai dinh dang."""
    s = (s or "").strip().replace(".", ",")
    m = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:,(\d{1,3}))?", s)
    if not m:
        return None
    h = int(m.group(1) or 0)
    mn, sec = int(m.group(2)), int(m.group(3))
    ms = int((m.group(4) or "0").ljust(3, "0"))
    return h * 3600 + mn * 60 + sec + ms / 1000


def _sec(t: str) -> float:
    t = t.strip().replace(".", ",")
    h, m, rest = t.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
