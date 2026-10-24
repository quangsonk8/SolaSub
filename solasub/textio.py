"""
Doc van ban goc: .txt / .md (tu do bang ma) va .docx (Word) — CHI dung thu vien chuan, khong them goi.

.docx la file zip chua word/document.xml. Lay chu theo tung doan van (w:p), giu tab va xuong dong, va BO:
  - w:rt        : chu phien am furigana (ruby) trong file tieng Nhat — de lai thi cach doc kana bi chen vao
                  kich ban, can chinh lech het.
  - w:delText   : chu DA XOA khi bat theo doi thay doi (track changes).
  - w:instrText : ma truong (vd PAGE, HYPERLINK "…") — khong phai loi thoai.
  - w:txbxContent: khung van ban (text box) — Word luu 2 ban (moi + du phong) nen de lai se bi lap.
"""
import io
import os
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
FILTER = "Văn bản / Word (*.txt *.md *.docx);;Word (*.docx);;Văn bản (*.txt *.md);;Tất cả (*.*)"

_SKIP = {W + "rt", W + "delText", W + "instrText", W + "txbxContent"}
_BREAK = {W + "br", W + "cr"}


def load_text(path: str) -> str:
    """Doc file van ban goc. Loi doc duoc -> ValueError voi thong bao tieng Viet de hien cho nguoi dung."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return read_docx(path)
    if ext == ".doc":
        raise ValueError("File .doc (Word 97–2003) chưa đọc được.\n\n"
                         "Mở file bằng Word → File → Save As → chọn “Word Document (*.docx)” rồi chọn lại.")
    raw = io.open(path, "rb").read()
    if raw[:4] == b"PK\x03\x04":            # thuc chat la .docx nhung bi doi duoi
        return read_docx(path)
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):   # Notepad "Unicode" = UTF-16 co BOM
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # File tieng Nhat cu hay luu Shift-JIS
        return raw.decode("shift_jis", errors="replace")


def read_docx(path: str) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        raise ValueError("Không đọc được file Word này (file hỏng hoặc không phải .docx).")
    body = ET.fromstring(xml).find(W + "body")
    if body is None:
        return ""
    paras = []
    _collect(body, paras)
    # Bo dong trong o dau/cuoi; giu dong trong o giua (ngat doan cua kich ban)
    return "\n".join(paras).strip("\n")


def _collect(node, out):
    """Duyet theo thu tu tai lieu, gap doan van (w:p) thi lay chu cua no (ke ca doan trong bang)."""
    for child in node:
        if child.tag in _SKIP:
            continue
        if child.tag == W + "p":
            out.append(_para_text(child))
        else:
            _collect(child, out)


def _para_text(p):
    parts = []

    def walk(n):
        for c in n:
            t = c.tag
            if t in _SKIP:
                continue
            if t == W + "t":
                parts.append(c.text or "")
            elif t == W + "tab":
                parts.append("\t")
            elif t in _BREAK:
                parts.append("\n")
            elif t == W + "noBreakHyphen":
                parts.append("-")
            else:
                walk(c)

    walk(p)
    return "".join(parts)
