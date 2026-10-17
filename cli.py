"""
SolaSub — tao phu de tu audio + van ban goc.

    python cli.py --audio story.mp3 --text story.txt --lang ja

Chu trong SRT LUON la van ban goc cua ban; Whisper chi lam mot viec duy nhat
la chi ra tung tu nam o giay nao.
"""
import argparse
import io
import json
import os
import time

from solasub.paths import ensure_ffmpeg_on_path
ensure_ffmpeg_on_path()   # whisper goi thang "ffmpeg" tu PATH

from solasub.align import load_model, align_words, build_cues  # noqa: E402
from solasub.problems import detect
from solasub.srt import audio_duration, write_srt
from solasub.subtitle import normalize


def main():
    ap = argparse.ArgumentParser(description="Tao phu de bang forced alignment")
    ap.add_argument("--audio", required=True)
    ap.add_argument("--text", required=True, help="File van ban goc (.txt, UTF-8)")
    ap.add_argument("--lang", default="ja")
    ap.add_argument("--model", default="base")
    ap.add_argument("--device", default=None, help="cuda | cpu (mac dinh: tu chon)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    raw = io.open(args.text, encoding="utf-8").read()
    text = normalize(raw)
    dur = audio_duration(args.audio)
    print(f"[audio] {dur:.1f}s ({dur/60:.1f} phut) | van ban {len(text)} ky tu")

    t0 = time.time()
    model, device = load_model(args.model, args.device)
    print(f"[model] {args.model} tren {device} ({time.time()-t0:.1f}s)")

    t0 = time.time()
    stream = align_words(model, args.audio, text, args.lang)
    t_align = time.time() - t0
    print(f"[align] {t_align:.1f}s -> nhanh gap {dur/t_align:.0f}x thoi gian thuc"
          f" | {len(stream.words)} tu")

    cues = build_cues(stream, text, dur)
    stats = detect(cues, dur)

    out = args.out or os.path.splitext(args.audio)[0] + ".srt"
    n = write_srt(cues, out)

    print(f"\n[ket qua] {n} cue -> {out}")
    print(f"  cue can xem lai: {stats['_cue_co_van_de']}/{stats['_tong_cue']}"
          f" ({100*stats['_cue_co_van_de']/max(1,stats['_tong_cue']):.1f}%)")
    for k, v in sorted(stats.items()):
        if not k.startswith("_"):
            print(f"    {k:22s} {v}")

    json.dump({"stats": stats, "align_seconds": t_align, "duration": dur,
               "model": args.model, "device": device, "cues": cues},
              io.open(out + ".json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
