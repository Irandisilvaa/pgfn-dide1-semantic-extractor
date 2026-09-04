from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from time import perf_counter

from src.connectors.google_webapp import GoogleWebAppConnector
from src.semantic.action_extractor import ActionOrientedExtractor
from src.semantic.local_llm import LocalLLMClient
from src.semantic.segmenter import make_units


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        if key:
            os.environ.setdefault(key, value)


def safe_hash(value: str, salt: str) -> str | None:
    value = (value or "").strip()

    if not value:
        return None

    return hashlib.sha256(
        (salt + "|" + value).encode("utf-8")
    ).hexdigest()[:16]


def distributed_blocks(
    total_rows: int,
    sample_size: int,
    blocks: int,
) -> tuple[list[int], int]:
    sample_size = max(1, min(sample_size, total_rows))
    blocks = max(1, min(blocks, sample_size))
    block_size = math.ceil(sample_size / blocks)

    if block_size > 50:
        raise ValueError(
            "block_size excedeu 50. Aumente --blocks."
        )

    max_start = max(0, total_rows - block_size)

    if blocks == 1:
        starts = [0]
    else:
        starts = [
            round(i * max_start / (blocks - 1))
            for i in range(blocks)
        ]

    out: list[int] = []
    seen: set[int] = set()

    for start in starts:
        if start not in seen:
            seen.add(start)
            out.append(start)

    return out, block_size


