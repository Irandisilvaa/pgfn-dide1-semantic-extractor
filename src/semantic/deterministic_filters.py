from __future__ import annotations

import re
import unicodedata


_EXACT_LOW_VALUE = {
    "poder judiciário",
    "poder judiciario",
    "justiça federal",
    "justica federal",
    "relatório",
    "relatorio",
    "fundamentação",
    "fundamentacao",
    "dispositivo",
    "sentença",
    "sentenca",
    "decisão",
    "decisao",
    "despacho",
    "expedientes necessários.",
    "expedientes necessarios.",
    "nada mais.",
}

_PARTY_PREFIXES = (
    "autor:",
    "autora:",
    "réu:",
    "reu:",
    "ré:",
    "impetrante:",
    "impetrado:",
    "impetrada:",
    "autoridade:",
    "advogado",
    "advogada",
    "procurador:",
    "procuradora:",
)

_SIGNATURE_PREFIXES = (
    "assinado eletronicamente",
    "documento assinado",
    "assinatura eletrônica",
    "assinatura eletronica",
)

_DATE_ONLY_RE = re.compile(
    r"^\s*"
    r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
    r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?"
    r"\s*$"
)

_TIME_ONLY_RE = re.compile(
    r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s*$"
)

_PROCESS_NUMBER_RE = re.compile(
    r"^\s*\d{4,7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\s*$"
)

_ID_ONLY_RE = re.compile(
    r"^\s*(?:id\.?|ids\.?)\s*\d+\s*$",
    re.IGNORECASE,
)

_GENERIC_COMMAND_RE = re.compile(
    r"^\s*(?:"
    r"intime(?:m)?(?:\(m\))?-se|"
    r"notifique(?:m)?(?:\(m\))?-se|"
    r"cumpra-se|publique-se|registre-se"
    r")\s*[.!]?\s*$",
    re.IGNORECASE,
)

_VARA_HEADER_RE = re.compile(
    r"^\s*\d{1,3}\s*[ªºa]?\s*vara\s+federal\b.*$",
    re.IGNORECASE,
)

_TRIBUNAL_HEADER_RE = re.compile(
    r"^\s*(?:tribunal regional federal|trf|seção judiciária|"
    r"secao judiciaria)\b.*$",
    re.IGNORECASE,
)

_PREPARATORY_RE = re.compile(
    r"(?:"
    r"passo a realizar o seguinte ato ordinat[óo]rio|"
    r"decorrido o prazo|"
    r"ap[óo]s o decurso do prazo|"
    r"pelas raz[õo]es a seguir"
    r")\s*:?\s*$",
    re.IGNORECASE,
)

# Padrões observados no piloto real v3.1: itens de pedido da parte que
# lexicalmente parecem comandos judiciais. A regra é deliberadamente
# conservadora e não se aplica quando o trecho já está marcado como DISPOSITIVO.
_PARTY_REQUEST_LIST_RE = re.compile(
    r"^\s*(?:[a-z]|[ivxlcdm]+|\d+)\s*[.)-]\s*(?:"
    r"a\s+concess[ãa]o\b|"
    r"o\s+deferimento\b|"
    r"a\s+suspens[ãa]o\b|"
    r"seja\s+(?:julgad[oa]|declarad[oa]|reconhecid[oa]|concedid[oa])\b|"
    r"(?:determine|conceda|declare|reconhe[cç]a|confirme|expe[cç]a|autorize)\b"
    r")",
    re.IGNORECASE,
)

_PARTY_REQUEST_FINAL_RE = re.compile(
    r"^\s*(?:[a-z]\s*[.)-]\s*)?(?:e\s+)?ao\s+final,?\s+"
    r"(?:seja|a\s+concess[ãa]o|o\s+deferimento)\b",
    re.IGNORECASE,
)

