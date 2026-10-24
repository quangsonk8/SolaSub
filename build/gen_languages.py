"""
Sinh lai bang LANGUAGES trong solasub/languages.py tu whisper.tokenizer.LANGUAGES.

App KHONG import whisper luc mo (whisper keo theo PyTorch, lam cham khoi dong vai giay) nen bang ngon ngu
duoc chep san vao code. Nang cap openai-whisper thi chay lai:

    venv-cpu\\Scripts\\python.exe build\\gen_languages.py
"""
import io
import os
import re

import whisper
import whisper.tokenizer as tok

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "solasub", "languages.py")

items = list(tok.LANGUAGES.items())
rows = [items[i:i + 5] for i in range(0, len(items), 5)]
body = "\n".join("    " + ", ".join(f'"{c}": "{n}"' for c, n in r) + "," for r in rows)
block = (
    f"# Chep tu whisper.tokenizer.LANGUAGES (openai-whisper {whisper.__version__}, {len(items)} ngon ngu).\n"
    "# KHONG import whisper luc mo app: goi whisper keo theo ca PyTorch (~3 giay, lan dau sau khi bat may con\n"
    "# lau hon nhieu) chi de lay danh sach nay. Nang cap whisper thi chay lai build/gen_languages.py.\n"
    "LANGUAGES = {\n" + body + "\n}\n"
)

src = io.open(PATH, encoding="utf-8").read()
new, n = re.subn(r"# Chep tu whisper\.tokenizer\.LANGUAGES.*?\nLANGUAGES = \{.*?\n\}\n", lambda _: block, src, flags=re.S)
if n != 1:
    raise SystemExit("Khong tim thay khoi LANGUAGES trong languages.py")
io.open(PATH, "w", encoding="utf-8", newline="\n").write(new)

ns = {}
exec(compile(new, PATH, "exec"), ns)
assert ns["LANGUAGES"] == tok.LANGUAGES
print(f"OK: {len(items)} ngon ngu (whisper {whisper.__version__}) -> {PATH}")
