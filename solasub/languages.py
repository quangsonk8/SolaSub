"""
Danh sach ngon ngu — lay THANG tu whisper.tokenizer thay vi go tay,
nen nang cap thu vien la tu co them ngon ngu moi, khong phai sua code.
"""

# Nhung thu tieng hay dung nhat — ghim len dau danh sach.
PINNED = ["ja", "vi", "en", "zh", "ko"]

# Ten tieng Viet cho cac ngon ngu pho bien; cai nao khong co thi dung ten tieng Anh.
VI_NAMES = {
    "ja": "Nhật", "vi": "Việt", "en": "Anh", "zh": "Trung", "ko": "Hàn",
    "th": "Thái", "id": "Indonesia", "fr": "Pháp", "de": "Đức", "es": "Tây Ban Nha",
    "ru": "Nga", "pt": "Bồ Đào Nha", "it": "Ý", "ar": "Ả Rập", "hi": "Hindi",
    "km": "Khmer", "lo": "Lào", "my": "Miến Điện", "ms": "Mã Lai", "tl": "Tagalog",
    "nl": "Hà Lan", "pl": "Ba Lan", "tr": "Thổ Nhĩ Kỳ", "uk": "Ukraina",
}


def all_languages():
    """[(ma, nhan hien thi)] — ghim truoc, phan con lai xep theo ten."""
    try:
        from whisper.tokenizer import LANGUAGES
    except Exception:
        LANGUAGES = {c: c for c in PINNED}

    def label(code):
        en = LANGUAGES.get(code, code).title()
        vi = VI_NAMES.get(code)
        return f"{code} — {vi} ({en})" if vi else f"{code} — {en}"

    pinned = [(c, label(c)) for c in PINNED if c in LANGUAGES]
    rest = sorted(((c, label(c)) for c in LANGUAGES if c not in PINNED),
                  key=lambda x: x[1].split("—")[1].strip().lower())
    return pinned, rest


def code_from_label(text: str) -> str:
    """'ja — Nhật (Japanese)' -> 'ja'. Nhan duoc ca khi nguoi dung chi go 'ja'."""
    text = (text or "").strip()
    return text.split("—")[0].strip() if "—" in text else text
