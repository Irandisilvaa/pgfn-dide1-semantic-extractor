from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import re
from openpyxl import load_workbook
from .text_utils import norm

ALIASES = {
    "processo": {"processo", "numero_processo", "n_processo"},
    "classe": {"classe", "classe_judicial"},
    "origem": {"origem"},
    "orgao_julgador": {"orgao_julgador", "orgao julgador"},
    "data": {"data", "data_expediente"},
    "polo_ativo": {"polo_ativo", "polo ativo"},
    "polo_passivo": {"polo_passivo", "polo passivo"},
    "expediente": {"expediente"},
    "prazo": {"prazo"},
    "assunto": {"assunto"},
    "secao_subsecao": {"secao_subsecao", "secao/subsecao", "seção/subseção"},
    "link": {"link"},
    "decisao": {"decisao_judicial", "decisão judicial", "decisao", "decisão"},
    "nucleo": {"nucleo", "núcleo"},
}


def _canon_header(v: Any) -> str:
    s = norm("" if v is None else str(v))
    s = re.sub(r"[^a-z0-9/]+", "_", s).strip("_")
    return s


def _find_columns(headers):
    canon = {_canon_header(h): i for i, h in enumerate(headers)}
    out = {}
    for key, vals in ALIASES.items():
        candidates = {_canon_header(v) for v in vals}
        for c in candidates:
            if c in canon:
                out[key] = canon[c]
                break
    missing = [x for x in ("processo", "classe", "orgao_julgador", "expediente", "decisao") if x not in out]
    if missing:
        raise ValueError(f"Colunas obrigatórias não encontradas: {missing}. Cabeçalhos: {headers}")
    return out

@dataclass
class DecisionRecord:
    source_row: int
    data: dict


def iter_records(path: str, sheet: str | None = None) -> Iterable[DecisionRecord]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    wb = load_workbook(p, read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    headers = list(next(rows))
    mapping = _find_columns(headers)
    for excel_row, row in enumerate(rows, start=2):
        d = {}
        for key, idx in mapping.items():
            d[key] = row[idx] if idx < len(row) else None
        d["decisao"] = "" if d.get("decisao") is None else str(d.get("decisao"))
        d["processo"] = "" if d.get("processo") is None else str(d.get("processo"))
        yield DecisionRecord(excel_row, d)
