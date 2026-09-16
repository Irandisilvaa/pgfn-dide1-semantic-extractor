from pathlib import Path

import pytest
from openpyxl import Workbook

from src.annotation.local_xlsx import inspect_workbook, iter_source_rows


def make_input(path: Path, headers=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "input"
    ws.append(headers or [
        "Extração", "Processo", "Classe judicial", "Órgão julgador",
        "Polo Ativo", "Polo Passivo", "Decisão", "Matéria SAJ", "Ind.", "tags"
    ])
    ws.append(["2026-09-01", "P1", "Classe", "Órgão", "A", "B", "Intime-se a União.", "M", "I", "T"])
    ws.append(["2026-09-02", "P2", "Classe", "Órgão", "A", "B", "Julgo improcedente o pedido.", "M", "", ""])
    wb.save(path)


def test_inspect_local_xlsx_and_iter(tmp_path: Path):
    path = tmp_path / "entrada.xlsx"
    make_input(path)
    info = inspect_workbook(path, "input")
    assert "Processo" in info.canonical_to_index
    assert "Decisão" in info.canonical_to_index
    rows = list(iter_source_rows(path, sheet="input"))
    assert len(rows) == 2
    assert rows[0]["source_row"] == 2
    assert rows[0]["Processo"] == "P1"
    assert rows[1]["Decisão"] == "Julgo improcedente o pedido."


def test_local_xlsx_accepts_unaccented_aliases(tmp_path: Path):
    path = tmp_path / "entrada.xlsx"
    make_input(path, headers=[
        "Extracao", "Processo", "Classe judicial", "Orgao julgador",
        "Polo Ativo", "Polo Passivo", "Decisao", "Materia SAJ", "Ind", "tag"
    ])
    rows = list(iter_source_rows(path, sheet="input", limit=1))
    assert rows[0]["Decisão"] == "Intime-se a União."
    assert rows[0]["Órgão julgador"] == "Órgão"
    assert rows[0]["tags"] == "T"


def test_local_xlsx_requires_decision_and_process(tmp_path: Path):
    path = tmp_path / "bad.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "input"
    ws.append(["Extração", "Classe judicial"])
    ws.append(["x", "y"])
    wb.save(path)
    with pytest.raises(ValueError, match="Colunas obrigatórias ausentes"):
        inspect_workbook(path, "input")
