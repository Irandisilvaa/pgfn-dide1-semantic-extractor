from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import re
import time

from .input_loader import iter_records
from .text_utils import norm
from .rules_jovaldo import classify as jovaldo_classify
from .segmenter import segment, reconstruct_exact
from .router import route
from .teacher import call_llama
from .workbook import write_review_workbook


OPERATIVE_START = re.compile(
    r"^(?:\d+[.)]\s*)?(?:(?:diante|ante) do exposto[,;:]?\s*|isto posto[,;:]?\s*|por tais fundamentos[,;:]?\s*)?"
    r"(?:determino|defiro|indefiro|julgo|homologo|declaro|rejeito|condeno|extingo|acolho|"
    r"intime-se|intimem-se|notifique-se|cite-se|arquive-se|arquivem-se|remeta-se|remetam-se|"
    r"expeca-se|proceda|procedam|aguarde-se|mantenha-se|libere-se|suspenda-se|"
    r"ficam? as partes intimadas|vistas? (?:a|as|ao))\b",
    re.I,
)


def is_execucao_fiscal(record: dict) -> bool:
    return "execucao fiscal" in norm(record.get("classe", ""))


def _decision_hash(decision: str) -> str:
    return hashlib.sha256((decision or "").encode("utf-8", errors="replace")).hexdigest()


def _category_from_text(text: str) -> str:
    n = norm(text)
    if any(v in n for v in ("julgo", "homologo", "declaro", "rejeito", "extingo", "acolho")):
        return "resultado_julgamento"
    if "honorario" in n or "custas" in n:
        return "honorarios_custas"
    if "prescri" in n or "decaden" in n:
        return "prescricao_decadencia"
    if any(v in n for v in ("intim", "notifi", "cit", "vista")):
        return "intimacao_manifestacao"
    if "arquiv" in n or "remeta" in n or "conclus" in n:
        return "recurso_proximo_passo"
    if "requisit" in n or "pagamento" in n or "precatorio" in n or "rpv" in n:
        return "restituicao_pagamento"
    return "ordem_determinacao"


def heuristic_rules_only(units, max_candidates=3):
    out = []
    for u in units:
        if u.rejected:
            continue
        n = norm(u.text)
        if OPERATIVE_START.search(n):
            out.append({
                "unit_ids": [u.unit_id],
                "category": _category_from_text(u.text),
                "priority": 3,
                "reason": "deterministic rules fallback",
            })
        if len(out) >= max_candidates:
            break
    return out


def _fallback_score(text: str, label: str) -> int:
    """Fallback propositalmente conservador: prefere perder um recorte a inventar ação em narrativa."""
    n = norm(text)
    lead = n[:180]
    score = 0

    if OPERATIVE_START.search(n):
        score += 4

    if "requisitorio" in label and "requisit" in n and any(x in n for x in ("intim", "manifest", "pagamento", "exped")):
        score += 8
    if "contrarrazo" in label and "contrarrazo" in n and any(x in n for x in ("intim", "manifest")):
        score += 8
    if "citacao" in label and any(x in lead for x in ("cite-se", "citacao", "cita", "intim")):
        score += 8
    if "ato ordinatorio" in label and any(x in lead for x in ("intim", "vista", "prazo", "arquiv")):
        score += 6
    if "sobrestamento" in label and "sobrest" in lead:
        score += 8
    if "prescricao" in label and "prescri" in lead and any(x in lead for x in ("declaro", "julgo", "reconhe")):
        score += 8
    if "sentenca" in label and any(x in lead for x in ("julgo", "homologo", "declaro", "extingo", "rejeito", "acolho", "condeno")):
        score += 8

    # Evita narrativa típica que apareceu no piloto de 100 decisões.
    if lead.startswith(("sustenta ", "alega ", "a parte sustenta ", "a impetrante sustenta ", "a autora sustenta ")):
        return 0
    if "foi devidamente notificada" in lead or "culminou no ato declaratorio" in lead:
        score = max(0, score - 6)
    return score


