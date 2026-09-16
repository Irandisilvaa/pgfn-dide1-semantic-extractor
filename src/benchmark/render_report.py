from __future__ import annotations
import argparse, json
from pathlib import Path


def pct(x):
    return f"{100*x:.1f}%"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("summary")
    p.add_argument("--output", default="")
    args = p.parse_args()

    s = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    md = f"""# Relatório de benchmark — {s['label']}

## Ambiente experimental

- Benchmark: DIDE1 sintético v{s['benchmark_version']}
- Documentos: {s['documents']}
- Dados reais PGFN: **não**
- API de planilha: **não**
- API externa de LLM: **não**

## Métricas

| Métrica | Resultado |
|---|---:|
| Exact Precision | {pct(s['exact_precision'])} |
| Exact Recall | {pct(s['exact_recall'])} |
| Exact F1 | {pct(s['exact_f1'])} |
| Hit@1 | {pct(s['rank1_hit_rate'])} |
| Documentos com ao menos 1 GOLD | {pct(s['document_any_gold_rate'])} |
| Documentos com todos os GOLDs | {pct(s['document_all_gold_rate'])} |
| Categoria nos matches exatos | {pct(s['category_accuracy_on_exact'])} |
| Erros de inferência | {s['errors']} |
| Duplicatas finais | {s['duplicate_outputs']} |
| Wall time | {s['latency']['wall_seconds']:.1f} s |

## Leitura

O resultado mede extração literal de recortes contra um gabarito conhecido.
Não mede ainda desempenho em decisões reais da PGFN. A passagem para piloto
real deve ocorrer somente em ambiente institucional autorizado e com revisão
humana dos recortes.
"""
    output = Path(args.output) if args.output else Path(args.summary).with_suffix(".md")
    output.write_text(md, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
