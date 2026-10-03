from pathlib import Path
from openpyxl import load_workbook

from dide1.workbook import write_review_workbook, build_gold, rebuild_review


def _decision(source_row, decision_hash, expediente, cache=False):
    return {
        "source_row": source_row,
        "processo": "P1",
        "classe": "CumSenFaz",
        "origem": "PJE-AL",
        "orgao_julgador": "1ª Vara Federal AL",
        "data": "2026-01-01",
        "expediente": expediente,
        "prazo": 15,
        "assunto": "Tema",
        "secao_subsecao": "AL / Maceió",
        "link": f"https://example/{source_row}",
        "decisao": "DESPACHO\n\nIntime-se a parte em 15 dias.",
        "nucleo": "NTDC",
        "rule_id": "J19",
        "rule_label": "ato ordinatório",
        "route_key": "cumsenfaz|al_maceio|1a_vara",
        "specialist": "global_teacher",
        "teacher_status": "OK",
        "teacher_attempts": 1,
        "teacher_response_mode": "json_schema",
        "decision_sha256": decision_hash,
        "cache_hit": cache,
    }


def _candidate(source_row, decision_hash):
    return {
        "source_row": source_row,
        "Processo": "P1",
        "candidate_rank": 1,
        "candidate_text": "Intime-se a parte em 15 dias.",
        "teacher_category": "intimacao_manifestacao",
        "teacher_priority": 1,
        "teacher_reason": "ordem clara",
        "decision_sha256": decision_hash,
    }


def test_v43_review_is_compact_and_hides_technical(tmp_path: Path):
    path = tmp_path / "review.xlsx"
    write_review_workbook(path, [_decision(2, "abc", "Intimação (1)"), _decision(3, "abc", "Intimação (2)", True)], [_candidate(2, "abc"), _candidate(3, "abc")])
    wb = load_workbook(path)
    assert wb.sheetnames[0] == "revisao"
    assert wb["dados_tecnicos"].sheet_state == "hidden"
    assert wb["candidatos_tecnicos"].sheet_state == "hidden"
    ws = wb["revisao"]
    headers = {c.value: c.column for c in ws[1]}
    assert "Recorte 1" in headers
    assert "Validação 1" in headers
    assert "candidate_1_reason" not in headers
    assert ws.cell(2, headers["Validação 1"]).value == "PENDENTE"
    assert ws.column_dimensions["A"].hidden is True


def test_v43_build_gold_uses_edited_visible_values(tmp_path: Path):
    review = tmp_path / "review.xlsx"
    out = tmp_path / "gold.jsonl"
    write_review_workbook(review, [_decision(2, "abc", "Intimação (1)")], [_candidate(2, "abc")])
    wb = load_workbook(review)
    ws = wb["revisao"]
    h = {c.value: c.column for c in ws[1]}
    ws.cell(2, h["Recorte 1"]).value = "Intime-se a parte em 10 dias."
    ws.cell(2, h["Categoria 1"]).value = "intimacao_manifestacao"
    ws.cell(2, h["Validação 1"]).value = "AJUSTADO"
    ws.cell(2, h["Status da decisão"]).value = "VALIDADO_COMPLETO"
    wb.save(review)
    result = build_gold(str(review), str(out))
    assert result["validated_documents"] == 1
    assert result["blocked_documents"] == 0
    text = out.read_text(encoding="utf-8")
    assert "10 dias" in text
    assert '"validation": "AJUSTADO"' in text


def test_v43_blocks_incomplete_validated_doc(tmp_path: Path):
    review = tmp_path / "review.xlsx"
    out = tmp_path / "gold.jsonl"
    write_review_workbook(review, [_decision(2, "abc", "Intimação (1)")], [_candidate(2, "abc")])
    wb = load_workbook(review)
    ws = wb["revisao"]
    h = {c.value: c.column for c in ws[1]}
    ws.cell(2, h["Status da decisão"]).value = "VALIDADO_COMPLETO"
    wb.save(review)
    result = build_gold(str(review), str(out))
    assert result["validated_documents"] == 0
    assert result["blocked_documents"] == 1
    issues = (tmp_path / "gold_build_issues.csv").read_text(encoding="utf-8-sig")
    assert "ainda não revisado" in issues


def test_rebuild_review_does_not_require_qwen(tmp_path: Path):
    old = tmp_path / "old.xlsx"
    new = tmp_path / "new.xlsx"
    # Simula v4.3 para garantir caminho de rebuild; a função também aceita v4.2.
    write_review_workbook(old, [_decision(2, "abc", "Intimação (1)")], [_candidate(2, "abc")])
    result = rebuild_review(str(old), str(new))
    assert result["qwen_rerun"] is False
    assert new.exists()
