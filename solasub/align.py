"""
Lay moc thoi gian THAT tu audio bang stable-ts forced alignment.

Khac han cach WinUI dang lam: WinUI uoc luong thoi gian theo ty le ky tu roi bam
khoang lang (do duoc 40% dung gio). O day Whisper nghe audio va chi ra tung tu nam
o giay nao (93% dung gio) — chu van la BAN GOC cua nguoi dung, khong phai chu Whisper nghe duoc.
"""
import os
from dataclasses import dataclass
from typing import List, Optional

from .subtitle import (normalize, split_segments, apply_film_style,
                       split_at_clauses, MAX_DUR)


@dataclass
class Word:
    text: str
    start: float
    end: float
    prob: float


class WordStream:
    """
    Chuoi tu kem moc thoi gian. Vi align() duoc nap DUNG van ban da normalize,
    ghep cac word lai se ra lai chinh van ban do (chi lech khoang trang) — nho vay
    anh xa ky-tu -> thoi gian la CHINH XAC, khong can khop mo.
    """

    def __init__(self, words: List[Word]):
        self.words = words
        # moc ky tu (bo khoang trang) tich luy tai dau moi word
        self._offsets = []
        n = 0
        for w in words:
            self._offsets.append(n)
            n += sum(1 for c in w.text if not c.isspace())
        self.total_chars = n

    def span(self, a: int, b: int):
        """
        Thoi gian cua doan ky tu [a, b) (chi so KY TU KHONG KHOANG TRANG trong van ban).
        Tra ve (start, end, prob_tb, so_word_hop_le) hoac None neu het chuoi.

        Tra theo VI TRI KY TU TUYET DOI, khong theo con tro word: take() cu lay word toi khi DU-HOAC-VUOT so ky
        tu -> word vat ngang ranh gioi 2 cau (tieng Nhat co nhieu word nhieu ky tu: 「ました。」) lam con tro chay
        truoc, phan thua CONG DON qua tung cau. Do thuc te 36 phut: lech 55 ky tu (+10s) o phut 8, ~250 ky tu cuoi
        bi day qua het audio -> 10 cau cuoi mat khoi SRT. Cau bat dau/ket thuc giua 1 word -> noi suy theo ty le ky tu.
        """
        import bisect
        if a >= self.total_chars or b <= a:
            return None
        b = min(b, self.total_chars)
        i = max(0, bisect.bisect_right(self._offsets, a) - 1)
        j = max(i, bisect.bisect_right(self._offsets, b - 1) - 1)

        def at(idx: int, ch: int, end: bool) -> float:
            w = self.words[idx]
            n = max(1, sum(1 for c in w.text if not c.isspace()))
            frac = (ch - self._offsets[idx] + (1 if end else 0)) / n
            return w.start + (w.end - w.start) * min(1.0, max(0.0, frac))

        used = self.words[i:j + 1]
        start = at(i, a, False)
        end = at(j, b - 1, True)
        prob = sum(w.prob for w in used) / len(used)
        return start, max(start, end), prob, sum(1 for w in used if w.end > w.start)


def load_model(name: str = "base", device: Optional[str] = None):
    import stable_whisper
    import torch
    from .paths import resource
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    # base.pt duoc dong goi san de lan chay dau khong phai tai 139 MB.
    # Model khac (small/medium/large) van tai ve cache cua nguoi dung nhu thuong.
    bundled = resource("models", f"{name}.pt")
    root = os.path.dirname(bundled) if bundled else None
    return stable_whisper.load_model(name, device=device, download_root=root), device


def _result_words(result, offset: float = 0.0) -> List[Word]:
    return [Word(w.word, float(w.start) + offset, float(w.end) + offset, float(w.probability or 0.0))
            for s in result.segments for w in getattr(s, "words", []) or []]


def align_words(model, audio: str, text: str, language: str = "ja", status=None) -> WordStream:
    """Chay forced alignment, tra ve chuoi tu. `text` PHAI la ban da normalize."""
    words = _result_words(model.align(audio, text, language=language))
    words = repair_alignment(model, audio, words, language, status)
    return WordStream(words)


# ===== Sua cuc bo nhung vung align bi lac =====
# Audio dai, align() doi khi BO CUOC o mot doan: do that tren 36 phut tieng Nhat, ~2 phut cuoi bi don het ve
# 36:35 ("Failed to align the last 603/8789 words") trong khi audio dung chu. Align lai RIENG doan audio nam
# giua 2 moc dung voi dung phan van ban do thi chinh xac (~0,5s so voi luc Whisper nghe thay).
_W_CHARS = 60          # cua so do toc do doc (ky tu, khong tinh khoang trang)
_MAX_CPS = 25.0        # nhanh hon = bi DON (TTS nhanh nhat ~10 ky tu/giay)
_MIN_CPS = 60 / 45.0   # 60 ky tu keo dai qua 45s = bi GIAN (nhay coc)
_SR = 16000


def _nchars(s: str) -> int:
    return sum(1 for c in s if not c.isspace())


def _bad_flags(words: List[Word]) -> List[bool]:
    n = len(words)
    bad = [False] * n
    cum, acc = [], 0
    for w in words:
        cum.append(acc)
        acc += _nchars(w.text)
    j = 0
    for i in range(n):
        if j < i:
            j = i
        while j < n and cum[j] - cum[i] < _W_CHARS:
            j += 1
        if j >= n:
            break
        dt = words[j].start - words[i].start
        if dt < _W_CHARS / _MAX_CPS or dt > _W_CHARS / _MIN_CPS:
            for k in range(i, j + 1):
                bad[k] = True
    # Chuoi tu do dai 0 lien tiep (>= 8 ky tu) = align bo cuoc o doan nay
    i = 0
    while i < n:
        if words[i].end - words[i].start <= 0.0:
            k = i
            while k < n and words[k].end - words[k].start <= 0.0:
                k += 1
            if sum(_nchars(w.text) for w in words[i:k]) >= 8:
                for m in range(i, k):
                    bad[m] = True
            i = k
        else:
            i += 1
    return bad


