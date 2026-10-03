from __future__ import annotations

from pathlib import Path
import hashlib
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


def _decision_hash(decision: str) -> str:
    # Hash do texto original: decisões idênticas reutilizam exatamente a mesma inferência.
    return hashlib.sha256((decision or "").encode("utf-8", errors="replace")).hexdigest()


def heuristic_rules_only(units, max_candidates=3):
    stems = (
        "intim", "notifi", "cit", "determino", "julgo", "defiro", "indefiro",
        "condeno", "arquiv", "remeta", "homologo", "rejeito", "concedo", "denego",
        "expe", "proceda", "aguarde", "manif", "requisit", "sobrest",
    )
    out = []
    for u in units:
        if u.rejected:
            continue
        n = norm(u.text)
        if any(v in n for v in stems):
            if any(v in n for v in ("julgo", "homologo", "rejeito", "concedo", "denego")):
                cat = "resultado_julgamento"
            elif any(v in n for v in ("intim", "notifi", "cit", "manif")):
                cat = "intimacao_manifestacao"
            elif "arquiv" in n or "remeta" in n:
                cat = "recurso_proximo_passo"
            elif "requisit" in n or "pagamento" in n or "precatorio" in n:
                cat = "restituicao_pagamento"
            else:
                cat = "ordem_determinacao"
            out.append({"unit_ids": [u.unit_id], "category": cat, "priority": 3, "reason": "deterministic rules fallback"})
        if len(out) >= max_candidates:
            break
    return out


def _rule_fallback(units, rule, max_candidates=3):
    """Fallback conservador quando o teacher falha: usa regra conhecida + unidades acionáveis."""
    if rule is None:
        return heuristic_rules_only(units, max_candidates=max_candidates)

    label = norm(rule.label)
    preferred = []
    for u in units:
        if u.rejected:
            continue
        n = norm(u.text)
        score = 0
        if "requisitorio" in label and "requisit" in n:
            score += 6
        if "contrarrazo" in label and "contrarrazo" in n:
            score += 6
        if "citacao" in label and ("cit" in n or "cita" in n):
            score += 6
        if "ato ordinatorio" in label and any(x in n for x in ("intim", "manif", "prazo", "arquiv")):
            score += 4
        if "sobrestamento" in label and "sobrest" in n:
            score += 6
        if "prescricao" in label and "prescri" in n:
            score += 5
        if any(x in n for x in ("intim", "determino", "defiro", "indefiro", "julgo", "homologo", "arquiv", "remeta", "expe", "proceda", "aguarde")):
            score += 2
        if score:
            preferred.append((score, u))

    preferred.sort(key=lambda x: (-x[0], x[1].start))
    chosen = preferred[:max_candidates]
    if not chosen:
        return heuristic_rules_only(units, max_candidates=max_candidates)

    out = []
    for _, u in chosen:
        n = norm(u.text)
        if "requisit" in n or "pagamento" in n or "precatorio" in n:
            cat = "restituicao_pagamento"
        elif any(x in n for x in ("intim", "manif", "cit")):
            cat = "intimacao_manifestacao"
        elif "arquiv" in n or "remeta" in n:
            cat = "recurso_proximo_passo"
        else:
            cat = "ordem_determinacao"
        out.append({"unit_ids": [u.unit_id], "category": cat, "priority": 2, "reason": f"rule fallback: {rule.rule_id}/{rule.label}"})
    return out


def _candidate_row(rec, d, rank, s, decision, units, rule, routing, teacher_status, teacher_attempts, teacher_response_mode, decision_sha256, cache_hit):
    text = reconstruct_exact(decision, s["unit_ids"], units)
    return {
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
        "teacher_status": teacher_status,
        "teacher_attempts": teacher_attempts,
        "teacher_response_mode": teacher_response_mode,
        "decision_sha256": decision_sha256,
        "cache_hit": cache_hit,
        "status_validacao": "",
        "texto_ajustado": "",
        "categoria_ajustada": "",
        "observacao": "",
        "revisor": "",
        "revisado_em": "",
    }


