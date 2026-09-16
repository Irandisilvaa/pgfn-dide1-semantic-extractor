from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path


ALLOWED = {
    "resultado_julgamento","ordem_determinacao","intimacao_manifestacao",
    "tutela","obrigacao","prazo_cumprimento","restituicao_pagamento",
    "honorarios_custas","recurso_proximo_passo","prescricao_decadencia",
    "reconhecimento_concordancia","outro_acionavel",
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True)
    args = p.parse_args()

    rows = []
    for line in Path(args.dataset).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))

    ids = set()
    diffs = Counter()
    scenarios = Counter()

    for row in rows:
        rid = row["id_sintetico"]
        if rid in ids:
            raise SystemExit(f"ID duplicado: {rid}")
        ids.add(rid)

        if not row.get("synthetic_only", False):
            raise SystemExit(f"{rid}: synthetic_only não confirmado.")

        if "DECISÃO SINTÉTICA PARA BENCHMARK" not in row["decisao"]:
            raise SystemExit(f"{rid}: marcador sintético ausente.")

        for gold in row["gold"]:
            if gold["text"] not in row["decisao"]:
                raise SystemExit(f"{rid}: GOLD não é literal.")
            if gold["category"] not in ALLOWED:
                raise SystemExit(f"{rid}: categoria GOLD inválida.")

        diffs[row["dificuldade"]] += 1
        scenarios[row["cenario"]] += 1

    print("dataset:", args.dataset)
    print("registros:", len(rows))
    print("dificuldades:", dict(diffs))
    print("cenários distintos:", len(scenarios))
    print("dados reais PGFN: NÃO")
    print("status: OK")


if __name__ == "__main__":
    main()
