"""
Luat cat dong theo chuan phu de dien anh.

Giu nguyen moi hang so va thuat toan da kiem chung o ban WinUI, de hai cong cu
cho ra SRT giong het nhau. Khac biet duy nhat: o day THOI GIAN den tu Whisper
(dung that) thay vi uoc luong theo ty le ky tu.
"""
import re

# ===== Chuan phu de phim =====
LINE_MAX_LATIN = 42     # ky tu/dong (chuan Netflix/BBC cho he Latin)
LINE_MAX_CJK = 20       # CJK moi ky tu la 1 am tiet -> dong phai ngan hon
MAX_LINES = 2
CPS_LATIN = 17.0        # toc do doc toi da (ky tu/giay)
CPS_CJK = 9.0
MIN_DUR = 1.0
MAX_DUR = 7.0
GAP = 0.10              # khoang ho giua 2 cue
LEAD_OUT = 0.15         # giu them sau khi dut tieng

SENTENCE_SPLIT = re.compile(r"(?<=[.!?;。！？；…؟؛।॥])")
COMMA_SPLIT = re.compile(r"(?<=[,、，：)）」』】،])")
AUDIO_TAG = re.compile(r"\[[^\]\r\n]{1,30}\]")

# Cam ky ngat dong tieng Nhat (禁則処理)
NO_START = "、。，．・：；？！ー）］｝」』〉》ぁぃぅぇぉっゃゅょゎヵヶ々,.!?:;)]}"
NO_END = "（［｛「『〈《([{"
PARTICLES = "をにへとがはでもやのからまでよりねよか"

_NEG_INF = float("-inf")


def normalize(text: str) -> str:
    """Bo audio tag + gom khoang trang. PHAI dung ban nay cho CA align lan chia cue."""
    return re.sub(r"\s+", " ", AUDIO_TAG.sub(" ", text)).strip()


def is_cjk(s: str) -> bool:
    cjk = letters = 0
    for c in s:
        if c.isspace() or (not c.isalnum() and not _in_cjk_block(c)):
            continue
        letters += 1
        if _in_cjk_block(c):
            cjk += 1
    return letters > 0 and cjk * 100 // letters >= 30


def _in_cjk_block(c: str) -> bool:
    o = ord(c)
    return (0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF
            or 0xAC00 <= o <= 0xD7AF or 0x3400 <= o <= 0x4DBF)


def line_max(cjk): return LINE_MAX_CJK if cjk else LINE_MAX_LATIN
def seg_max(cjk): return line_max(cjk) * MAX_LINES
def cps(cjk): return CPS_CJK if cjk else CPS_LATIN


def spoken_weight(s: str) -> int:
    """So ky tu THUC SU duoc doc (bo tag + khoang trang)."""
    return max(1, sum(1 for c in AUDIO_TAG.sub(" ", s) if not c.isspace()))


def is_hiragana(c): return 0x3041 <= ord(c) <= 0x309F
def is_katakana(c): return 0x30A0 <= ord(c) <= 0x30FF
def is_kanji(c): return 0x4E00 <= ord(c) <= 0x9FFF or 0x3400 <= ord(c) <= 0x4DBF


def cjk_break_score(s: str, i: int) -> float:
    """Diem vi tri ngat i (giua s[i-1] va s[i]). Cang cao cang giong ranh gioi tu."""
    if i <= 0 or i >= len(s):
        return _NEG_INF
    prev, cur = s[i - 1], s[i]
    if cur in NO_START or prev in NO_END:
        return _NEG_INF
    sc = 0.0
    if prev in "、，,":
        sc += 22                                        # ngat sau dau cau: thang ap dao
    if is_hiragana(prev) and not is_hiragana(cur):
        sc += 6                                         # hiragana -> kanji/katakana
    if prev in PARTICLES and not is_hiragana(cur):
        sc += 4                                         # ngay sau tro tu
    if is_kanji(prev) and is_hiragana(cur):
        sc -= 8                                         # kanji + okurigana = GIUA tu
    if is_katakana(prev) and is_katakana(cur):
        sc -= 6
    return sc


