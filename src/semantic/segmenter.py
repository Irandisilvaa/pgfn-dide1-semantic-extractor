from __future__ import annotations

from dataclasses import dataclass
import html
import re


@dataclass(frozen=True)
class TextUnit:
    id: str
    index: int
    text: str
    section: str = "OUTRO"


_URL_RE = re.compile(r"https?\\?://\S+", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_PRIVATE_DOT = "\uE000"

_ABBREVIATIONS = (
    "art", "arts", "inc", "incs", "n", "no", "núm", "p", "pp",
    "dr", "dra", "sr", "sra", "des", "min", "rel", "proc",
    "fl", "fls", "id", "ids", "exmo", "exma", "v", "cf",
    "e",  # E. TRF / E. Tribunal
)


def _merge_soft_lines(lines: list[str]) -> list[str]:
    """
    Une quebras visuais que não parecem representar novo parágrafo.

    Conservador: cobre principalmente casos observados no piloto, como:
    "... no E." + "TRF da 5ª Região ...".
    """
    out: list[str] = []
    i = 0

    while i < len(lines):
        current = lines[i].strip()

        if not current:
            out.append("")
            i += 1
            continue

        while i + 1 < len(lines):
            nxt = lines[i + 1].strip()

            if not nxt:
                break

            lower = current.lower()

            should_merge = bool(
                re.search(r"\b(?:no|do|da)\s+e\.$", lower)
                or current.endswith(",")
                or current.endswith("(")
                or current.endswith('"')
            )

            if not should_merge:
                break

            current = f"{current} {nxt}".strip()
            i += 1

        out.append(current)
        i += 1

    return out


def normalize_decision_text(raw: str) -> str:
    text = html.unescape(raw or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = _TAG_RE.sub(" ", text)
    text = _URL_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = [
        _WS_RE.sub(" ", line).strip()
        for line in text.split("\n")
    ]

    lines = _merge_soft_lines(lines)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _protect_dots(text: str) -> str:
    protected = text

    protected = re.sub(
        r"(?<=\d)\.(?=\d)",
        _PRIVATE_DOT,
        protected,
    )

    for abbr in _ABBREVIATIONS:
        protected = re.sub(
            rf"\b({re.escape(abbr)})\.",
            rf"\1{_PRIVATE_DOT}",
            protected,
            flags=re.IGNORECASE,
        )

    protected = re.sub(
        r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ])\.(?=\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]\.)",
        rf"\1{_PRIVATE_DOT}",
        protected,
    )

    return protected


def _restore_dots(text: str) -> str:
    return text.replace(_PRIVATE_DOT, ".")


_ACTION_START = (
    r"(?:"
    r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9]"
    r"|Intime(?:m)?-se"
    r"|Notifique(?:m)?-se"
    r"|Dê-se"
    r"|Dêem-se"
    r"|Expeça-se"
    r"|Oficie-se"
    r"|Cumpra-se"
    r"|Publique-se"
    r"|Após"
    r"|Transitad[oa]"
    r"|Certificad[oa]"
    r"|Determino"
    r"|Defiro"
    r"|Indefiro"
    r"|Julgo"
    r"|Homologo"
    r"|Condeno"
    r"|Declaro"
    r")"
)


def _split_sentences(paragraph: str) -> list[str]:
    protected = _protect_dots(paragraph)

    parts = re.split(
        rf"(?<=[.!?;])\s+(?={_ACTION_START})",
        protected,
        flags=re.IGNORECASE,
    )

    return [
        _restore_dots(p).strip()
        for p in parts
        if _restore_dots(p).strip()
    ]


def _split_action_clauses(text: str) -> list[str]:
    protected = _protect_dots(text)

    action_verbs = (
        r"(?:"
        r"determino|defiro|indefiro|julgo|homologo|condeno|declaro|"
        r"intime(?:m)?-se|notifique(?:m)?-se|dê-se|dêem-se|"
        r"expeça-se|oficie-se|cumpra-se|publique-se|"
        r"fica(?:m)?|deverá|deverão"
        r")"
    )

    parts = re.split(
        rf"(?<=;)\s+(?={action_verbs}\b)",
        protected,
        flags=re.IGNORECASE,
    )

    return [
        _restore_dots(p).strip()
        for p in parts
        if _restore_dots(p).strip()
    ]


