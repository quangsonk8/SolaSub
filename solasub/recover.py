"""
Kich ban co doan KHONG co trong audio -> tim ra, danh dau, va van can dung phan con lai.

Vi sao can: align() bat buoc MOI chu trong kich ban phai duoc doc. Gap audio bi thieu (vd audio TTS tao bang
nhieu doan, moi doan bi cat mat duoi), no mat nhip ngay cho thieu dau tien va khong bat lai duoc: do that tren 1
file 90 phut tieng Nhat thieu 9 cho (~650 ky tu moi cho) -> 64% so tu bi don het ve giay cuoi, 1376/1485 cue hong.
Chi 1 cho thieu ~95 ky tu (file 77 phut khac) cung du pha hong toan bo phan sau.

Cach lam (nghe lai TOAN BO audio tren CPU chi ~4x thoi gian thuc: 90 phut -> 22 phut -> qua cham):
1. Nghe thu 12s moi phut -> lay MOC: 1 cho het cau ma chu nghe duoc khop chac voi kich ban.
2. Cat audio + kich ban theo cac moc thanh khuc ~1 phut, align RIENG tung khuc (tong = 1 luot align).
   align() cuc nhay voi chu khong duoc doc -> khuc nao hong la khuc co van de.
3. Nghe KY rieng khuc hong (them 15s ngu canh moi ben), ghep chu nghe duoc voi kich ban: cho kich ban nhay
   coc nhieu chu ma audio gan nhu khong troi thoi gian = doan THIEU. Cat o cho lang nhat, align lai phan con lai.
Ham thuan (khong can model) tach rieng de test duoc.
"""
import bisect
import statistics
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from .align import Word, _bad_flags, _nchars, _result_words, mmss, repair_alignment, _SR

K = 4                 # do dai k-gram lam moc khop
MIN_MISSING = 25      # ky tu (khong tinh dau cau) toi thieu de coi la 1 doan thieu
SHORT_GAP = 8         # khoang chua khop ngan hon thi bo qua (Whisper nghe sai vai chu la chuyen thuong)
TIME_SHARE = 0.35     # audio co < 35% thoi gian can de doc khoang chu do -> chu do khong duoc doc
MERGE_CHARS = 12      # 2 doan thieu chi cach nhau vai chu "khop" (khop nham) va gan nhu cung thoi diem -> gop
MERGE_SECONDS = 2.0

PROBE_EVERY = 60.0    # nghe thu 12s moi phut
PROBE_LEN = 12.0
ANCHOR_RUN = 6        # moc phai nam cuoi 1 chuoi >= 6 ky tu khop lien tiep (khop ngau nhien khong dai the)
BAD_CHARS = 20        # khuc co >= 20 ky tu align lech nhip -> nghe ky khuc do
CONTEXT = 15.0        # nghe ky: them 15s moi ben — Whisper nghe kem o mep doan cat cut (do: bao nham 3 cho)
SUB_EVERY = 10.0      # khuc align roi (khong thieu chu): chia khuc con ~10s theo cho het cau da nghe ky

TRACE: List[str] = []    # vet quyet dinh cua lan do gan nhat (de chan doan; khong anh huong ket qua)

# Dau cau / ky hieu: khong doc thanh tieng, bo khi so khop. KHONG bo 'ー' (truong am, la mot phan cua tu).
_PUNCT = set("、。，．！？「」『』（）()【】〈〉《》…‥・,.!?;:：；\"'“”‘’〜~-—–♪")
_SENT_END = set("。．！？!?」』…")
# Dau DONG / ket cau di theo cau truoc. KHONG gom dau mo 「『（: nuot 「 cua cau sau vao khuc truoc -> khuc ket thuc
# bang 1 dau mo le, stable-ts lap lai tu cuoi (「…けど」けど」「」) -> lech so ky tu (do: 6/7 khuc lech vi vay).
_TRAILING = set("、。，．！？!?」』）)】〉》…‥・,.;:：；\"'”’〜~♪")


def _fold(c: str) -> str:
    o = ord(c)
    if 0x30A1 <= o <= 0x30F6:            # katakana -> hiragana (Whisper hay viet lan hai bang chu)
        return chr(o - 0x60)
    if 0xFF01 <= o <= 0xFF5E:            # chu/so full-width -> ASCII
        return chr(o - 0xFEE0).lower()
    return c.lower()


def _matchable(c: str) -> bool:
    return not c.isspace() and c not in _PUNCT


def script_keys(text: str) -> Tuple[str, List[int]]:
    """(chuoi so khop, m2s): m2s[k] = vi tri ky tu (KHONG tinh khoang trang, nhu WordStream) cua ky tu so khop k."""
    keys, m2s, n = [], [], 0
    for c in text:
        if c.isspace():
            continue
        if _matchable(c):
            keys.append(_fold(c))
            m2s.append(n)
        n += 1
    return "".join(keys), m2s


