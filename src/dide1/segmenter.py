from dataclasses import dataclass
import re
from .filters import rejection_reason

@dataclass
class Unit:
    unit_id: str
    start: int
    end: int
    text: str
    section: str
    rejected: str | None = None

HEADINGS = {
    "RELATÓRIO": "RELATORIO",
    "RELATORIO": "RELATORIO",
    "FUNDAMENTAÇÃO": "FUNDAMENTACAO",
    "FUNDAMENTACAO": "FUNDAMENTACAO",
    "DECIDO": "DECISAO",
    "DECISÃO": "DECISAO",
    "DECISAO": "DECISAO",
    "DISPOSITIVO": "DISPOSITIVO",
}
SPLIT_LONG = re.compile(r"(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])")


def segment(text: str, long_threshold: int = 1200):
    units = []
    section = "OUTRO"
    uid = 1
    # Preserve offsets by splitting on blank-line boundaries.
    spans = []
    last = 0
    for m in re.finditer(r"\n\s*\n+", text):
        if m.start() > last:
            spans.append((last, m.start()))
        last = m.end()
    if last < len(text): spans.append((last, len(text)))
    if not spans and text: spans = [(0, len(text))]

    for s, e in spans:
        chunk = text[s:e]
        stripped = chunk.strip()
        if not stripped:
            continue
        upper = stripped.upper().strip(" :-")
        if upper in HEADINGS:
            section = HEADINGS[upper]
            continue
        subspans = [(s, e)]
        if len(chunk) > long_threshold:
            subspans = []
            cursor = s
            for part in SPLIT_LONG.split(chunk):
                idx = text.find(part, cursor, e)
                if idx < 0: continue
                subspans.append((idx, idx + len(part)))
                cursor = idx + len(part)
        for ss, ee in subspans:
            raw = text[ss:ee].strip()
            if not raw: continue
            # Restore exact trimmed bounds.
            ltrim = len(text[ss:ee]) - len(text[ss:ee].lstrip())
            rtrim = len(text[ss:ee]) - len(text[ss:ee].rstrip())
            a = ss + ltrim
            b = ee - rtrim
            raw = text[a:b]
            units.append(Unit(f"U{uid:04d}", a, b, raw, section, rejection_reason(raw)))
            uid += 1
    return units


def reconstruct_exact(source: str, unit_ids, units):
    selected = [u for u in units if u.unit_id in set(unit_ids)]
    if not selected:
        return ""
    selected.sort(key=lambda u: u.start)
    # Require contiguous/near-contiguous selection to avoid stitching unrelated text.
    start, end = selected[0].start, selected[0].end
    for u in selected[1:]:
        gap = source[end:u.start]
        if len(gap) > 8 and gap.strip():
            return "\n".join(x.text for x in selected)
        end = u.end
    return source[start:end]