def _hard_wrap(s: str, max_len: int):
    """Cat doan qua dai khi khong con dau cau. CJK: do diem ngat, khong cat cung."""
    if " " in s:
        buf = []
        for w in s.split(" "):
            cur = " ".join(buf)
            if buf and len(cur) + 1 + len(w) > max_len:
                yield cur
                buf = []
            buf.append(w)
        if buf:
            yield " ".join(buf)
        return

    pos = 0
    while pos < len(s):
        if len(s) - pos <= max_len:
            yield s[pos:]
            return
        lo = pos + max(4, max_len * 6 // 10)
        hi = min(len(s) - 1, pos + max_len + max_len // 4)
        best, bs = -1, _NEG_INF
        for i in range(lo, hi + 1):
            sc = cjk_break_score(s, i)
            if sc == _NEG_INF:
                continue
            sc -= abs(i - (pos + max_len)) * 0.35       # cang gan max_len cang tot
            if sc > bs:
                bs, best = sc, i
        if best < 0:
            best = min(pos + max_len, len(s))
        yield s[pos:best]
        pos = best


def _append_clause(buf: str, part: str) -> str:
    if buf and part and ord(part[0]) < 128 and part[0].isalnum():
        return buf + " " + part
    return buf + part


def split_segments(text: str, max_len: int = 0):
    """Chia van ban thanh cac doan phu de. Port 1-1 tu SplitIntoSubtitleSegments."""
    out = []
    norm = normalize(text)
    if not norm:
        return out
    if max_len <= 0:
        max_len = seg_max(is_cjk(norm))

    for sentence in (x.strip() for x in SENTENCE_SPLIT.split(norm)):
        if not sentence:
            continue
        if len(sentence) <= max_len:
            out.append(sentence)
            continue
        buf = ""
        for part in (x.strip() for x in COMMA_SPLIT.split(sentence)):
            if not part:
                continue
            if len(part) > max_len:
                if buf:
                    out.append(buf); buf = ""
                out.extend(_hard_wrap(part, max_len))
            elif not buf:
                buf = part
            elif len(buf) + len(part) + 1 <= max_len:
                buf = _append_clause(buf, part)
            else:
                out.append(buf); buf = part
        if buf:
            out.append(buf)

    return out or [norm]


def wrap_lines(s: str) -> str:
    """Be 1 phu de thanh toi da 2 dong can doi, ton trong ranh gioi tu."""
    cjk = is_cjk(s)
    lm = line_max(cjk)
    if len(s) <= lm:
        return s

    mid = len(s) // 2
    best, best_score = -1, float("inf")
    for i in range(1, len(s)):
        if cjk:
            bs = cjk_break_score(s, i)
            if bs == _NEG_INF:
                continue
            score = -bs + abs(i - mid) * 0.4            # cang NHO cang tot
        else:
            if s[i] != " ":
                continue
            score = abs(i - mid)
            if s[i - 1] in ",;:":
                score -= 6
        first, second = i, len(s) - i - (0 if cjk else 1)
        if first > lm or second > lm:
            score += 1000                               # tran -> chi dung khi het cach
        if score < best_score:
            best_score, best = score, i
    if best < 0:
        return s
    return s[:best].rstrip() + "\n" + s[best:].lstrip()


def apply_film_style(cues, duration, preserve_starts=False):
    """
    cues: list dict { start, end, text }  — sua tai cho.
    Port tu ApplyFilmStyle: lead-out, thoi luong toi thieu theo CPS, tran 7s,
    khoang ho 100ms, khong chong lan, khong vuot do dai audio.

    preserve_starts=True khi moc bat dau la SU THAT do duoc (Whisper align), khong
    phai uoc luong: luc do tuyet doi khong duoc day start muon lai de thoa man
    thoi luong toi thieu — lam vay la tu tay tao ra do tre ma ta vua xoa bo duoc.
    """
    n = len(cues)
    for k in range(n):
        e = cues[k]
        if e["end"] <= e["start"]:
            e["end"] = e["start"] + 0.4

        nxt = cues[k + 1]["start"] if k < n - 1 else duration
        room = nxt - GAP

        # Lead-out, nhung khong duoc day cue vuot tran 7s
        if e["end"] + LEAD_OUT <= room and e["end"] + LEAD_OUT - e["start"] <= MAX_DUR:
            e["end"] += LEAD_OUT

        cjk = is_cjk(e["text"])
        needed = max(MIN_DUR, spoken_weight(e["text"]) / cps(cjk))
        if e["end"] - e["start"] < needed:
            e["end"] = min(e["start"] + needed, max(room, e["end"]))
            # Van thieu (bi cue sau chan) -> day cue sau muon lai neu no con du dai.
            # KHONG lam dieu nay khi start la moc do duoc: tha de cue ngan hon mot chut
            # con hon lam phu de cau sau hien tre.
            if (not preserve_starts) and e["end"] - e["start"] < needed and k < n - 1:
                want = e["start"] + needed
                new_next = want + GAP
                if new_next + MIN_DUR <= cues[k + 1]["end"]:
                    cues[k + 1]["start"] = new_next
                    e["end"] = want

        # Tran 7s — nhung khong duoc cat toi muc bo roi loi thoai
        if e["end"] - e["start"] > MAX_DUR:
            e["end"] = max(e["start"] + MAX_DUR, min(room, e["end"]))

        e["end"] = min(e["end"], duration)
        if e["end"] <= e["start"]:
            e["end"] = min(e["start"] + 0.4, duration)

        if k < n - 1 and cues[k + 1]["start"] < e["end"] + GAP:
            if preserve_starts:
                # Giu nguyen start that cua cue sau -> rut NGAN cue nay lai de chua khoang ho
                e["end"] = min(e["end"], cues[k + 1]["start"] - GAP)
                if e["end"] <= e["start"]:
                    e["end"] = max(e["start"] + 0.2, cues[k + 1]["start"] - 0.02)
            else:
                s = e["end"] + GAP
                if s < cues[k + 1]["end"] - 0.2:
                    cues[k + 1]["start"] = s
    return cues


def split_at_clauses(text: str, parts: int):
    """
    Chia text thanh ~parts nhom, CHI cat o ranh gioi menh de (ket cau / dau phay).
    Khong cat cung giua menh de -> khong che doi tu ghep (vd 立ち|上がりました).
    """
    units = []
    for sent in (x.strip() for x in SENTENCE_SPLIT.split(text)):
        if not sent:
            continue
        for cl in (y.strip() for y in COMMA_SPLIT.split(sent)):
            if cl:
                units.append(cl)
    if len(units) <= 1:
        return [text]

    total = sum(spoken_weight(u) for u in units)
    per = total / max(1, parts)
    res, buf, acc = [], "", 0.0
    for u in units:
        w = spoken_weight(u)
        if buf and acc + w / 2.0 > per:
            res.append(buf); buf = ""; acc = 0.0
        buf = _append_clause(buf, u)
        acc += w
    if buf:
        res.append(buf)
    return res
