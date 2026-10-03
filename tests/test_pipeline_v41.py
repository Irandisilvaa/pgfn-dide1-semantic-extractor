from pathlib import Path
from openpyxl import Workbook

from dide1.pipeline import run
from dide1.teacher import TeacherResult


def _make_xlsx(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Processo", "Classe", "Origem", "Órgão Julgador", "Expediente", "Assunto", "Seção/Subseção", "Decisão Judicial", "Núcleo"])
    decision = "DESPACHO\n\nIntime-se a parte para manifestação no prazo de 10 dias."
    ws.append(["P1", "CumSenFaz", "PJE-AL", "1ª Vara Federal AL", "Intimação (1)", "Tema", "AL / Maceió", decision, "NTDC"])
    ws.append(["P1", "CumSenFaz", "PJE-AL", "1ª Vara Federal AL", "Intimação (2)", "Tema", "AL / Maceió", decision, "NTDC"])
    wb.save(path)


def test_pipeline_caches_identical_decisions(tmp_path, monkeypatch):
    inp = tmp_path / "in.xlsx"
    out = tmp_path / "out"
    _make_xlsx(inp)
    calls = {"n": 0}

    def fake_call(record, units, routing, rule_match, max_candidates=3):
        calls["n"] += 1
        actionable = [u for u in units if "Intime-se" in u.text][0]
        return TeacherResult(
            selected=[{"unit_ids": [actionable.unit_id], "category": "intimacao_manifestacao", "priority": 1, "reason": "ok"}],
            status="OK",
            attempts=1,
            response_mode="json_schema",
        )

    monkeypatch.setattr("dide1.pipeline.call_llama", fake_call)
    manifest = run(str(inp), str(out), limit=2, teacher_mode="llama")
    assert manifest["processed"] == 2
    assert manifest["errors"] == 0
    assert manifest["unique_inferences"] == 1
    assert manifest["cache_hits"] == 1
    assert calls["n"] == 1
