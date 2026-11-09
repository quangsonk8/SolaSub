"""python -m unittest discover tests"""
import os
import random
import tempfile
import unittest

from solasub.align import Word, WordStream, build_cues
from solasub.problems import detect
from solasub.recover import (find_missing, heard_keys, match_pairs, pick_anchors, script_keys,
                             speech_rate)
from solasub.srt import write_srt

RATE = 6.0      # ky tu / giay


def _kana(rng, n):
    return "".join(chr(rng.randint(0x3041, 0x3093)) for _ in range(n))


def _heard(chars, t_start=0.0, skip=None, noise_every=0, rng=None):
    """Gia lap Whisper: moi ky tu 1 word, doc deu RATE ky tu/giay; `skip`=(a,b) KHONG doc (khong ton thoi gian)."""
    words, t = [], t_start
    for i, c in enumerate(chars):
        if skip and skip[0] <= i < skip[1]:
            continue
        if noise_every and i % noise_every == 0:
            c = chr(0x4E00 + rng.randint(0, 500))        # nghe sai chu (kanji khac)
        words.append(Word(c, t, t + 1 / RATE, 0.9))
        t += 1 / RATE
    return words, t


class FindMissing(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(7)
        self.script = _kana(self.rng, 3000)

    def _gaps(self, words, duration):
        S, _ = script_keys(self.script)
        H, t0, t1 = heard_keys(words)
        pairs = match_pairs(S, H)
        return find_missing(pairs, t0, t1, speech_rate(pairs, t0), start=(-1, 0.0), end=(len(S), duration))

    def test_finds_text_the_audio_skipped(self):
        words, dur = _heard(self.script, skip=(1200, 1850), noise_every=29, rng=self.rng)
        gaps = self._gaps(words, dur)
        self.assertEqual(len(gaps), 1)
        a, b, t_lo, t_hi = gaps[0]
        self.assertLessEqual(abs(a - 1200), 4)
        self.assertLessEqual(abs(b - 1850), 4)
        self.assertLess(t_hi - t_lo, 1.0)                   # audio gan nhu khong troi qua cho thieu
        self.assertAlmostEqual(t_lo, 1200 / RATE, delta=1.0)

    def test_misheard_but_spoken_is_not_missing(self):
        # 80 ky tu nghe sai hoan toan nhung VAN ton thoi gian doc -> khong phai doan thieu
        words, dur = _heard(self.script, noise_every=29, rng=self.rng)
        for w in words[1500:1580]:
            w.text = chr(0x4E00 + self.rng.randint(0, 500))
        self.assertEqual(self._gaps(words, dur), [])

    def test_missing_tail(self):
        words, dur = _heard(self.script, skip=(2600, 3000))
        gaps = self._gaps(words, dur)
        self.assertEqual(len(gaps), 1)
        self.assertLessEqual(abs(gaps[0][0] - 2600), 4)
        self.assertEqual(gaps[0][1], 3000)

    def test_complete_audio_has_no_gap(self):
        words, dur = _heard(self.script, noise_every=17, rng=self.rng)
        self.assertEqual(self._gaps(words, dur), [])


class Mmss(unittest.TestCase):
    def test_truncates_instead_of_rounding(self):
        from solasub.align import mmss
        self.assertEqual(mmss(390.1), "6:30")      # :.0f tung in 7:30
        self.assertEqual(mmss(59.6), "0:59")       # :.0f tung in 0:60
        self.assertEqual(mmss(3725), "62:05")


class Anchors(unittest.TestCase):
    def test_anchor_lands_right_after_a_sentence_end_inside_the_probe(self):
        rng = random.Random(3)
        text = "".join(_kana(rng, rng.randint(20, 40)) + "。" for _ in range(80))
        S, m2s = script_keys(text)
        ns_text = "".join(text.split())
        words, dur = _heard(S, noise_every=31, rng=rng)
        H, t0, t1 = heard_keys(words)
        pairs = match_pairs(S, H)
        probes = [(0.0, 12.0), (60.0, 72.0), (120.0, 132.0)]
        anchors = pick_anchors(pairs, t1, m2s, ns_text, probes)
        self.assertEqual(len(anchors), 3)
        for (s, t), (a, b) in zip(anchors, probes):
            self.assertEqual(ns_text[s - 1], "。")              # cat ngay sau dau het cau
            self.assertTrue(a <= t <= b)
            spoken = sum(1 for c in ns_text[:s] if c != "。")  # so ky tu doc truoc moc
            self.assertAlmostEqual(t, spoken / RATE, delta=0.5)


class MissingCues(unittest.TestCase):
    def test_missing_sentence_is_flagged_and_not_exported(self):
        s1, s2, s3 = "今日はいい天気ですね。", "明日は雨が降るでしょう。", "傘を持って出かけましょう。"
        words, t = [], 0.0
        for c in s1:
            words.append(Word(c, t, t + 0.15, 0.9)); t += 0.15
        cut = t + 0.1
        words.append(Word(s2, cut, cut, 0.0, missing=True))
        t = cut + 0.3
        for c in s3:
            words.append(Word(c, t, t + 0.15, 0.9)); t += 0.15
        stream = WordStream(words)
        cues = build_cues(stream, s1 + "\n" + s2 + "\n" + s3, t + 1)
        detect(cues, t + 1)
        texts = {c["text"]: c for c in cues}
        self.assertTrue(texts[s2]["missing"])
        self.assertEqual(texts[s2]["issues"], ["khong_co_trong_audio"])
        self.assertFalse(texts[s1]["missing"])
        self.assertNotIn("khong_co_trong_audio", texts[s3]["issues"])
        self.assertEqual(stream.missing_regions()[0]["chars"], len(s2))

        path = os.path.join(tempfile.mkdtemp(), "x.srt")
        self.assertEqual(write_srt(cues, path), 2)
        with open(path, encoding="utf-8") as f:
            self.assertNotIn("明日", f.read())


if __name__ == "__main__":
    unittest.main()
