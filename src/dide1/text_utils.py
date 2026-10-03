import re
import unicodedata


def strip_accents(text: str) -> str:
    text = "" if text is None else str(text)
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def norm(text: str) -> str:
    text = strip_accents(text).casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slug(text: str, max_len: int = 80) -> str:
    s = norm(text)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return (s[:max_len] or "na")
