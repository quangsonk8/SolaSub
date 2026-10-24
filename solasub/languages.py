"""
Danh sach ngon ngu cho o chon ngon ngu — bang tinh san (LANGUAGES ben duoi), KHONG nap whisper/torch.
"""

# Chep tu whisper.tokenizer.LANGUAGES (openai-whisper 20250625, 100 ngon ngu).
# KHONG import whisper luc mo app: goi whisper keo theo ca PyTorch (~3 giay, lan dau sau khi bat may con
# lau hon nhieu) chi de lay danh sach nay. Nang cap whisper thi chay lai build/gen_languages.py.
LANGUAGES = {
    "en": "english", "zh": "chinese", "de": "german", "es": "spanish", "ru": "russian",
    "ko": "korean", "fr": "french", "ja": "japanese", "pt": "portuguese", "tr": "turkish",
    "pl": "polish", "ca": "catalan", "nl": "dutch", "ar": "arabic", "sv": "swedish",
    "it": "italian", "id": "indonesian", "hi": "hindi", "fi": "finnish", "vi": "vietnamese",
    "he": "hebrew", "uk": "ukrainian", "el": "greek", "ms": "malay", "cs": "czech",
    "ro": "romanian", "da": "danish", "hu": "hungarian", "ta": "tamil", "no": "norwegian",
    "th": "thai", "ur": "urdu", "hr": "croatian", "bg": "bulgarian", "lt": "lithuanian",
    "la": "latin", "mi": "maori", "ml": "malayalam", "cy": "welsh", "sk": "slovak",
    "te": "telugu", "fa": "persian", "lv": "latvian", "bn": "bengali", "sr": "serbian",
    "az": "azerbaijani", "sl": "slovenian", "kn": "kannada", "et": "estonian", "mk": "macedonian",
    "br": "breton", "eu": "basque", "is": "icelandic", "hy": "armenian", "ne": "nepali",
    "mn": "mongolian", "bs": "bosnian", "kk": "kazakh", "sq": "albanian", "sw": "swahili",
    "gl": "galician", "mr": "marathi", "pa": "punjabi", "si": "sinhala", "km": "khmer",
    "sn": "shona", "yo": "yoruba", "so": "somali", "af": "afrikaans", "oc": "occitan",
    "ka": "georgian", "be": "belarusian", "tg": "tajik", "sd": "sindhi", "gu": "gujarati",
    "am": "amharic", "yi": "yiddish", "lo": "lao", "uz": "uzbek", "fo": "faroese",
    "ht": "haitian creole", "ps": "pashto", "tk": "turkmen", "nn": "nynorsk", "mt": "maltese",
    "sa": "sanskrit", "lb": "luxembourgish", "my": "myanmar", "bo": "tibetan", "tl": "tagalog",
    "mg": "malagasy", "as": "assamese", "tt": "tatar", "haw": "hawaiian", "ln": "lingala",
    "ha": "hausa", "ba": "bashkir", "jw": "javanese", "su": "sundanese", "yue": "cantonese",
}

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
