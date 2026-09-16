from __future__ import annotations
import argparse, json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("summaries", nargs="+")
    args = p.parse_args()

    rows = []
    for item in args.summaries:
        d = json.loads(Path(item).read_text(encoding="utf-8"))
        rows.append({
            "label": d["label"],
            "docs": d["documents"],
            "err": d["errors"],
            "P": d["exact_precision"],
            "R": d["exact_recall"],
            "F1": d["exact_f1"],
            "R1": d["rank1_hit_rate"],
            "HitDoc": d["document_any_gold_rate"],
            "Cat": d["category_accuracy_on_exact"],
            "Wall_s": d["latency"]["wall_seconds"],
        })

    cols = ["label","docs","err","P","R","F1","R1","HitDoc","Cat","Wall_s"]
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    print(" | ".join(c.ljust(widths[c]) for c in cols))
    print("-+-".join("-"*widths[c] for c in cols))
    for r in rows:
        print(" | ".join(str(r[c]).ljust(widths[c]) for c in cols))


if __name__ == "__main__":
    main()
