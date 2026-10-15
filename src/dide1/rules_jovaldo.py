"""Baseline determinístico inspirado na fórmula compartilhada por Jovaldo.
A ordem das regras é proposital e reproduz a semântica de IFS: primeira regra vence.
"""
import re
from dataclasses import dataclass
from .text_utils import normalizar

@dataclass
class ResultadoRegra:
    rotulo: str
    id_regra: str
    evidencia: str


def _contem(texto_base: str, termo: str) -> bool:
    return normalizar(termo) in normalizar(texto_base)


def classificar(texto_decisao: str, expediente: str = "") -> ResultadoRegra | None:
    texto_bruto = texto_decisao or ""
    texto_normalizado = normalizar(texto_bruto)
    expediente_normalizado = normalizar(expediente)
    regras_ordenadas = [
        ("certidão migração", "J01", lambda: "o presente processo foi migrado para este sistema eletronico" in texto_normalizado, "processo migrado"),
        ("sobrestamento", "J02", lambda: "finalidade: intimar as partes acerca do sobrestamento do processo" in texto_normalizado, "sobrestamento"),
        ("falar prescrição", "J03", lambda: "manifestarem-se sobre a ocorrencia de prescricao intercorrente" in texto_normalizado, "prescrição intercorrente"),
        ("falar EPE", "J04", lambda: "intime-se a credora para se manifestar sobre a epe" in texto_normalizado, "manifestar sobre EPE"),
        ("sentença prescrição/decadência", "J05", lambda: "extingo a presente execucao" in texto_normalizado and "art. 487" in texto_normalizado, "extinção art. 487"),
        ("ajuizada em duplicidade", "J06", lambda: "ajuizada em duplicidade" in texto_normalizado, "duplicidade"),
        ("transformação valores", "J07", lambda: "determino a transformacao em pagamento definitivo" in texto_normalizado, "pagamento definitivo"),
        ("sentença_proc_EPE", "J08", lambda: "acolho a excecao de pre-executividade" in texto_normalizado, "acolho EPE"),
        ("Sentença Resolução CNJ 689/2026", "J09", lambda: "689/2026" in texto_bruto and "sentenca" in expediente_normalizado, "689/2026 + expediente sentença"),
        ("Sentença1 Resolução CNJ 689/2026", "J10", lambda: "689/2026" in texto_bruto and bool(re.search(r"SENTENÇA\s*\n", texto_bruto)), "689/2026 + cabeçalho sentença"),
        ("Resolução CNJ 689/2026", "J11", lambda: "689/2026" in texto_bruto, "689/2026"),
        ("citação", "J12", lambda: "citacao" in expediente_normalizado, "expediente citação"),
        ("sentença", "J13", lambda: "sentenca" in expediente_normalizado, "expediente sentença"),
        ("requisitório", "J14", lambda: "intimacao do requisitorio" in expediente_normalizado, "expediente requisitório"),
        ("contrarrazões", "J15", lambda: "intimacao para contrarrazoes" in expediente_normalizado, "expediente contrarrazões"),
        ("contrarrazões1", "J16", lambda: "intimo a(s) parte(s) apelada(s) para apresentar(em) contrarrazoes" in texto_normalizado, "texto contrarrazões"),
        ("falar_docs", "J17", lambda: "manifeste-se acerca do(s) novo(s) documento(s) juntado(s) aos autos" in texto_normalizado, "novos documentos"),
        ("sentença1", "J18", lambda: bool(re.search(r"SENTENÇA\s*\n", texto_bruto)), "cabeçalho sentença"),
        ("ato ordinatório", "J19", lambda: bool(re.search(r"ATO ORDINATÓRIO\s*\n", texto_bruto)), "cabeçalho ato ordinatório"),
    ]
    for rotulo, id_regra_atual, condicao, evidencia in regras_ordenadas:
        try:
            if condicao():
                return ResultadoRegra(rotulo, id_regra_atual, evidencia)
        except Exception:
            continue
    return None