def _split_oversized(text: str, max_unit_chars: int) -> list[str]:
    if len(text) <= max_unit_chars:
        return [text]

    protected = _protect_dots(text)
    rough = re.split(r"(?<=[;:])\s+", protected)
    rough = [
        _restore_dots(x).strip()
        for x in rough
        if x.strip()
    ]

    out: list[str] = []
    current = ""

    for part in rough:
        if len(part) > max_unit_chars:
            words = part.split()
            buf: list[str] = []
            size = 0

            for word in words:
                extra = len(word) + (1 if buf else 0)

                if buf and size + extra > max_unit_chars:
                    out.append(" ".join(buf))
                    buf = [word]
                    size = len(word)
                else:
                    buf.append(word)
                    size += extra

            if buf:
                out.append(" ".join(buf))
            continue

        if not current:
            current = part
        elif len(current) + 1 + len(part) <= max_unit_chars:
            current = f"{current} {part}"
        else:
            out.append(current)
            current = part

    if current:
        out.append(current)

    return [x.strip() for x in out if x.strip()]


def _section_from_paragraph(paragraph: str, current: str) -> str:
    norm = re.sub(r"\s+", " ", paragraph.strip()).upper()

    if re.fullmatch(r"(?:I+\.\s*)?RELAT[ÓO]RIO[.:]?", norm):
        return "RELATORIO"

    if re.fullmatch(
        r"(?:I+\.\s*)?(?:FUNDAMENTA[CÇ][ÃA]O|M[ÉE]RITO)[.:]?",
        norm,
    ):
        return "FUNDAMENTACAO"

    if re.fullmatch(
        r"(?:I+\.\s*)?(?:DISPOSITIVO|CONCLUS[ÃA]O)[.:]?",
        norm,
    ):
        return "DISPOSITIVO"

    if re.fullmatch(
        r"(?:DECIS[ÃA]O|SENTEN[CÇ]A|DESPACHO)[.:]?",
        norm,
    ):
        return "DECISAO"

    if re.match(r"^(?:ANTE|DIANTE) DO EXPOSTO\b", norm):
        return "DISPOSITIVO"

    if re.match(
        r"^(?:JULGO|HOMOLOGO|CONDENO|DECLARO|DEFIRO|INDEFIRO)\b",
        norm,
    ):
        if current in {
            "FUNDAMENTACAO",
            "RELATORIO",
            "OUTRO",
            "DECISAO",
        }:
            return "DISPOSITIVO"

    return current


def make_units(
    raw: str,
    *,
    max_unit_chars: int = 1000,
) -> list[TextUnit]:
    clean = normalize_decision_text(raw)

    paragraphs = [
        p.strip()
        for p in re.split(r"\n+", clean)
        if p.strip()
    ]

    atomic: list[tuple[str, str]] = []
    current_section = "OUTRO"

    for paragraph in paragraphs:
        current_section = _section_from_paragraph(
            paragraph,
            current_section,
        )

        for sentence in _split_sentences(paragraph):
            for clause in _split_action_clauses(sentence):
                for piece in _split_oversized(
                    clause,
                    max_unit_chars=max_unit_chars,
                ):
                    atomic.append((piece, current_section))

    return [
        TextUnit(
            id=f"P{i:04d}",
            index=i,
            text=text,
            section=section,
        )
        for i, (text, section) in enumerate(atomic, start=1)
    ]


def group_units(
    units: list[TextUnit],
    *,
    max_chunk_chars: int = 3000,
) -> list[list[TextUnit]]:
    chunks: list[list[TextUnit]] = []
    current: list[TextUnit] = []
    current_len = 0

    for unit in units:
        extra = len(unit.text) + len(unit.id) + len(unit.section) + 18

        if current and current_len + extra > max_chunk_chars:
            chunks.append(current)
            current = [unit]
            current_len = extra
        else:
            current.append(unit)
            current_len += extra

    if current:
        chunks.append(current)

    return chunks
