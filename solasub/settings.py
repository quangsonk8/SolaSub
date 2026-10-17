"""
Luu cau hinh nguoi dung giua cac lan mo tool.

Nam o %LOCALAPPDATA%\\SolaSub\\settings.json — khong de trong thu muc cai dat,
vi thu muc do co the khong co quyen ghi (Program Files).
"""
import io
import json
import os

APP_DIR = os.path.join(os.environ.get("LOCALAPPDATA")
                       or os.path.expanduser("~"), "SolaSub")
PATH = os.path.join(APP_DIR, "settings.json")

DEFAULTS = {
    "lang": "ja",                                   # ngon ngu dung lan cuoi
    "languages": ["ja", "vi", "en", "zh", "ko"],    # danh sach hien trong o chon
    "model": "base",                                # khong bay ra UI — sua tay neu can
    "last_audio_dir": "",
    "last_text_dir": "",
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        if os.path.exists(PATH):
            data = json.load(io.open(PATH, encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
    except Exception:
        pass                      # file hong -> dung mac dinh, khong lam chet app
    if not cfg.get("languages"):
        cfg["languages"] = list(DEFAULTS["languages"])
    return cfg


def save(cfg: dict) -> bool:
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        keep = {k: cfg.get(k, v) for k, v in DEFAULTS.items()}
        json.dump(keep, io.open(PATH, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False
