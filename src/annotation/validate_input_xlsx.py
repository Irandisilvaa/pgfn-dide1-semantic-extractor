from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from src.annotation.local_xlsx import EXPECTED_COLUMNS, inspect_workbook, iter_source_rows


def main() -> None:
    p = argparse.ArgumentParser(description="Valida a planilha XLSX local antes de chamar o teacher.")
    p.add_argument("--input-xlsx", required=True)
    p.add_argument("--sheet", default="input")
    args = p.parse_args()

    info = inspect_workbook(args.input_xlsx, args.sheet)
    docs = 0
    empty_decisions = 0
    empty_processes = 0
    processes = Counter()

    for row in iter_source_rows(info.path, sheet=info.sheet):
        docs += 1
        decision = str(row.get("Decisão") or "").strip()
        process = str(row.get("Processo") or "").strip()
        if not decision:
            empty_decisions += 1
        if not process:
            empty_processes += 1
        else:
            processes[process] += 1

    print("=== DIDE1 / VALIDAÇÃO DA PLANILHA LOCAL ===")
    print("arquivo:", Path(args.input_xlsx).resolve())
    print("aba:", info.sheet)
    print("linhas de dados:", docs)
    print("decisões vazias:", empty_decisions)
    print("processos vazios:", empty_processes)
    print("processos únicos:", len(processes))
    print("colunas reconhecidas:")
    for name in EXPECTED_COLUMNS:
        state = "OK" if name in info.canonical_to_index else "AUSENTE/OPCIONAL"
        print(f"  - {name}: {state}")
    print("status: OK")


if __name__ == "__main__":
    main()