def heard_keys(words: List[Word]):
    """(chuoi nghe duoc, t0[], t1[]): thoi diem bat dau/ket thuc cua tung ky tu (noi suy deu trong word)."""
    keys, t0, t1 = [], [], []
    for w in words:
        cs = [c for c in w.text if _matchable(c)]
        if not cs:
            continue
        d = max(0.0, w.end - w.start) / len(cs)
        for i, c in enumerate(cs):
            keys.append(_fold(c))
            t0.append(w.start + i * d)
            t1.append(w.start + (i + 1) * d)
    return "".join(keys), t0, t1


def _unique_grams(s: str, k: int):
    pos = {}
    for i in range(len(s) - k + 1):
        g = s[i:i + k]
        pos[g] = -1 if g in pos else i
    return {g: i for g, i in pos.items() if i >= 0}


def _lis(pairs):
    """Day con dai nhat tang chat theo j (pairs da sap theo i)."""
    tails, tails_at, prev = [], [], [-1] * len(pairs)
    for n, (_, j) in enumerate(pairs):
        p = bisect.bisect_left(tails, j)
        if p == len(tails):
            tails.append(j)
            tails_at.append(n)
        else:
            tails[p] = j
            tails_at[p] = n
        prev[n] = tails_at[p - 1] if p else -1
    out, n = [], (tails_at[-1] if tails_at else -1)
    while n >= 0:
        out.append(pairs[n])
        n = prev[n]
    return out[::-1]


def match_pairs(S: str, H: str, k: int = K):
    """Cac cap (i trong S, j trong H) khop nhau, tang dan ca hai phia."""
    us, uh = _unique_grams(S, k), _unique_grams(H, k)
    chain = _lis(sorted((i, uh[g]) for g, i in us.items() if g in uh))
    pairs = []
    pi = pj = 0                                   # da phu toi (khong gom) pi trong S, pj trong H
    for i, j in chain + [(len(S), len(H))]:
        if i < pi or j < pj:                      # moc goi len moc truoc
            continue
        a, b = S[pi:i], H[pj:j]
        if a and b and len(a) * len(b) <= 4_000_000:
            for blk in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
                if blk.size >= 3:                 # khop 1-2 chu le te (の, が...) la ngau nhien
                    pairs.extend((pi + blk.a + x, pj + blk.b + x) for x in range(blk.size))
        if i < len(S):
            pairs.extend((i + x, j + x) for x in range(k))
            pi, pj = i + k, j + k
    return pairs


def speech_rate(pairs, t0) -> Optional[float]:
    """Toc do doc (ky tu so khop / giay): trung vi tren cac cua so ~80 ky tu — cho thieu chi la ngoai lai."""
    rates, last = [], None
    for i, j in pairs:
        if last is None:
            last = (i, j)
        elif i - last[0] >= 80:
            dt = t0[j] - t0[last[1]]
            if dt > 0:
                rates.append((i - last[0]) / dt)
            last = (i, j)
    return statistics.median(rates) if rates else None


def find_missing(pairs, t0, t1, rate: float, start=None, end=None):
    """
    [(a, b, t_lo, t_hi)]: doan [a, b) cua chuoi so khop khong duoc doc; audio chuyen tu phan truoc sang phan sau
    trong [t_lo, t_hi]. start/end = (i, t): moc ao dau/cuoi FILE (de bat doan thieu o dau/duoi); None = chi xet
    khoang giua cac cap khop that (khi chi nghe 1 khuc giua file).
    """
    pts = ([(start[0], start[1], start[1])] if start else []) + [(i, t0[j], t1[j]) for i, j in pairs] \
        + ([(end[0], end[1], end[1])] if end else [])
    gaps = []
    for (pi, _, p_end), (qi, q_start, _) in zip(pts, pts[1:]):
        gap = qi - pi - 1
        if gap >= SHORT_GAP and (q_start - p_end) < TIME_SHARE * gap / rate:
            gaps.append([pi + 1, qi, p_end, q_start])
    merged = []
    for g in gaps:
        if merged and g[0] - merged[-1][1] <= MERGE_CHARS and g[2] - merged[-1][3] <= MERGE_SECONDS:
            merged[-1][1], merged[-1][3] = g[1], g[3]
        else:
            merged.append(g)
    return [tuple(g) for g in merged if g[1] - g[0] >= MIN_MISSING]


