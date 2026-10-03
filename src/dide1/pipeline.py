from pathlib import Path
import json
import time
from .input_loader import iter_records
from .text_utils import norm
from .rules_jovaldo import classify as jovaldo_classify
from .segmenter import segment, reconstruct_exact
from .router import route
from .teacher import call_llama
from .workbook import write_review_workbook


def is_execucao_fiscal(record: dict) -> bool:
    return "execucao fiscal" in norm(record.get("classe", ""))


def heuristic_rules_only(units, max_candidates=3):
    verbs = ("intime", "notifique", "cite", "determino", "julgo", "defiro", "indefiro", "condeno", "arquiv", "remeta", "homologo", "rejeito", "concedo", "denego", "expeça", "proceda")
    out = []
    for u in units:
        if u.rejected: continue
        n = norm(u.text)
        if any(v in n for v in verbs):
            if any(v in n for v in ("julgo", "homologo", "rejeito", "concedo", "denego")): cat = "resultado_julgamento"
            elif any(v in n for v in ("intime", "notifique", "cite")): cat = "intimacao_manifestacao"
            elif "arquiv" in n or "remeta" in n: cat = "recurso_proximo_passo"
            else: cat = "ordem_determinacao"
            out.append({"unit_ids": [u.unit_id], "category": cat, "priority": 3, "reason": "rules-only smoke test"})
        if len(out) >= max_candidates: break
    return out


def run(input_xlsx: str, output_dir: str, limit: int | None = None, start_index: int = 0, sheet: str | None = None, teacher_mode: str = "llama", max_candidates: int = 3, include_execucao_fiscal: bool = False):
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    pred_path = outdir / "predictions.jsonl"
    err_path = outdir / "errors.jsonl"
    records_out = []
    candidates_out = []
    errors = []
    scanned = 0
    accepted = 0
    started = time.time()
    for idx, rec in enumerate(iter_records(input_xlsx, sheet=sheet)):
        if idx < start_index:
            continue
        if limit is not None and scanned >= limit:
            break
        scanned += 1
        d = rec.data
        if (not include_execucao_fiscal) and is_execucao_fiscal(d):
            records_out.append({"source_row": rec.source_row, **d, "status_documento": "EXCLUIDO_EXECUCAO_FISCAL", "rule_label": "", "route_key": "", "teacher_recortes_count": 0})
            continue
        decision = d.get("decisao", "")
        units = segment(decision)
        rule = jovaldo_classify(decision, d.get("expediente", ""))
        routing = route(d)
        try:
            if teacher_mode == "llama":
                selected = call_llama(d, units, routing, rule, max_candidates=max_candidates)
            elif teacher_mode == "rules":
                selected = heuristic_rules_only(units, max_candidates=max_candidates)
            else:
                raise ValueError("teacher_mode deve ser 'llama' ou 'rules'")
            for rank, s in enumerate(selected, start=1):
                text = reconstruct_exact(decision, s["unit_ids"], units)
                candidates_out.append({
                    "source_row": rec.source_row,
                    "Processo": d.get("processo", ""),
                    "candidate_rank": rank,
                    "unit_ids": json.dumps(s["unit_ids"], ensure_ascii=False),
                    "candidate_text": text,
                    "teacher_category": s["category"],
                    "teacher_priority": s["priority"],
                    "teacher_reason": s.get("reason", ""),
                    "rule_id": "" if rule is None else rule.rule_id,
                    "rule_label": "" if rule is None else rule.label,
                    "route_key": routing["route_key"],
                    "specialist": routing["specialist"],
                    "status_validacao": "",
                    "texto_ajustado": "",
                    "categoria_ajustada": "",
                    "observacao": "",
                    "revisor": "",
                    "revisado_em": "",
                })
            if not selected:
                candidates_out.append({
                    "source_row": rec.source_row, "Processo": d.get("processo", ""), "candidate_rank": 0,
                    "unit_ids": "[]", "candidate_text": "", "teacher_category": "", "teacher_priority": "", "teacher_reason": "",
                    "rule_id": "" if rule is None else rule.rule_id, "rule_label": "" if rule is None else rule.label,
                    "route_key": routing["route_key"], "specialist": routing["specialist"],
                    "status_validacao": "", "texto_ajustado": "", "categoria_ajustada": "", "observacao": "", "revisor": "", "revisado_em": ""
                })
            accepted += 1
            records_out.append({
                "source_row": rec.source_row, **d,
                "status_documento": "PENDENTE_REVISAO",
                "rule_id": "" if rule is None else rule.rule_id,
                "rule_label": "" if rule is None else rule.label,
                "route_key": routing["route_key"],
                "specialist": routing["specialist"],
                "teacher_recortes_count": len(selected),
                "observacao_documento": "", "revisor_documento": "", "revisado_em": "",
            })
        except Exception as e:
            errors.append({"source_row": rec.source_row, "processo": d.get("processo", ""), "error": repr(e)})
            records_out.append({"source_row": rec.source_row, **d, "status_documento": "ERRO", "rule_label": "" if rule is None else rule.label, "route_key": routing["route_key"], "teacher_recortes_count": 0})

    with pred_path.open("w", encoding="utf-8") as f:
        for x in candidates_out:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with err_path.open("w", encoding="utf-8") as f:
        for x in errors:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    review_path = outdir / "review.xlsx"
    write_review_workbook(review_path, records_out, candidates_out)
    manifest = {
        "input": str(input_xlsx), "sheet": sheet, "teacher_mode": teacher_mode,
        "start_index": start_index, "limit": limit, "scanned": scanned, "processed": accepted,
        "errors": len(errors), "max_candidates": max_candidates,
        "elapsed_seconds": round(time.time() - started, 3),
        "review_workbook": str(review_path),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
