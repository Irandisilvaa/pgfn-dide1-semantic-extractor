import re
from .text_utils import norm

PURE_NUMERIC = re.compile(r"^\s*\d{16,}\s*$")
PARTY_REQUEST = re.compile(r"(?is)^\s*(?:\(?[ivxlcdm]+\)?[\s.\-–—:]*)?(?:no mérito,\s*)?(?:requer|requer-se|pede|postula|pretende|ao final,\s*(?:requer|o reconhecimento|a declaração))\b")
HISTORICAL = re.compile(r"(?is)\b(?:por meio de|em)\s+(?:despacho|decis[aã]o|senten[cç]a|ac[oó]rd[aã]o).*?\b(?:determinou|deferiu|indeferiu|concedeu|denegou|julgou)\b")
ORPHAN_DEADLINE = re.compile(r"(?is)^\s*prazo\s+(?:para\s+[^:]{1,80}:\s*)?\d+\s*(?:\([^)]*\))?\s*dias?\.?\s*$")
EXTERNAL_CITATION = re.compile(r"(?is)\bPROCESSO\s*:\s*\S+.*?\b(?:RELATOR|DESEMBARGADOR|TURMA|TRIBUNAL)\b.*?\bJULGAMENTO\s*:\s*\d{1,2}/\d{1,2}/\d{2,4}")


def rejection_reason(text: str) -> str | None:
    t = text or ""
    if not t.strip(): return "empty"
    if PURE_NUMERIC.match(t): return "numeric_identifier_only"
    if PARTY_REQUEST.search(t): return "likely_party_request"
    if HISTORICAL.search(t): return "historical_reference"
    if ORPHAN_DEADLINE.match(t): return "orphan_deadline"
    if EXTERNAL_CITATION.search(t): return "external_case_citation"
    if t.rstrip().endswith(":"): return "trailing_colon_fragment"
    if len(norm(t)) < 12: return "too_short"
    return None
