import argparse
import json
from .pipeline import run
from .inspect_data import inspect
from .workbook import build_gold


def main():
    p = argparse.ArgumentParser(prog="dide1")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("inspect", help="Valida e resume a planilha")
    a.add_argument("--input", required=True)
    a.add_argument("--sheet")
    a.add_argument("--limit", type=int)

    r = sub.add_parser("run", help="Executa pipeline de extração/teacher")
    r.add_argument("--input", required=True)
    r.add_argument("--output", required=True)
    r.add_argument("--sheet")
    r.add_argument("--limit", type=int, help="Limite de linhas/expedientes escaneados")
    r.add_argument("--unique-limit", type=int, help="Limite de decisões únicas por SHA-256; ideal para lotes de revisão")
    r.add_argument("--start-index", type=int, default=0)
    r.add_argument("--teacher", choices=["llama", "rules"], default="llama")
    r.add_argument("--max-candidates", type=int, default=3)
    r.add_argument("--include-execucao-fiscal", action="store_true")

    g = sub.add_parser("build-gold", help="Converte workbook humano revisado em GOLD JSONL")
    g.add_argument("--review", required=True)
    g.add_argument("--output", required=True)

    args = p.parse_args()
    if args.cmd == "inspect":
        result = inspect(args.input, args.sheet, args.limit)
    elif args.cmd == "run":
        result = run(args.input, args.output, args.limit, args.start_index, args.sheet, args.teacher, args.max_candidates, args.include_execucao_fiscal, args.unique_limit)
    else:
        result = build_gold(args.review, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