def write_checkpoint(
    path: Path,
    *,
    offset: int,
    processed: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "next_offset": offset,
                "processed": processed,
                "updated_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def append_preview(
    path: Path,
    *,
    row_number: int,
    process_hash: str | None,
    recortes: list[dict],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "row_number": row_number,
        "process_hash": process_hash,
        "recortes": recortes,
    }

    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "PGFN DIDE1 v1.0 - extração semântica local. "
            "Somente leitura da planilha."
        )
    )

    parser.add_argument(
        "--mode",
        choices=["distributed", "sequential"],
        default="distributed",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=10,
        help=(
            "distributed: tamanho da amostra. "
            "sequential: número máximo; 0 = até o fim."
        ),
    )
    parser.add_argument("--blocks", type=int, default=10)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--start-offset", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--max-unit-chars", type=int, default=1000)
    parser.add_argument("--max-chunk-chars", type=int, default=3000)
    parser.add_argument(
        "--max-candidates-per-chunk",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--max-global-candidates",
        type=int,
        default=30,
    )
    parser.add_argument(
        "--validator-batch-size",
        type=int,
        default=6,
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--base-url",
        default=os.getenv(
            "LOCAL_LLM_BASE_URL",
            "http://127.0.0.1:8081/v1",
        ),
    )
    parser.add_argument("--model", default="")
    parser.add_argument("--show-text", action="store_true")
    parser.add_argument("--show-units", action="store_true")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--summary",
        default="runtime/summary.json",
    )
    parser.add_argument(
        "--preview-jsonl",
        default="",
        help=(
            "Opcional. Salva recortes localmente em JSONL. "
            "Nunca inclua runtime/ no Git."
        ),
    )
    parser.add_argument(
        "--checkpoint",
        default="runtime/checkpoint.json",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Somente em mode=sequential.",
    )
    parser.add_argument(
        "--salt",
        default="pgfn-dide1-v1-local",
    )

    args = parser.parse_args()
    load_env_file(args.env_file)

    if args.resume and args.mode != "sequential":
        raise SystemExit(
            "--resume só pode ser usado com --mode sequential."
        )

    checkpoint_path = Path(args.checkpoint)

    if args.resume and checkpoint_path.exists():
        payload = json.loads(
            checkpoint_path.read_text(encoding="utf-8")
        )
        args.start_offset = int(
            payload.get("next_offset", args.start_offset)
        )
        print(
            "Retomando do offset:",
            args.start_offset,
        )

    connector = GoogleWebAppConnector()

    print("Conectando ao LLM local...")
    llm = LocalLLMClient(
        base_url=args.base_url,
        model=(args.model or None),
    )
    print("LLM local:", llm.health())

    extractor = ActionOrientedExtractor(
        llm,
        max_candidates_per_chunk=(
            args.max_candidates_per_chunk
        ),
        max_chunk_chars=args.max_chunk_chars,
        max_unit_chars=args.max_unit_chars,
        temperature=args.temperature,
        validator_batch_size=args.validator_batch_size,
        max_global_candidates=args.max_global_candidates,
    )

    first = connector.audit_page(
        limit=1,
        offset=0,
        include_decision=False,
    )
    total_rows = int(first["total_rows"])

    print("Base:", total_rows)
    print("Modo:", args.mode)
    print(
        "MODO SOMENTE LEITURA: nenhuma célula será alterada."
    )
    print(
        "LLM permitido somente em localhost/127.0.0.1."
    )

    processed = 0
    errors = 0
    total_recortes = 0
    latencies: list[float] = []
    counts: list[int] = []
    category_counts: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    filter_counts: Counter[str] = Counter()
    validator_rejected_total = 0
    validator_failed_total = 0

    preview_path = (
        Path(args.preview_jsonl)
        if args.preview_jsonl
        else None
    )

    if preview_path and preview_path.exists() and not args.resume:
        preview_path.unlink()

    def process_row(row: dict) -> None:
        nonlocal processed
        nonlocal errors
        nonlocal total_recortes
        nonlocal validator_rejected_total
        nonlocal validator_failed_total

        processed += 1

        row_number = int(row["row_number"])
        processo = str(row.get("processo", "") or "")
        decision = str(row.get("decisao", "") or "")
        process_hash = safe_hash(processo, args.salt)

        print()
        print("=" * 80)
        print(
            f"[{processed}] linha={row_number} "
            f"| process_hash={process_hash} "
            f"| chars={len(decision)}"
        )

        if args.show_units:
            units = make_units(
                decision,
                max_unit_chars=args.max_unit_chars,
            )
            print("--- UNIDADES ---")
            for unit in units:
                print(
                    f"[{unit.id}][{unit.section}] "
                    f"{unit.text}"
                )

        started = perf_counter()

        try:
            result = extractor.extract(
                decision,
                top_k=args.top_k,
            )

            elapsed = perf_counter() - started
            latencies.append(elapsed)

            recortes = result["recortes"]
            counts.append(len(recortes))
            total_recortes += len(recortes)

            filter_counts.update(
                result.get("filter_reasons", {})
            )
            validator_rejected_total += int(
                result.get("validator_rejected", 0)
            )
            validator_failed_total += int(
                result.get("validator_failed", 0)
            )

            print(
                f"unidades={result['n_units']} "
                f"| elegíveis={result['n_eligible_units']} "
                f"| filtradas={result['filtered_units']} "
                f"| chunks={result['n_chunks']} "
                f"| antes_validador="
                f"{result['n_candidates_before_validator']} "
                f"| rejeitados_validador="
                f"{result['validator_rejected']} "
                f"| falhas_validador="
                f"{result['validator_failed']} "
                f"| recortes={len(recortes)} "
                f"| tempo={elapsed:.1f}s"
            )

            if not recortes:
                print("RECORTES: nenhum")

            for i, rec in enumerate(recortes, start=1):
                category_counts[rec["category"]] += 1
                section_counts[rec["section"]] += 1

                print(
                    f"\nRECORTE {i} "
                    f"[{rec['category']}] "
                    f"prioridade={rec['priority']} "
                    f"validacao={rec['validator_relevance']} "
                    f"status={rec['validator_status']} "
                    f"secao={rec['section']} "
                    f"score={rec['heuristic_score']} "
                    f"ids={rec['unit_ids']} "
                    f"expandido={rec['context_expanded']}"
                )

                if args.show_text:
                    print("texto:")
                    print(rec["text"])

            if preview_path is not None:
                append_preview(
                    preview_path,
                    row_number=row_number,
                    process_hash=process_hash,
                    recortes=recortes,
                )

        except Exception as exc:
            errors += 1
            print(
                "ERRO:",
                type(exc).__name__,
                str(exc)[:700],
            )

        finally:
            del decision
            del processo

    if args.mode == "distributed":
        sample_size = max(
            1,
            min(args.sample_size, total_rows),
        )
        starts, block_size = distributed_blocks(
            total_rows,
            sample_size,
            args.blocks,
        )

        print("Amostra:", sample_size)
        print("Offsets:", starts)
        print("Bloco:", block_size)

        for block_no, start in enumerate(starts, start=1):
            remaining = sample_size - processed

            if remaining <= 0:
                break

            limit = min(block_size, remaining)

            print(
                f"\nBaixando bloco "
                f"{block_no}/{len(starts)} "
                f"(offset={start}, limit={limit})..."
            )

            page = connector.audit_page(
                limit=limit,
                offset=start,
                include_decision=True,
            )

            for row in page.get("rows", []):
                if processed >= sample_size:
                    break
                process_row(row)

    else:
        page_size = max(1, min(50, args.page_size))
        max_rows = max(0, args.sample_size)
        offset = max(0, args.start_offset)

        print("Offset inicial:", offset)
        print(
            "Máximo de linhas:",
            "ATÉ O FIM" if max_rows == 0 else max_rows,
        )

        while True:
            if max_rows > 0:
                remaining = max_rows - processed
                if remaining <= 0:
                    break
                limit = min(page_size, remaining)
            else:
                limit = page_size

            page = connector.audit_page(
                limit=limit,
                offset=offset,
                include_decision=True,
            )

            rows = page.get("rows", [])
            if not rows:
                break

            for row in rows:
                process_row(row)

            offset = int(
                page.get(
                    "next_offset",
                    offset + len(rows),
                )
            )

            write_checkpoint(
                checkpoint_path,
                offset=offset,
                processed=processed,
            )

            if not page.get("has_more"):
                break

    summary = {
        "version": "1.0.0",
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "mode": args.mode,
        "processed": processed,
        "errors": errors,
        "docs_with_recortes": sum(
            1 for n in counts if n > 0
        ),
        "docs_without_recortes": sum(
            1 for n in counts if n == 0
        ),
        "total_recortes": total_recortes,
        "average_recortes_per_document": (
            round(sum(counts) / len(counts), 2)
            if counts else 0
        ),
        "average_latency_seconds": (
            round(sum(latencies) / len(latencies), 2)
            if latencies else None
        ),
        "categories": dict(category_counts),
        "sections": dict(section_counts),
        "validator_rejected_total": validator_rejected_total,
        "validator_failed_total": validator_failed_total,
        "deterministic_filter_reasons": dict(filter_counts),
        "security": {
            "spreadsheet_modified": False,
            "full_decision_persisted": False,
            "process_number_persisted": False,
            "llm_must_be_localhost": True,
            "preview_contains_recortes_if_enabled": bool(
                preview_path
            ),
        },
    }

    summary_path = Path(args.summary)
    summary_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 80)
    print("=== PGFN DIDE1 v1.0 CONCLUÍDO ===")
    print("documentos:", processed)
    print("erros:", errors)
    print("recortes:", total_recortes)
    print(
        "média recortes/documento:",
        summary["average_recortes_per_document"],
    )
    print(
        "latência média (s):",
        summary["average_latency_seconds"],
    )
    print(
        "falhas do validador:",
        validator_failed_total,
    )
    print("categorias:", summary["categories"])
    print("seções:", summary["sections"])
    print("resumo:", summary_path)

    if preview_path:
        print(
            "preview LOCAL com recortes:",
            preview_path,
        )

    print(
        "Nenhuma célula da planilha foi alterada."
    )


if __name__ == "__main__":
    main()
