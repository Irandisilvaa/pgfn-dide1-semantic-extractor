from pathlib import Path
from openpyxl import Workbook, load_workbook

from dide1.pipeline import run
from dide1.teacher import TeacherResult


def _make_xlsx(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Processo", "Classe", "Origem", "Órgão Julgador", "Expediente", "Assunto", "Seção/Subseção", "Decisão Judicial", "Núcleo"])
    d1 = "DESPACHO\n\nIntime-se a parte A para manifestação no prazo de 10 dias."
    d2 = "DESPACHO\n\nIntime-se a parte B para manifestação no prazo de 15 dias."
    d3 = "DESPACHO\n\nIntime-se a parte C para manifestação no prazo de 20 dias."
    ws.append(["P1", "CumSenFaz", "PJE-AL", "1ª Vara Federal AL", "Intimação (1)", "Tema", "AL / Maceió", d1, "NTDC"])
    ws.append(["P1", "CumSenFaz", "PJE-AL", "1ª Vara Federal AL", "Intimação (2)", "Tema", "AL / Maceió", d1, "NTDC"])
    ws.append(["P2", "CumSenFaz", "PJE-AL", "1ª Vara Federal AL", "Intimação (3)", "Tema", "AL / Maceió", d2, "NTDC"])
    ws.append(["P3", "CumSenFaz", "PJE-AL", "1ª Vara Federal AL", "Intimação (4)", "Tema", "AL / Maceió", d3, "NTDC"])
    wb.save(path)


def test_unique_limit_yields_exact_unique_review_rows(tmp_path, monkeypatch):
    inp = tmp_path / "in.xlsx"
    out = tmp_path / "out"
    _make_xlsx(inp)

    def fake_call(record, units, routing, rule_match, max_candidates=3):
        actionable = [u for u in units if "Intime-se" in u.text][0]
        return TeacherResult(
            selected=[{"unit_ids": [actionable.unit_id], "category": "intimacao_manifestacao", "priority": 1, "reason": "ok"}],
            status="OK", attempts=1, response_mode="json_schema",
        )

    monkeypatch.setattr("dide1.pipeline.call_llama", fake_call)
    manifest = run(str(inp), str(out), teacher_mode="llama", unique_limit=2)
    assert manifest["unique_decisions"] == 2
    assert manifest["scanned"] == 3
    assert manifest["processed"] == 3
    assert manifest["cache_hits"] == 1

    wb = load_workbook(out / "review.xlsx")
    assert wb["revisao"].max_row == 3  # cabeçalho + 2 decisões únicas