# Referências inequívocas a decisões anteriores não devem ser tratadas como
# comando atual. Mantemos padrões específicos para reduzir falso bloqueio.
_HISTORICAL_DECISION_RE = re.compile(
    r"(?:"
    r"^\s*(?:na\s+sequ[êe]ncia,?\s*)?a\s+(?:decis[ãa]o|senten[cç]a|despacho|ac[óo]rd[ãa]o)\s+"
    r"(?:de\s+)?id\.?\s*\d+.*\b(?:reconheceu|determinou|deferiu|indeferiu|julgou|homologou|condenou)\b|"
    r"^\s*(?:indeferiu-se|deferiu-se|determinou-se|julgou-se|homologou-se)\b.*\b(?:no|na)\s+id\.?\s*\d+|"
    r"\b(?:foi|foram)\s+(?:deferid|indeferid|determinad|julgad|homologad|reconhecid)[a-záéíóúâêôãõç]*\b.*\bid\.?\s*\d+"
    r")",
    re.IGNORECASE,
)

_ORPHAN_DEADLINE_RE = re.compile(
    r"^\s*prazo\s*:?[ \t]*(?:de\s+)?\d{1,4}\s*(?:\([^)]*\)\s*)?"
    r"(?:dias?|horas?|meses?)\.?\s*$",
    re.IGNORECASE,
)

_GENERIC_URGENCY_RE = re.compile(
    r"^\s*cumpra-se\s+(?:com\s+)?urg[êe]ncia[.!]?\s*$",
    re.IGNORECASE,
)

_INTERNAL_GENERIC_ORDER_RE = re.compile(
    r"^\s*adote\s+a\s+secretaria\s+as\s+provid[êe]ncias\s+necess[áa]rias"
    r"\s+ao\s+impulsionamento\s+do\s+feito[.!]?\s*$",
    re.IGNORECASE,
)


_NARRATIVE_OR_ARGUMENT_RE = re.compile(
    r"(?:"
    r"^a parte (?:autora|ré|re|requerente|impetrante)\s+"
    r"(?:alega|alegou|sustenta|sustentou|requer|requereu|pediu|pugnou)\b|"
    r"^a defesa\s+(?:apresentou|alega|alegou|sustenta|sustentou)\b|"
    r"^o minist[ée]rio p[úu]blico\s+informou\b|"
    r"^foram juntados documentos\b|"
    r"^a legisla[cç][ãa]o de reg[êe]ncia cont[ée]m regras gerais\b|"
    r"^a controv[ée]rsia exige interpreta[cç][ãa]o sistem[áa]tica\b|"
    r"^a jurisprud[êe]ncia citada pelas partes\b|"
    r"^o art\.\s*\d+.*(?:mencionad|invocad|citado)"
    r")",
    re.IGNORECASE,
)

_STRONG_JUDICIAL_ACTION_RE = re.compile(
    r"\b(?:"
    r"determino|defiro|indefiro|julgo|homologo|condeno|declaro|"
    r"reconhe[cç]o|intime(?:m)?-se|notifique(?:m)?-se|d[êe]-se|"
    r"expe[cç]a-se|oficie-se|arquive(?:m)?-se|remetam-se|"
    r"encaminhem-se|suspenda-se|fica\s+determinado"
    r")\b",
    re.IGNORECASE,
)

_ACTION_WORDS = (
    "determino",
    "defiro",
    "indefiro",
    "julgo",
    "homologo",
    "condeno",
    "declaro",
    "intime",
    "intimem",
    "notifique",
    "notifiquem",
    "dê-se",
    "de-se",
    "expeça",
    "expeca",
    "oficie",
    "cumpra",
    "arquive",
    "arquivem",
    "restitu",
    "suspend",
    "manifesta",
    "parecer",
    "prazo",
    "recurso",
    "remessa",
    "trânsito",
    "transito",
    "requisição",
    "requisicao",
    "pagamento",
    "prescri",
    "honorár",
    "honorar",
)

_STRONG_DISPOSITIVE = (
    "determino",
    "defiro",
    "indefiro",
    "julgo",
    "homologo",
    "condeno",
    "declaro",
    "reconheço",
    "reconheco",
)

_PGFN_TERMS = (
    "fazenda nacional",
    "união",
    "uniao",
    "pfn",
    "pgfn",
    "procuradoria-geral da fazenda nacional",
    "procuradoria da fazenda nacional",
)


def normalize_for_rule(text: str) -> str:
    value = (text or "").strip().lower()
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\s+", " ", value)
    return value