def sentence_anchors(pairs, t1, m2s: List[int], ns_text: str, a: float, b: float, min_gap: float = 0.0):
    """
    Moc (vi_tri_ky_tu, thoi_diem) trong [a, b - 0.5]: ngay SAU 1 cho het cau, ma ky tu truoc no nam cuoi chuoi
    >= ANCHOR_RUN cap khop lien tiep (khop ngau nhien khong dai the). Cat o het cau -> khong che doi tu, co quang
    lang de cat. min_gap: cac moc cach nhau it nhat bao nhieu giay.
    """
    out, run, prev = [], 0, None
    for i, j in pairs:
        if not (a <= t1[j] <= b - 0.5):
            prev = None
            continue
        run = run + 1 if prev and prev == (i - 1, j - 1) else 1
        prev = (i, j)
        if run < ANCHOR_RUN:
            continue
        p = m2s[i] + 1
        if p < len(ns_text) and ns_text[p] in _SENT_END:
            while p < len(ns_text) and ns_text[p] in _TRAILING:
                p += 1
            if not out or t1[j] - out[-1][1] >= min_gap:
                out.append((p, t1[j]))
    return out


def pick_anchors(pairs, t1, m2s: List[int], ns_text: str, windows):
    """Moi cua so nghe thu -> toi da 1 moc (cai muon nhat trong cua so)."""
    out = []
    for a, b in windows:
        got = sentence_anchors(pairs, t1, m2s, ns_text, a, b)
        if got:
            out.append(got[-1])
    return out


