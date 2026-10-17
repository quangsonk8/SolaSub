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

    def take(self, cursor: int, n_chars: int):
        """
        Lay doan bat dau tu word index `cursor` cho du `n_chars` ky tu (khong tinh space).
        Tra ve (start, end, prob_tb, cursor_moi, so_word_dung).
        """
        if cursor >= len(self.words):
            return None
        got = 0
        i = cursor
        used = []
        while i < len(self.words) and got < n_chars:
            w = self.words[i]
            got += sum(1 for c in w.text if not c.isspace())
            used.append(w)
            i += 1
        if not used:
            return None
        valid = [w for w in used if w.end > w.start]
        start = min(w.start for w in used)
        end = max(w.end for w in used)
        prob = sum(w.prob for w in used) / len(used)
        return start, end, prob, i, len(valid)


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


def align_words(model, audio: str, text: str, language: str = "ja") -> WordStream:
    """Chay forced alignment, tra ve chuoi tu. `text` PHAI la ban da normalize."""
    result = model.align(audio, text, language=language)
    words = [Word(w.word, float(w.start), float(w.end), float(w.probability or 0.0))
             for s in result.segments for w in getattr(s, "words", []) or []]
    return WordStream(words)


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
    cues, cursor = [], 0

    while pending:
        seg = pending.pop(0)
        need = sum(1 for c in seg if not c.isspace())
        got = stream.take(cursor, need)
        if got is None:
            break
        start, end, prob, next_cursor, n_valid = got

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
        cursor = next_cursor

    # Don chong lan truoc khi ap luat phim (giu nguyen thu tu, khong sort lai)
    for i in range(1, len(cues)):
        if cues[i]["start"] < cues[i - 1]["start"]:
            cues[i]["start"] = cues[i - 1]["start"]

    # preserve_starts: moc bat dau la su that do duoc, khong duoc day muon lai
    apply_film_style(cues, duration, preserve_starts=True)
    return cues