def uppercase_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]

    if not letters:
        return 0.0

    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters)


def has_strong_dispositive(text: str) -> bool:
    norm = normalize_for_rule(text)
    return any(word in norm for word in _STRONG_DISPOSITIVE)


def effective_section(text: str, section: str) -> str:
    """Promove para DISPOSITIVO quando o próprio recorte é um decisum claro."""
    norm = normalize_for_rule(text)
    if re.match(r"^(?:ante|diante)\s+(?:(?:do|o)\s+)?exposto\b", norm):
        return "DISPOSITIVO"
    if re.match(
        r"^(?:julgo|homologo|extingo|condeno|declaro|defiro|indefiro|"
        r"denego|concedo|rejeito|nego\s+provimento|dou\s+provimento)\b",
        norm,
    ):
        return "DISPOSITIVO"
    return section


def incomplete_reason(text: str) -> str | None:
    raw = (text or "").strip()
    norm = normalize_for_rule(raw)

    if not raw:
        return "empty"

    if _PREPARATORY_RE.search(raw):
        return "preparatory_fragment"

    if raw.endswith(":") and not has_strong_dispositive(raw):
        return "trailing_colon_fragment"

    if re.search(r"\b(?:no|do|da)\s+e\.\s*$", norm):
        return "broken_abbreviation_fragment"

    if re.search(
        r"\b(?:considerando que|tendo em vista que|uma vez que)\s*$",
        norm,
    ):
        return "unfinished_connector"

    return None


def low_value_reason(text: str, *, section: str | None = None) -> str | None:
    raw = (text or "").strip()
    norm = normalize_for_rule(raw)

    if not norm:
        return "empty"

    if norm in _EXACT_LOW_VALUE:
        return "generic_or_heading"

    if _GENERIC_COMMAND_RE.match(raw) or _GENERIC_URGENCY_RE.match(raw):
        return "generic_command"

    if _ORPHAN_DEADLINE_RE.match(raw):
        return "orphan_deadline"

    if _INTERNAL_GENERIC_ORDER_RE.match(raw):
        return "generic_internal_order"

    if (section or "").upper() != "DISPOSITIVO":
        if _PARTY_REQUEST_LIST_RE.search(raw) or _PARTY_REQUEST_FINAL_RE.search(raw):
            return "likely_party_request"

    if _HISTORICAL_DECISION_RE.search(raw):
        return "historical_reference"

    if _DATE_ONLY_RE.match(raw):
        return "date_only"

    if _TIME_ONLY_RE.match(raw):
        return "time_only"

    if _PROCESS_NUMBER_RE.match(raw):
        return "process_number_only"

    if _ID_ONLY_RE.match(raw):
        return "id_only"

    if _VARA_HEADER_RE.match(raw):
        return "court_header"

    if _TRIBUNAL_HEADER_RE.match(raw):
        return "court_header"

    if _NARRATIVE_OR_ARGUMENT_RE.search(raw) and not _STRONG_JUDICIAL_ACTION_RE.search(raw):
        return "narrative_or_argument"

    incomplete = incomplete_reason(raw)
    if incomplete and not (
        incomplete == "trailing_colon_fragment"
        and has_strong_dispositive(raw)
    ):
        return incomplete

    if any(norm.startswith(prefix) for prefix in _PARTY_PREFIXES):
        if not any(word in norm for word in _ACTION_WORDS):
            return "party_or_authority_line"

    if any(norm.startswith(prefix) for prefix in _SIGNATURE_PREFIXES):
        return "signature"

    if len(raw) <= 18 and not any(
        word in norm for word in _ACTION_WORDS
    ):
        return "too_short"

    if (
        len(raw) <= 220
        and uppercase_ratio(raw) >= 0.78
        and not any(word in norm for word in _ACTION_WORDS)
    ):
        return "uppercase_header"

    return None


def has_direct_pgfn_reference(text: str) -> bool:
    norm = normalize_for_rule(text)
    return any(term in norm for term in _PGFN_TERMS)


def has_action_signal(text: str) -> bool:
    norm = normalize_for_rule(text)
    return any(word in norm for word in _ACTION_WORDS)