def run(input_xlsx: str, output_dir: str, limit: int | None = None, start_index: int = 0, sheet: str | None = None, teacher_mode: str = "llama", max_candidates: int = 3, include_execucao_fiscal: bool = False):
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    pred_path = outdir / "predictions.jsonl"
    err_path = outdir / "errors.jsonl"
    records_out = []
    candidates_out = []
    errors = []
    cache: dict[str, dict] = {}
    scanned = 0
    accepted = 0
    cache_hits = 0
    unique_inferences = 0
    retries_ok = 0
    rule_fallbacks = 0
    empty_valid = 0
    started = time.time()

    for idx, rec in enumerate(iter_records(input_xlsx, sheet=sheet)):
        if idx < start_index:
            continue
        if limit is not None and scanned >= limit:
            break
        scanned += 1
        d = rec.data

        if (not include_execucao_fiscal) and is_execucao_fiscal(d):
            records_out.append({
                "source_row": rec.source_row, **d,
                "status_documento": "EXCLUIDO_EXECUCAO_FISCAL",
                "rule_label": "", "route_key": "", "teacher_recortes_count": 0,
                "teacher_status": "", "teacher_attempts": 0, "teacher_response_mode": "",
                "decision_sha256": "", "cache_hit": False,
            })
            continue

        decision = d.get("decisao", "") or ""
        units = segment(decision)
        rule = jovaldo_classify(decision, d.get("expediente", ""))
        routing = route(d)
        decision_sha256 = _decision_hash(decision)
        cache_hit = False

        try:
            if teacher_mode == "llama" and decision_sha256 in cache:
                cached = cache[decision_sha256]
                selected = cached["selected"]
                teacher_status = cached["teacher_status"]
                teacher_attempts = cached["teacher_attempts"]
                teacher_response_mode = cached["teacher_response_mode"]
                cache_hit = True
                cache_hits += 1
            elif teacher_mode == "llama":
                unique_inferences += 1
                try:
                    result = call_llama(d, units, routing, rule, max_candidates=max_candidates)
                    selected = result.selected
                    teacher_status = result.status
                    teacher_attempts = result.attempts
                    teacher_response_mode = result.response_mode
                    if teacher_status == "RETRY_OK":
                        retries_ok += 1
                    if teacher_status == "EMPTY_VALID":
                        empty_valid += 1
                except Exception as teacher_exc:
                    selected = _rule_fallback(units, rule, max_candidates=max_candidates)
                    if selected:
                        teacher_status = "RULE_FALLBACK"
                        teacher_attempts = int(__import__("os").getenv("DIDE1_LLM_RETRIES", "1")) + 1
                        teacher_response_mode = "fallback"
                        rule_fallbacks += 1
                        errors.append({
                            "source_row": rec.source_row,
                            "processo": d.get("processo", ""),
                            "severity": "RECOVERED",
                            "teacher_status": teacher_status,
                            "error": repr(teacher_exc),
                        })
                    else:
                        raise teacher_exc
                cache[decision_sha256] = {
                    "selected": selected,
                    "teacher_status": teacher_status,
                    "teacher_attempts": teacher_attempts,
                    "teacher_response_mode": teacher_response_mode,
                }
            elif teacher_mode == "rules":
                selected = heuristic_rules_only(units, max_candidates=max_candidates)
                teacher_status = "EMPTY_VALID" if not selected else "OK"
                teacher_attempts = 0
                teacher_response_mode = "rules"
            else:
                raise ValueError("teacher_mode deve ser 'llama' ou 'rules'")

            for rank, s in enumerate(selected, start=1):
                candidates_out.append(_candidate_row(
                    rec, d, rank, s, decision, units, rule, routing,
                    teacher_status, teacher_attempts, teacher_response_mode,
                    decision_sha256, cache_hit,
                ))

            if not selected:
                candidates_out.append({
                    "source_row": rec.source_row, "Processo": d.get("processo", ""), "candidate_rank": 0,
                    "unit_ids": "[]", "candidate_text": "", "teacher_category": "", "teacher_priority": "", "teacher_reason": "",
                    "rule_id": "" if rule is None else rule.rule_id, "rule_label": "" if rule is None else rule.label,
                    "route_key": routing["route_key"], "specialist": routing["specialist"],
                    "teacher_status": teacher_status, "teacher_attempts": teacher_attempts,
                    "teacher_response_mode": teacher_response_mode, "decision_sha256": decision_sha256,
                    "cache_hit": cache_hit,
                    "status_validacao": "", "texto_ajustado": "", "categoria_ajustada": "", "observacao": "", "revisor": "", "revisado_em": "",
                })

            accepted += 1
            records_out.append({
                "source_row": rec.source_row, **d,
                "status_documento": "PENDENTE_REVISAO",
                "rule_id": "" if rule is None else rule.rule_id,
                "rule_label": "" if rule is None else rule.label,
                "route_key": routing["route_key"],
                "specialist": routing["specialist"],
                "teacher_status": teacher_status,
                "teacher_attempts": teacher_attempts,
                "teacher_response_mode": teacher_response_mode,
                "decision_sha256": decision_sha256,
                "cache_hit": cache_hit,
                "teacher_recortes_count": len(selected),
                "observacao_documento": "", "revisor_documento": "", "revisado_em": "",
            })
        except Exception as e:
            errors.append({
                "source_row": rec.source_row, "processo": d.get("processo", ""),
                "severity": "FATAL", "teacher_status": "ERROR", "error": repr(e),
            })
            records_out.append({
                "source_row": rec.source_row, **d,
                "status_documento": "ERRO",
                "rule_id": "" if rule is None else rule.rule_id,
                "rule_label": "" if rule is None else rule.label,
                "route_key": routing["route_key"], "specialist": routing["specialist"],
                "teacher_status": "ERROR", "teacher_attempts": 0, "teacher_response_mode": "",
                "decision_sha256": decision_sha256, "cache_hit": cache_hit,
                "teacher_recortes_count": 0,
            })

    with pred_path.open("w", encoding="utf-8") as f:
        for x in candidates_out:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with err_path.open("w", encoding="utf-8") as f:
        for x in errors:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    review_path = outdir / "review.xlsx"
    write_review_workbook(review_path, records_out, candidates_out)
    fatal_errors = sum(1 for e in errors if e.get("severity") == "FATAL")
    recovered_errors = sum(1 for e in errors if e.get("severity") == "RECOVERED")
    manifest = {
        "version": "4.1.0-router-resilient",
        "input": str(input_xlsx), "sheet": sheet, "teacher_mode": teacher_mode,
        "start_index": start_index, "limit": limit, "scanned": scanned, "processed": accepted,
        "errors": fatal_errors, "recovered_errors": recovered_errors,
        "max_candidates": max_candidates,
        "unique_inferences": unique_inferences,
        "cache_hits": cache_hits,
        "teacher_retries_ok": retries_ok,
        "rule_fallbacks": rule_fallbacks,
        "empty_valid": empty_valid,
        "elapsed_seconds": round(time.time() - started, 3),
        "review_workbook": str(review_path),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
