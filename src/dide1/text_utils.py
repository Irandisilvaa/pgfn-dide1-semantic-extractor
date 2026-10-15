import re
import unicodedata


def remover_acentos(texto: str) -> str:
    texto = "" if texto is None else str(texto)
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    texto = remover_acentos(texto).casefold()
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def gerar_slug(texto: str, tamanho_maximo: int = 80) -> str:
    s = normalizar(texto)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return (s[:tamanho_maximo] or "na")
