import re
from .text_utils import norm

PURE_NUMERIC = re.compile(r"^\s*\d{16,}\s*$")
PARTY_REQUEST = re.compile(r"(?is)^\s*(?:\(?[ivxlcdm]+\)?[\s.\-–—:]*)?(?:no mérito,\s*)?(?:requer|requer-se|pede|postula|pretende|ao final,\s*(?:requer|o reconhecimento|a declaração))\b")
HISTORICAL = re.compile(r"(?is)\b(?:por meio de|em)\s+(?:despacho|decis[aã]o|senten[cç]a|ac[oó]rd[aã]o).*?\b(?:determinou|deferiu|indeferiu|concedeu|denegou|julgou)\b")
ORPHAN_DEADLINE = re.compile(r"(?is)^\s*prazo\s+(?:para\s+[^:]{1,80}:\s*)?\d+\s*(?:\([^)]*\))?\s*dias?\.?\s*$")
EXTERNAL_CITATION = re.compile(r"(?is)\bPROCESSO\s*:\s*\S+.*?\b(?:RELATOR|DESEMBARGADOR|TURMA|TRIBUNAL)\b.*?\bJULGAMENTO\s*:\s*\d{1,2}/\d{1,2}/\d{2,4}")
SIGNATURE_BLOCK = re.compile(r"(?is)^\s*(?:\(assinado\s+digitalmente\)\s*)?(?:assinado\s+eletronicamente\s+por\b|documento\s+assinado\s+eletronicamente\b)")
SIGNATURE_DATE_ONLY = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*$")
SIGNATURE_ROLE_BLOCK = re.compile(r"(?is)^\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ .\-]{5,}\s*\n\s*(?:ju[ií]z|ju[ií]za|desembargador|desembargadora|t[eé]cnico|analista)\b")
LOCATION_DATE_BOILERPLATE = re.compile(r"(?is)^\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç .\-/]+,\s*(?:data(?:\s+e\s+hora)?\s+(?:registrad[ao]s?(?:\s+no\s+sistema)?|da assinatura)|na data da assinatura eletr[oô]nica)\.?\s*$")
URL_ONLY = re.compile(r"(?is)^\s*https?://\S+\s*(?:\d{12,})?\s*$")
GENERIC_CLOSING = re.compile(r"(?is)^\s*(?:intima[cç][õo]es?\s+e\s+)?provid[eê]ncias\s+necess[aá]rias\.?\s*$|^\s*intima[cç][õo]es?\s+e\s+provid[eê]ncias\s+necess[aá]rias\.?\s*$")
ACTION_PARENT = re.compile(r"(?is)\b(?:determino|defiro|indefiro|condeno|fixo|homologo|intime-se|proceda|promova|adote|observe|considere)\b")


def rejection_reason(text: str) -> str | None:
    t = text or ""
    if not t.strip():
        return "empty"
    if PURE_NUMERIC.match(t):
        return "numeric_identifier_only"
    if SIGNATURE_BLOCK.search(t) or SIGNATURE_DATE_ONLY.match(t) or SIGNATURE_ROLE_BLOCK.match(t):
        return "signature_or_timestamp"
    if LOCATION_DATE_BOILERPLATE.match(t):
        return "location_date_boilerplate"
    if URL_ONLY.match(t):
        return "url_or_electronic_identifier"
    if GENERIC_CLOSING.match(t):
        return "generic_closing_fragment"
    if PARTY_REQUEST.search(t):
        return "likely_party_request"
    if HISTORICAL.search(t):
        return "historical_reference"
    if ORPHAN_DEADLINE.match(t):
        return "orphan_deadline"
    if EXTERNAL_CITATION.search(t):
        return "external_case_citation"
    # Uma ordem acionável que termina em ':' pode ser a unidade-mãe de lista a/b/c.
    if t.rstrip().endswith(":") and not ACTION_PARENT.search(t):
        return "trailing_colon_fragment"
    if len(norm(t)) < 12:
        return "too_short"
    return None