def quietest(arr, t_lo: float, t_hi: float, pad: float = 0.25) -> float:
    """Diem lang nhat (khung 40ms) trong [t_lo - pad, t_hi + pad] — cat audio o day it pham vao tieng noi nhat."""
    import numpy as np
    a = max(0, int((t_lo - pad) * _SR))
    b = min(len(arr), int((t_hi + pad) * _SR))
    fr = int(0.04 * _SR)
    if b - a < 2 * fr:
        return (t_lo + t_hi) / 2
    seg = arr[a:b]
    n = (len(seg) // fr) * fr
    energy = np.sqrt((seg[:n].reshape(-1, fr) ** 2).mean(axis=1))
    k = int(energy.argmin())
    return (a + k * fr + fr / 2) / _SR


def recover_missing(model, audio: str, text: str, language: str, status=None) -> Optional[List[Word]]:
    """
    Tra ve chuoi tu moi (co Word.missing cho doan thieu) hoac None neu khong thay doan thieu nao
    (luc do align() hong vi ly do khac — nhac nen, am thanh lan... — giu ket qua cu).
    """
    import whisper
    say = status or (lambda m: None)
    arr = whisper.load_audio(audio)
    duration = len(arr) / _SR
    S, m2s = script_keys(text)
    ns_text = "".join(c for c in text if not c.isspace())
    ns2t = [i for i, c in enumerate(text) if not c.isspace()]
    total = len(ns_text)
    TRACE[:] = []
    if len(S) < 50:
        return None

    def listen(a, b):
        res = model.transcribe(arr[int(a * _SR):int(b * _SR)], language=language, word_timestamps=True,
                               condition_on_previous_text=False, verbose=None)
        return _result_words(res, offset=a)

    def piece(p, q):                    # van ban (giu khoang trang ben trong) cua ky tu [p, q)
        return text[ns2t[p]:ns2t[q - 1] + 1] if q > p else ""

    def align_piece(p, q, ta, tb):
        """
        Align [p, q) vao audio [ta, tb]. Tra (words tuyet doi, words tuong doi | None, clip).
        words tuong doi = None: align tra ve SAI so ky tu (rot/lap chu khi khuc co chu khong duoc doc) -> words
        tuyet doi la 1 word noi suy deu de giu dung anh xa ky tu, nguoi goi coi khuc nay la hong.
        """
        seg = piece(p, q)
        if not seg:
            return [], [], None
        if tb - ta < 0.5:
            return [Word(seg, ta, max(ta, tb), 0.0)], [], None
        clip = arr[int(ta * _SR):int(tb * _SR)]
        rel = _result_words(model.align(clip, seg, language=language))
        if _nchars("".join(w.text for w in rel)) != q - p:
            TRACE.append(f"[{p},{q}) {ta:.0f}-{tb:.0f}s align tra sai so ky tu")
            return [Word(seg, ta, tb, 0.0)], None, clip
        return [Word(w.text, w.start + ta, w.end + ta, w.prob) for w in rel], rel, clip

    # 1. Nghe thu -> moc
    probes = [(t, min(duration, t + PROBE_LEN)) for t in
              (k * PROBE_EVERY for k in range(int(duration // PROBE_EVERY) + 1)) if duration - t > 2.0]
    heard = []
    for k, (a, b) in enumerate(probes):
        say(f"Audio có vẻ thiếu đoạn so với văn bản — đang nghe thử để dò ({100 * k // len(probes)}%)…")
        heard += listen(a, b)
    H, h0, h1 = heard_keys(heard)
    pairs = match_pairs(S, H) if len(H) >= 50 else []
    rate = speech_rate(pairs, h0) if pairs else None
    if not rate:
        TRACE.append("khong du chu nghe thu de dat moc")
        return None
    pts = [(0, 0.0)]
    for s, t in pick_anchors(pairs, h1, m2s, ns_text, probes):
        cut = quietest(arr, t, t + 0.6, pad=0.1)
        if s > pts[-1][0] and cut > pts[-1][1] + 1.0 and s < total:
            pts.append((s, cut))
    pts.append((total, duration))
    TRACE.append(f"toc do {rate:.2f} ky tu/s; {len(pts) - 2} moc")

    # 2. Align tung khuc; 3. khuc hong -> nghe ky, tim doan thieu, align lai
    words: List[Word] = []
    n_missing = 0
    for k, ((p, ta), (q, tb)) in enumerate(zip(pts, pts[1:])):
        say(f"Đang căn từng khúc để dò đoạn thiếu ({k + 1}/{len(pts) - 1})…")
        got, rel, clip = align_piece(p, q, ta, tb)
        if rel is None:
            bad = q - p                     # tra sai so ky tu = hong ca khuc
        else:
            bad = sum(_nchars(w.text) for w, f in zip(rel, _bad_flags(rel)) if f) if rel else 0
        if bad < BAD_CHARS:
            words += got
            continue

        say(f"Khúc {mmss(ta)}–{mmss(tb)} nghi thiếu — đang nghe kỹ…")
        wa, wb = max(0.0, ta - CONTEXT), min(duration, tb + CONTEXT)
        Hk, k0, k1 = heard_keys(listen(wa, wb))
        k_lo, k_hi = bisect.bisect_left(m2s, p), bisect.bisect_left(m2s, q)
        margin = int(CONTEXT * rate * 1.5)
        s_lo, s_hi = max(0, k_lo - margin), min(len(S), k_hi + margin)
        local = [(i + s_lo, j) for i, j in match_pairs(S[s_lo:s_hi], Hk)] if len(Hk) >= 20 else []
        gaps = find_missing(local, k0, k1, rate,
                            start=(-1, 0.0) if p == 0 else None,
                            end=(len(S), duration) if q == total else None) if local else []
        # chi lay phan nam trong khuc nay
        spans = []
        for a, b, lo, hi in gaps:
            a, b = max(a, k_lo), min(b, k_hi)
            if b - a >= MIN_MISSING and ta - 2.0 <= lo and hi <= tb + 2.0:
                ma = m2s[a]
                mb = m2s[b] if b < len(m2s) else total
                spans.append((max(p, ma), min(q, mb), quietest(arr, lo, hi)))
        TRACE.append(f"khuc {ta:.0f}-{tb:.0f}s: {bad} ky tu lech -> thieu {[(a, b, round(c, 1)) for a, b, c in spans]}")
        if not spans:
            # Khong thieu chu, chi la align bi roi trong khuc nay (do: 1 khuc 52:10-53:10 lech 11-20s du audio
            # khop kich ban). Da nghe ky khuc nay roi -> cat nho them o cac cho het cau khop chac (~10s), align
            # tung khuc con: khuc cang ngan align cang kho lac.
            sub = [(s, quietest(arr, t, t + 0.6, pad=0.1))
                   for s, t in sentence_anchors(local, k1, m2s, ns_text, ta + 1.0, tb - 1.0, min_gap=SUB_EVERY)
                   if p < s < q]
            pts_k = [(p, ta)]
            for s, t in sub:
                if s > pts_k[-1][0] and t > pts_k[-1][1] + 1.0:
                    pts_k.append((s, t))
            pts_k.append((q, tb))
            TRACE.append(f"  -> chia {len(pts_k) - 1} khuc con")
            for (sp, st), (sq, sb) in zip(pts_k, pts_k[1:]):
                g2, r2, c2 = align_piece(sp, sq, st, sb)
                if r2:
                    r2 = repair_alignment(model, c2, r2, language)
                    words += [Word(w.text, w.start + st, w.end + st, w.prob) for w in r2]
                else:
                    words += g2             # noi suy (hiem) -> cue se bi danh dau do tin cay thap
            continue
        cur_p, cur_t = p, ta
        for ma, mb, cut in spans:
            if ma > cur_p:
                words += align_piece(cur_p, ma, cur_t, cut)[0]
            words.append(Word(piece(ma, mb), cut, cut, 0.0, missing=True))
            n_missing += 1
            cur_p, cur_t = mb, cut
        if q > cur_p:
            words += align_piece(cur_p, q, cur_t, tb)[0]

    if not n_missing:
        TRACE.append("khong thay doan thieu")
        return None
    if _nchars("".join(w.text for w in words)) != total:
        TRACE.append("tong so ky tu sai -> bo ket qua")
        return None
    return words