def infer_category_hint(text: str) -> str | None:
    """
    Retorna apenas categorias com sinal textual forte.

    A ordem é intencional: resultado final e próximo passo recursal devem
    prevalecer sobre palavras incidentais como "liminar", "prazo" ou
    "manifestação" presentes no mesmo trecho.
    """
    norm = normalize_for_rule(text)

    if "honorár" in norm or "honorar" in norm or "custas" in norm:
        return "honorarios_custas"

    if "prescri" in norm or "decad" in norm:
        return "prescricao_decadencia"

    # Resultado atual do julgamento / recurso.
    if re.search(
        r"(?:^|\b)(?:"
        r"julgo\b|homologo\b|extingo\b|denego\s+a\s+seguran[cç]a\b|"
        r"concedo(?:\s+parcialmente)?\s+a\s+seguran[cç]a\b|"
        r"rejeito\s+(?:os\s+)?embargos\b|nego(?:-lhes)?\s+provimento\b|"
        r"dou\s+provimento\b|recurso\s+(?:provido|desprovido)\b|"
        r"apela[cç][ãa]o\s+(?:provida|improvida)\b"
        r")",
        norm,
    ):
        return "resultado_julgamento"

    # Tutela/liminar, desde que não seja um resultado final capturado acima.
    if any(x in norm for x in ("tutela", "liminar")):
        return "tutela"

    if any(
        x in norm
        for x in (
            "restitu",
            "repetição de indébito",
            "repeticao de indebido",
            "compensa",
        )
    ):
        return "restituicao_pagamento"

    # Próximo passo recursal/processual antes de intimação/prazo, pois esses
    # termos frequentemente coexistem em contrarrazões/remessa ao TRF.
    if any(
        x in norm
        for x in (
            "contrarraz",
            "remeta-se",
            "remetam-se",
            "remeter os autos",
            "remeta o feito",
            "trf",
            "reexame necessário",
            "reexame necessario",
            "duplo grau",
            "trânsito em julgado",
            "transito em julgado",
            "arquive-se",
            "arquivem-se",
            "retornem os autos ao arquivo",
            "voltem os autos ao arquivo",
            "recurso",
        )
    ):
        return "recurso_proximo_passo"

    if any(
        x in norm
        for x in (
            "intime",
            "notifique",
            "manifestação",
            "manifestacao",
            "ciência",
            "ciencia",
            "parecer",
        )
    ):
        return "intimacao_manifestacao"

    if any(x in norm for x in ("reconhe", "concord", "não se oporia", "nao se oporia")):
        return "reconhecimento_concordancia"

    if "prazo" in norm:
        return "prazo_cumprimento"

    if any(
        x in norm
        for x in (
            "determino",
            "determinar à",
            "determinar a",
            "encaminhem-se",
            "oficie-se",
            "abstenha",
        )
    ):
        return "ordem_determinacao"

    return None


def heuristic_score(
    *,
    text: str,
    section: str,
    model_priority: int,
    validator_relevance: int = 0,
) -> float:
    score = float(model_priority) * 2.0
    score += float(validator_relevance) * 1.5
    norm = normalize_for_rule(text)

    section_bonus = {
        "DISPOSITIVO": 4.0,
        "DECISAO": 2.0,
        "FUNDAMENTACAO": 0.5,
        "RELATORIO": -3.0,
        "OUTRO": 0.0,
    }
    score += section_bonus.get(section, 0.0)

    if has_direct_pgfn_reference(text):
        score += 2.5

    if has_action_signal(text):
        score += 1.5

    if "prazo" in norm:
        score += 0.75

    if any(
        x in norm
        for x in ("diante do exposto", "ante o exposto")
    ):
        score += 1.0

    if section == "RELATORIO" and any(
        x in norm
        for x in (
            "objetivando",
            "requereu",
            "alegou",
            "sustentou",
            "pugnou",
        )
    ):
        score -= 2.0

    if _PARTY_REQUEST_LIST_RE.search(text) or _PARTY_REQUEST_FINAL_RE.search(text):
        score -= 5.0

    if _HISTORICAL_DECISION_RE.search(text):
        score -= 5.0

    return round(score, 3)
