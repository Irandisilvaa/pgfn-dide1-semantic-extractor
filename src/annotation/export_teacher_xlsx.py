from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter
import hashlib
import json
from typing import Any

from src.annotation.local_xlsx import inspect_workbook, iter_source_rows
from src.annotation.workbook import load_or_create_review_workbook, utc_now
from src.semantic.action_extractor import ActionOrientedExtractor
from src.semantic.local_llm import LocalLLMClient


PIPELINE_VERSION = "3.1.0-local-xlsx-teacher-gold-slm"


def process_hash(processo: str, salt: str = "dide1-review") -> str:
    return hashlib.sha256((salt + "|" + (processo or "")).encode("utf-8")).hexdigest()[:16]


def save_checkpoint(
    path: Path,
    *,
    next_excel_row: int,
    processed: int,
    errors: int,
    output: Path,
    input_xlsx: Path,
    sheet: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "next_excel_row": next_excel_row,
        "processed": processed,
        "errors": errors,
        "output": str(output),
        "input_xlsx": str(input_xlsx),
        "sheet": sheet,
        "saved_at_utc": utc_now(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _row_value(row: dict[str, Any], key: str) -> Any:
    value = row.get(key, "")
    return "" if value is None else value


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Planilha XLSX LOCAL -> teacher Qwen local -> XLSX de revisão humana. "
            "Não usa API de planilha e não altera o arquivo fonte."
        )
    )
    p.add_argument("--input-xlsx", required=True)
    p.add_argument("--sheet", default="input")
    p.add_argument("--limit", type=int, default=100, help="0 = até o fim.")
    p.add_argument("--start-excel-row", type=int, default=2)
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--output", default="runtime/private_annotations/teacher_review.xlsx")
    p.add_argument("--checkpoint", default="runtime/private_annotations/teacher_checkpoint.json")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--base-url", default="http://127.0.0.1:8081/v1")
    p.add_argument("--model", default="")
    p.add_argument("--save-every", type=int, default=25)
    args = p.parse_args()

    source = Path(args.input_xlsx)
    info = inspect_workbook(source, args.sheet)
    output = Path(args.output)
    checkpoint = Path(args.checkpoint)

    if source.resolve() == output.resolve():
        raise SystemExit("Segurança: entrada e saída não podem ser o mesmo arquivo.")

    processed = 0
    errors = 0
    start_excel_row = max(2, args.start_excel_row)

    if args.resume and checkpoint.exists():
        cp = json.loads(checkpoint.read_text(encoding="utf-8"))
        cp_input = Path(cp.get("input_xlsx", source))
        cp_sheet = str(cp.get("sheet", args.sheet))
        if cp_input.resolve() != source.resolve() or cp_sheet != args.sheet:
            raise SystemExit("Checkpoint pertence a outra planilha/aba. Não é seguro retomar.")
        start_excel_row = int(cp.get("next_excel_row", start_excel_row))
        processed = int(cp.get("processed", 0))
        errors = int(cp.get("errors", 0))

    llm = LocalLLMClient(base_url=args.base_url, model=(args.model or None))
    teacher_model = llm.health()["model"]
    extractor = ActionOrientedExtractor(llm)

    manifest = {
        "pipeline_version": PIPELINE_VERSION,
        "teacher_model": teacher_model,
        "generated_at_utc": utc_now(),
        "source": "XLSX local / read-only",
        "source_file_name": source.name,
        "source_sheet": args.sheet,
        "source_modified": False,
        "spreadsheet_api_used": False,
        "external_llm_api_used": False,
        "llm_endpoint": args.base_url,
        "tags_used_for_inference": False,
        "ind_used_for_inference": False,
        "note": "Saída do teacher NÃO é GOLD antes da validação humana.",
    }
    wb = load_or_create_review_workbook(output, manifest, args.resume)
    ws_dec = wb["decisoes"]
    ws_can = wb["candidatos"]

    remaining_limit = 0 if args.limit == 0 else max(0, args.limit - processed)

    print("=== DIDE1 TEACHER LOCAL XLSX -> REVIEW XLSX ===")
    print("Teacher local:", teacher_model)
    print("Entrada local:", source)
    print("Aba:", info.sheet)
    print("Primeira linha Excel:", start_excel_row)
    print("Limite total:", "ATÉ O FIM" if args.limit == 0 else args.limit)
    print("API de planilha: NÃO")
    print("LLM externo: NÃO")
    print("tags e Ind. entram no prompt: NÃO")

    next_excel_row = start_excel_row
    iterator_limit = remaining_limit if args.limit else 0

    for row in iter_source_rows(
        source,
        sheet=args.sheet,
        start_excel_row=start_excel_row,
        limit=iterator_limit,
    ):
        excel_row = int(row["source_row"])
        next_excel_row = excel_row + 1
        decision = str(_row_value(row, "Decisão")).strip()
        processo = str(_row_value(row, "Processo")).strip()
        started = perf_counter()

        try:
            result = extractor.extract(decision, top_k=args.top_k) if decision else {"recortes": []}
            recortes = result.get("recortes", [])
            generated = utc_now()

            ws_dec.append([
                excel_row,
                _row_value(row, "Extração"),
                processo,
                _row_value(row, "Classe judicial"),
                _row_value(row, "Órgão julgador"),
                _row_value(row, "Polo Ativo"),
                _row_value(row, "Polo Passivo"),
                decision,
                _row_value(row, "Matéria SAJ"),
                _row_value(row, "Ind."),
                _row_value(row, "tags"),
                teacher_model,
                PIPELINE_VERSION,
                generated,
                len(recortes),
                "", "", "", "",
            ])

            if recortes:
                for rec in recortes:
                    ws_can.append([
                        excel_row,
                        processo,
                        rec.get("rank", 0),
                        json.dumps(rec.get("unit_ids", []), ensure_ascii=False),
                        rec.get("section", ""),
                        rec.get("text", ""),
                        rec.get("category", ""),
                        rec.get("priority", ""),
                        rec.get("heuristic_score", ""),
                        "", "", "", "", "", "",
                    ])
            else:
                ws_can.append([
                    excel_row, processo, 0, "[]", "", "", "", "", "",
                    "", "", "", "", "", "",
                ])

            processed += 1
            elapsed = perf_counter() - started
            print(
                f"[{processed}] linha_excel={excel_row} hash={process_hash(processo)} "
                f"recortes={len(recortes)} tempo={elapsed:.1f}s"
            )
        except Exception as exc:
            errors += 1
            print(f"ERRO linha_excel={excel_row} {type(exc).__name__}: {str(exc)[:240]}")

        if (processed + errors) % max(1, args.save_every) == 0:
            wb.save(output)
            save_checkpoint(
                checkpoint,
                next_excel_row=next_excel_row,
                processed=processed,
                errors=errors,
                output=output,
                input_xlsx=source,
                sheet=args.sheet,
            )

    wb.save(output)
    save_checkpoint(
        checkpoint,
        next_excel_row=next_excel_row,
        processed=processed,
        errors=errors,
        output=output,
        input_xlsx=source,
        sheet=args.sheet,
    )

    print("=== CONCLUÍDO ===")
    print("documentos processados:", processed)
    print("erros:", errors)
    print("xlsx revisão:", output)
    print("checkpoint:", checkpoint)
    print("IMPORTANTE: candidatos do teacher ainda NÃO são GOLD.")


if __name__ == "__main__":
    main()
