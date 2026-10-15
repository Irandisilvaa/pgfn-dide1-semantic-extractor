import re
from .text_utils import normalizar

APENAS_NUMERICO = re.compile(r"^\s*\d{16,}\s*$")
PEDIDO_PARTE = re.compile(r"(?is)^\s*(?:\(?[ivxlcdm]+\)?[\s.\-–—:]*)?(?:no mérito,\s*)?(?:requer|requer-se|pede|postula|pretende|ao final,\s*(?:requer|o reconhecimento|a declaração))\b")
REFERENCIA_HISTORICA = re.compile(r"(?is)\b(?:por meio de|em)\s+(?:despacho|decis[aã]o|senten[cç]a|ac[oó]rd[aã]o).*?\b(?:determinou|deferiu|indeferiu|concedeu|denegou|julgou)\b")
PRAZO_ORFAO = re.compile(r"(?is)^\s*prazo\s+(?:para\s+[^:]{1,80}:\s*)?\d+\s*(?:\([^)]*\))?\s*dias?\.?\s*$")
CITACAO_EXTERNA = re.compile(r"(?is)\bPROCESSO\s*:\s*\S+.*?\b(?:RELATOR|DESEMBARGADOR|TURMA|TRIBUNAL)\b.*?\bJULGAMENTO\s*:\s*\d{1,2}/\d{1,2}/\d{2,4}")
BLOCO_ASSINATURA = re.compile(r"(?is)^\s*(?:\(assinado\s+digitalmente\)\s*)?(?:assinado\s+eletronicamente\s+por\b|documento\s+assinado\s+eletronicamente\b)")
APENAS_DATA_ASSINATURA = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*$")
BLOCO_CARGO_ASSINATURA = re.compile(r"(?is)^\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ .\-]{5,}\s*\n\s*(?:ju[ií]z|ju[ií]za|desembargador|desembargadora|t[eé]cnico|analista)\b")
LOCAL_DATA_PADRAO = re.compile(r"(?is)^\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç .\-/]+,\s*(?:data(?:\s+e\s+hora)?\s+(?:registrad[ao]s?(?:\s+no\s+sistema)?|da assinatura)|na data da assinatura eletr[oô]nica)\.?\s*$")
APENAS_URL = re.compile(r"(?is)^\s*https?://\S+\s*(?:\d{12,})?\s*$")
FECHO_GENERICO = re.compile(r"(?is)^\s*(?:\d+[.)]\s*)?(?:(?:intima[cç][õo]es?\s+e\s+)?provid[eê]ncias\s+necess[aá]rias|intima[cç][õo]es?\s+e\s+provid[eê]ncias\s+necess[aá]rias|intimem-se)\.?\s*$")
ORDEM_PRINCIPAL = re.compile(r"(?is)\b(?:determino|defiro|indefiro|condeno|fixo|homologo|intime-se|proceda|promova|adote|observe|considere)\b")


def motivo_rejeicao(texto: str) -> str | None:
    trecho = texto or ""
    if not trecho.strip():
        return "empty"
    if APENAS_NUMERICO.match(trecho):
        return "numeric_identifier_only"
    if BLOCO_ASSINATURA.search(trecho) or APENAS_DATA_ASSINATURA.match(trecho) or BLOCO_CARGO_ASSINATURA.match(trecho):
        return "signature_or_timestamp"
    if LOCAL_DATA_PADRAO.match(trecho):
        return "location_date_boilerplate"
    if APENAS_URL.match(trecho):
        return "url_or_electronic_identifier"
    if FECHO_GENERICO.match(trecho):
        return "generic_closing_fragment"
    if PEDIDO_PARTE.search(trecho):
        return "likely_party_request"
    if REFERENCIA_HISTORICA.search(trecho):
        return "historical_reference"
    if PRAZO_ORFAO.match(trecho):
        return "orphan_deadline"
    if CITACAO_EXTERNA.search(trecho):
        return "external_case_citation"
    # Uma ordem acionável que termina em ':' pode ser a unidade-mãe de lista a/b/c.
    if trecho.rstrip().endswith(":") and not ORDEM_PRINCIPAL.search(trecho):
        return "trailing_colon_fragment"
    if len(normalizar(trecho)) < 12:
        return "too_short"
    return None
