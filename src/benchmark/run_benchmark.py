from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from time import perf_counter

from src.semantic.action_extractor import ActionOrientedExtractor
from src.semantic.local_llm import LocalLLMClient


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if "decisao" not in row or "gold" not in row:
                raise ValueError(f"Linha {line_no}: registro inválido.")
            rows.append(row)
    return rows


def match_document(preds: list[dict], golds: list[dict]) -> dict:
    matched_p: set[int] = set()
    matched_g: set[int] = set()
    pairs: list[tuple[int, int]] = []

    for pi, pred in enumerate(preds):
        for gi, gold in enumerate(golds):
            if pi in matched_p or gi in matched_g:
                continue
            if normalize(pred["text"]) == normalize(gold["text"]):
                matched_p.add(pi)
                matched_g.add(gi)
                pairs.append((pi, gi))

    category_correct = sum(
        preds[pi].get("category") == golds[gi].get("category")
        for pi, gi in pairs
    )

    rank1_hit = False
    if preds:
        rank1_hit = any(
            normalize(preds[0]["text"]) == normalize(g["text"])
            for g in golds
        )

    return {
        "pred_count": len(preds),
        "gold_count": len(golds),
        "tp": len(pairs),
        "category_correct": category_correct,
        "rank1_hit": rank1_hit,
        "any_gold_found": bool(matched_g),
        "all_gold_found": len(matched_g) == len(golds),
    }


def div(a: float, b: float) -> float:
    return a / b if b else 0.0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True)
    p.add_argument("--base-url", default="http://127.0.0.1:8081/v1")
    p.add_argument("--model", default="")
    p.add_argument("--label", default="pilot")
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--output-dir", default="runtime")
    p.add_argument("--show-text", action="store_true")
    args = p.parse_args()

    rows = load_jsonl(Path(args.dataset))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== DIDE1 — BENCHMARK SINTÉTICO / PILOTO LOCAL ===")
    print("dataset:", args.dataset)
    print("documentos:", len(rows))
    print("dados reais PGFN: NÃO")
    print("API externa: NÃO")

    client = LocalLLMClient(
        base_url=args.base_url,
        model=(args.model or None),
    )
    print("modelo:", client.health())
    print()

    extractor = ActionOrientedExtractor(client)

    total_pred = total_gold = total_tp = 0
    category_correct = 0
    docs_any = docs_all = rank1_hits = 0
    errors = 0
    duplicate_outputs = 0
    success_latencies: list[float] = []
    attempt_latencies: list[float] = []
    difficulty = Counter()
    scenarios = Counter()

    results_path = out_dir / f"results_{args.label}.jsonl"
    summary_path = out_dir / f"summary_{args.label}.json"

    benchmark_started = perf_counter()

    with results_path.open("w", encoding="utf-8") as out:
        for i, row in enumerate(rows, start=1):
            started = perf_counter()
            try:
                result = extractor.extract(row["decisao"], top_k=args.top_k)
                elapsed = perf_counter() - started
                success_latencies.append(elapsed)
                attempt_latencies.append(elapsed)

                preds = result["recortes"]
                keys = [normalize(p["text"]) for p in preds]
                duplicate_outputs += len(keys) - len(set(keys))

                ev = match_document(preds, row["gold"])
                total_pred += ev["pred_count"]
                total_gold += ev["gold_count"]
                total_tp += ev["tp"]
                category_correct += ev["category_correct"]
                docs_any += int(ev["any_gold_found"])
                docs_all += int(ev["all_gold_found"])
                rank1_hits += int(ev["rank1_hit"])

                difficulty[f"{row['dificuldade']}|hit={ev['any_gold_found']}"] += 1
                scenarios[f"{row['cenario']}|hit={ev['any_gold_found']}"] += 1

                rec = {
                    "id_sintetico": row["id_sintetico"],
                    "cenario": row["cenario"],
                    "dificuldade": row["dificuldade"],
                    "latency_seconds": round(elapsed, 3),
                    "gold": row["gold"],
                    "predictions": preds,
                    "evaluation": ev,
                    "pipeline": {
                        "n_units": result["n_units"],
                        "n_chunks": result["n_chunks"],
                        "n_candidates_before_final": result[
                            "n_candidates_before_final"
                        ],
                        "llm_calls": result["llm_calls"],
                        "filter_reasons": result["filter_reasons"],
                    },
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")

                print(
                    f"[{i}/{len(rows)}] {row['id_sintetico']} "
                    f"{row['cenario']} | gold={ev['gold_count']} "
                    f"pred={ev['pred_count']} tp={ev['tp']} "
                    f"rank1={int(ev['rank1_hit'])} tempo={elapsed:.1f}s"
                )
                if args.show_text:
                    for j, pred in enumerate(preds, start=1):
                        print(
                            f"  PRED {j} [{pred['category']}] "
                            f"{pred['text']}"
                        )

            except Exception as exc:
                elapsed = perf_counter() - started
                attempt_latencies.append(elapsed)
                errors += 1
                print(
                    f"[{i}/{len(rows)}] ERRO {row['id_sintetico']}: "
                    f"{type(exc).__name__}: {str(exc)[:220]}"
                )
                out.write(json.dumps({
                    "id_sintetico": row["id_sintetico"],
                    "scenario": row["cenario"],
                    "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                    "latency_seconds": round(elapsed, 3),
                }, ensure_ascii=False) + "\n")

    wall = perf_counter() - benchmark_started
    precision = div(total_tp, total_pred)
    recall = div(total_tp, total_gold)
    f1 = div(2 * precision * recall, precision + recall)

    summary = {
        "benchmark_version": "2.0.0",
        "label": args.label,
        "documents": len(rows),
        "errors": errors,
        "successful_documents": len(rows) - errors,
        "predictions_total": total_pred,
        "gold_total": total_gold,
        "tp_exact": total_tp,
        "exact_precision": round(precision, 4),
        "exact_recall": round(recall, 4),
        "exact_f1": round(f1, 4),
        "rank1_hit_rate": round(div(rank1_hits, len(rows)), 4),
        "document_any_gold_rate": round(div(docs_any, len(rows)), 4),
        "document_all_gold_rate": round(div(docs_all, len(rows)), 4),
        "category_accuracy_on_exact": round(
            div(category_correct, total_tp), 4
        ),
        "duplicate_outputs": duplicate_outputs,
        "latency": {
            "mean_success_seconds": round(
                div(sum(success_latencies), len(success_latencies)), 3
            ),
            "mean_attempt_seconds": round(
                div(sum(attempt_latencies), len(attempt_latencies)), 3
            ),
            "wall_seconds": round(wall, 3),
        },
        "difficulty_breakdown": dict(difficulty),
        "scenario_breakdown": dict(scenarios),
        "security": {
            "synthetic_only": True,
            "spreadsheet_api_used": False,
            "external_llm_api_used": False,
        },
    }

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=== RESULTADO ===")
    print("exact precision:", summary["exact_precision"])
    print("exact recall:", summary["exact_recall"])
    print("exact f1:", summary["exact_f1"])
    print("rank1 hit rate:", summary["rank1_hit_rate"])
    print("doc any-gold rate:", summary["document_any_gold_rate"])
    print("doc all-gold rate:", summary["document_all_gold_rate"])
    print("category accuracy:", summary["category_accuracy_on_exact"])
    print("erros:", errors)
    print("duplicatas:", duplicate_outputs)
    print("wall time (s):", summary["latency"]["wall_seconds"])
    print("summary:", summary_path)
    print("results:", results_path)


if __name__ == "__main__":
    main()