def _rule_fallback(units, rule, max_candidates=3):
    """Fallback conservador quando o teacher falha; nunca força narrativa apenas por haver regra Jovaldo."""
    label = "" if rule is None else norm(rule.label)
    preferred = []
    for u in units:
        if u.rejected:
            continue
        score = _fallback_score(u.text, label)
        if score > 0:
            preferred.append((score, u.start, u))

    preferred.sort(key=lambda x: (-x[0], x[1]))
    out = []
    for _, _, u in preferred[:max_candidates]:
        out.append({
            "unit_ids": [u.unit_id],
            "category": _category_from_text(u.text),
            "priority": 2,
            "reason": "rule fallback conservador" if rule is None else f"rule fallback: {rule.rule_id}/{rule.label}",
        })
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


def run(
    input_xlsx: str,
    output_dir: str,
    limit: int | None = None,
    start_index: int = 0,
    sheet: str | None = None,
    teacher_mode: str = "llama",
    max_candidates: int = 3,
    include_execucao_fiscal: bool = False,
    unique_limit: int | None = None,
):
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    pred_path = outdir / "predictions.jsonl"
    err_path = outdir / "errors.jsonl"
    records_out = []
    candidates_out = []
    errors = []
    cache: dict[str, dict] = {}
    unique_seen: set[str] = set()
    scanned = 0
    accepted = 0
    cache_hits = 0
    unique_inferences = 0
    retries_ok = 0
    rule_fallbacks = 0
    rule_fallback_empty = 0
    empty_valid = 0
    skipped_empty_decisions = 0
    started = time.time()

    for idx, rec in enumerate(iter_records(input_xlsx, sheet=sheet)):
        if idx < start_index:
            continue
        if limit is not None and scanned >= limit:
            break
        if unique_limit is not None and len(unique_seen) >= unique_limit:
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
        if not decision.strip():
            skipped_empty_decisions += 1
            records_out.append({
                "source_row": rec.source_row, **d,
                "status_documento": "SEM_DECISAO",
                "rule_label": "", "route_key": "", "teacher_recortes_count": 0,
                "teacher_status": "", "teacher_attempts": 0, "teacher_response_mode": "",
                "decision_sha256": "", "cache_hit": False,
            })
            continue

        decision_sha256 = _decision_hash(decision)
        unique_seen.add(decision_sha256)
        units = segment(decision)
        rule = jovaldo_classify(decision, d.get("expediente", ""))
        routing = route(d)
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
                    teacher_attempts = int(os.getenv("DIDE1_LLM_RETRIES", "1")) + 1
                    teacher_response_mode = "fallback"
                    if selected:
                        teacher_status = "RULE_FALLBACK"
                        rule_fallbacks += 1
                    else:
                        teacher_status = "RULE_FALLBACK_EMPTY"
                        rule_fallback_empty += 1
                    errors.append({
                        "source_row": rec.source_row,
                        "processo": d.get("processo", ""),
                        "severity": "RECOVERED",
                        "teacher_status": teacher_status,
                        "error": repr(teacher_exc),
                    })
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
        "version": "4.2.0-review-metrics",
        "input": str(input_xlsx), "sheet": sheet, "teacher_mode": teacher_mode,
        "start_index": start_index, "limit": limit, "unique_limit": unique_limit,
        "scanned": scanned, "processed": accepted,
        "unique_decisions": len(unique_seen),
        "errors": fatal_errors, "recovered_errors": recovered_errors,
        "max_candidates": max_candidates,
        "unique_inferences": unique_inferences,
        "cache_hits": cache_hits,
        "teacher_retries_ok": retries_ok,
        "rule_fallbacks": rule_fallbacks,
        "rule_fallback_empty": rule_fallback_empty,
        "empty_valid": empty_valid,
        "skipped_empty_decisions": skipped_empty_decisions,
        "elapsed_seconds": round(time.time() - started, 3),
        "review_workbook": str(review_path),
        "review_sheet": "revisao_consolidada",
        "metrics_sheet": "metricas",
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