def _bad_regions(bad: List[bool], gap: int = 15, pad: int = 10):
    regions, i, n = [], 0, len(bad)
    while i < n:
        if not bad[i]:
            i += 1
            continue
        a = i
        while i < n and bad[i]:
            i += 1
        b = i - 1
        if regions and a - regions[-1][1] <= gap:
            regions[-1][1] = b
        else:
            regions.append([a, b])
    return [(max(0, a - pad), min(n - 1, b + pad)) for a, b in regions]


def repair_alignment(model, audio, words: List[Word], language: str, status=None,
                     max_passes: int = 3) -> List[Word]:
    if not words or not any(_bad_flags(words)):
        return words
    try:
        import whisper
        arr = whisper.load_audio(audio) if isinstance(audio, str) else audio
    except Exception:
        return words
    duration = len(arr) / _SR

    for _ in range(max_passes):
        bad = _bad_flags(words)
        regions = _bad_regions(bad)
        if not regions:
            break
        changed = False
        # Lam tu CUOI len dau: thay 1 vung khong lam lech chi so cua cac vung phia truoc
        for a, b in reversed(regions):
            t0 = words[a - 1].end if a > 0 else 0.0
            t1 = words[b + 1].start if b + 1 < len(words) else duration
            if t1 - t0 < 1.0:
                continue
            seg_text = "".join(w.text for w in words[a:b + 1])
            if status:
                status(f"Căn chỉnh lại đoạn {t0 / 60:.0f}:{t0 % 60:02.0f}–{t1 / 60:.0f}:{t1 % 60:02.0f}…")
            try:
                clip = arr[int(t0 * _SR):int(t1 * _SR)]
                new = _result_words(model.align(clip, seg_text, language=language), offset=t0)
            except Exception:
                continue
            # Anh xa ky tu -> thoi gian dua tren viec ghep word ra DUNG van ban: so ky tu phai khop
            if _nchars("".join(w.text for w in new)) != _nchars(seg_text):
                continue
            candidate = words[:a] + new + words[b + 1:]
            lo, hi = max(0, a - 30), min(len(candidate), a + len(new) + 30)
            old_bad = sum(_nchars(w.text) for w, f in zip(words[lo:b + 31], _bad_flags(words)[lo:b + 31]) if f)
            new_bad = sum(_nchars(w.text) for w, f in zip(candidate[lo:hi], _bad_flags(candidate)[lo:hi]) if f)
            if new_bad < old_bad:
                words = candidate
                changed = True
        if not changed:
            break
    return words


def transcribe_words(model, audio: str, language: str = "ja"):
    """
    Khong co van ban goc -> de Whisper tu NGHE ra chu.

    Chat luong kem han han align(): Whisper nghe dung am nhung viet sai chu, nhat la
    ten rieng va kanji (do thuc te: 「その仔細を糺さねばならぬ」 bi nghe thanh
    「その死材をなくさればならね」). Chi dung khi nguoi dung khong co kich ban.
    Tra ve (WordStream, van ban Whisper nghe duoc).
    """
    result = model.transcribe(audio, language=language, word_timestamps=True)
    words = [Word(w.word, float(w.start), float(w.end), float(w.probability or 0.0))
             for s in result.segments for w in getattr(s, "words", []) or []]
    if not words:   # mot so model khong tra ve word -> lui ve muc doan
        words = [Word(s.text, float(s.start), float(s.end), 0.0)
                 for s in result.segments]
    return WordStream(words), "".join(w.text for w in words)


def build_cues(stream: WordStream, text: str, duration: float):
    """
    Chia van ban theo luat phu de phim, roi GAN thoi gian that tu chuoi tu.

    Day la diem khac biet cot loi: Whisper cat theo tu (ra hang nghin doan vun),
    con o day ta giu cach chia cue theo CAU/MENH DE da kiem chung o WinUI, chi muon
    moc thoi gian cua Whisper.
    """
    pending = list(split_segments(text))
    cues, pos = [], 0     # pos = vi tri ky tu (khong khoang trang) cua dau cau hien tai

    while pending:
        seg = pending.pop(0)
        need = sum(1 for c in seg if not c.isspace())
        got = stream.span(pos, pos + need)
        if got is None:
            break
        start, end, prob, n_valid = got

        # Cue qua dai -> TACH o ranh gioi menh de roi do lai thoi gian that cho tung manh.
        # Ban C# phai noi suy vi khong biet tung tu o giay nao; o day tra cuu duoc chinh xac.
        if end - start > MAX_DUR:
            pieces = split_at_clauses(seg, max(2, int((end - start) // MAX_DUR) + 1))
            if len(pieces) > 1:
                pending = pieces + pending
                continue

        cues.append({
            "start": start, "end": end, "text": seg,
            "prob": prob,
            "n_words": max(1, n_valid),
            "failed": n_valid == 0,          # moi word deu start==end -> align hong
        })
        pos += need

    # Don chong lan truoc khi ap luat phim (giu nguyen thu tu, khong sort lai)
    for i in range(1, len(cues)):
        if cues[i]["start"] < cues[i - 1]["start"]:
            cues[i]["start"] = cues[i - 1]["start"]

    # preserve_starts: moc bat dau la su that do duoc, khong duoc day muon lai
    apply_film_style(cues, duration, preserve_starts=True)
    return cues
