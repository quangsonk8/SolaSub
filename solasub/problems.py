"""
Khoanh nhung cho CAN NGUOI XEM LAI.

Muc tieu cua SolaSub khong phai "tu dong 100%" ma la "tu dong 95% + chi ro 5% con lai".
Vi dung align() nen CHU luon dung (la ban goc), chi co THOI GIAN moi co the sai —
va may cai sai deu de lo ra bang may dau hieu duoi day.
"""
from .subtitle import (is_cjk, cps, spoken_weight, wrap_lines,
                       MIN_DUR, MAX_DUR, line_max)

# Nguong
LOW_PROB = 0.45          # do tin cay trung binh cua cue
BIG_GAP = 3.0            # khoang ho bat thuong truoc cue (giay)
CPS_OVER = 1.25          # vuot toc do doc cho phep bao nhieu lan


def detect(cues, duration):
    """Gan cue['issues'] = [ma_loi...] va tra ve thong ke."""
    stats = {}
    n = len(cues)
    for i, c in enumerate(cues):
        issues = []
        dur = c["end"] - c["start"]

        if c.get("failed"):
            issues.append("align_hong")          # moi word deu start==end
        if dur <= 0.05:
            issues.append("thoi_luong_0")
        if c.get("prob") is not None and c["prob"] < LOW_PROB:
            issues.append("do_tin_cay_thap")

        prev_end = cues[i - 1]["end"] if i else 0.0
        if c["start"] - prev_end > BIG_GAP:
            issues.append("ho_lon_truoc_cue")

        cjk = is_cjk(c["text"])
        if dur > 0 and spoken_weight(c["text"]) / dur > cps(cjk) * CPS_OVER:
            issues.append("doc_qua_nhanh")
        if dur > MAX_DUR + 0.01:
            issues.append("qua_dai")
        if dur < MIN_DUR - 0.01:
            issues.append("qua_ngan")

        # Van ban trong cue luon la MOT dong (de sua trong UI); viec be 2 dong chi xay ra
        # luc ghi file -> phai be thu roi moi do, khong do tren ban chua be.
        lm = line_max(cjk)
        if any(len(x) > lm for x in wrap_lines(c["text"]).split("\n")):
            issues.append("dong_tran")

        c["issues"] = issues

    for c in cues:
        for k in c["issues"]:
            stats[k] = stats.get(k, 0) + 1
    stats["_tong_cue"] = n
    stats["_cue_co_van_de"] = sum(1 for c in cues if c["issues"])
    return stats
