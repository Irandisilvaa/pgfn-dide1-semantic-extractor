from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from dide1.segmenter import segment
from dide1.constants import CATEGORIES
from dide1.router import route

SYSTEM = """Você é o classificador especializado DIDE1/PGFN. Selecione somente IDs de unidades da decisão atual que formem recortes juridicamente acionáveis. Não invente texto. Retorne JSON puro no formato {\"selected\":[{\"unit_ids\":[\"U0001\"],\"category\":\"categoria\"}]}."""


def stable_split(processo: str) -> str:
    h = int(hashlib.sha256(processo.encode("utf-8")).hexdigest()[:8], 16) % 100
    if h < 80: return "train"
    if h < 90: return "val"
    return "test"


def map_gold_to_units(decision: str, gold_items: list[dict]):
    units = segment(decision)
    selected = []
    issues = []
    for g in gold_items:
        text = str(g.get("text", ""))
        cat = str(g.get("category", ""))
        if cat not in CATEGORIES:
            issues.append({"reason": "invalid_category", "text": text, "category": cat})
            continue
        pos = decision.find(text)
        if pos < 0:
            issues.append({"reason": "gold_not_exact_source", "text": text, "category": cat})
            continue
        end = pos + len(text)
        ids = [u.unit_id for u in units if not (u.end <= pos or u.start >= end)]
        if not ids:
            issues.append({"reason": "no_units_for_gold", "text": text, "category": cat})
            continue
        selected.append({"unit_ids": ids, "category": cat})
    return units, selected, issues


def build(gold_jsonl: str, outdir: str):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    handles = {s: (out / f"sft_{s}.jsonl").open("w", encoding="utf-8") for s in ("train","val","test")}
    issues_f = (out / "sft_issues.jsonl").open("w", encoding="utf-8")
    counts = {"train":0,"val":0,"test":0,"issues":0}
    with open(gold_jsonl, encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            obj = json.loads(line)
            decision = obj.get("decision", "")
            processo = str(obj.get("Processo") or obj.get("source_row"))
            units, selected, issues = map_gold_to_units(decision, obj.get("gold", []))
            for issue in issues:
                issues_f.write(json.dumps({"Processo": processo, **issue}, ensure_ascii=False)+"\n")
                counts["issues"] += 1
            if issues:
                # Não treinar exemplo com GOLD não-extrativo: precisa correção humana primeiro.
                continue
            meta = obj.get("metadata", {})
            routing = route({
                "classe": meta.get("classe", ""), "orgao_julgador": meta.get("orgao_julgador", ""),
                "secao_subsecao": meta.get("secao_subsecao", "")
            })
            visible = [u for u in units if not u.rejected]
            user = {
                "contexto": {
                    "classe": meta.get("classe", ""), "orgao_julgador": meta.get("orgao_julgador", ""),
                    "expediente": meta.get("expediente", ""), "assunto": meta.get("assunto", ""),
                    "secao_subsecao": meta.get("secao_subsecao", ""), "routing": routing,
                },
                "unidades": [{"id":u.unit_id,"section":u.section,"text":u.text} for u in visible],
                "categorias_permitidas": CATEGORIES,
            }
            assistant = {"selected": selected}
            row = {"messages":[
                {"role":"system","content":SYSTEM},
                {"role":"user","content":json.dumps(user, ensure_ascii=False)},
                {"role":"assistant","content":json.dumps(assistant, ensure_ascii=False)},
            ], "Processo": processo}
            split = stable_split(processo)
            handles[split].write(json.dumps(row, ensure_ascii=False)+"\n")
            counts[split] += 1
    for h in handles.values(): h.close()
    issues_f.close()
    (out / "manifest.json").write_text(json.dumps(counts, indent=2, ensure_ascii=False), encoding="utf-8")
    return counts


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--gold", required=True)
    p.add_argument("--outdir", required=True)
    a=p.parse_args()
    print(json.dumps(build(a.gold,a.outdir), indent=2, ensure_ascii=False))

if __name__ == "__main__": main()
