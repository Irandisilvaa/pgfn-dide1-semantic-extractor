"""Baseline determinístico inspirado na fórmula compartilhada por Jovaldo.
A ordem das regras é proposital e reproduz a semântica de IFS: primeira regra vence.
"""
import re
from dataclasses import dataclass
from .text_utils import norm

@dataclass
class RuleMatch:
    label: str
    rule_id: str
    evidence: str


def _contains(haystack: str, needle: str) -> bool:
    return norm(needle) in norm(haystack)


def classify(decision_text: str, expediente: str = "") -> RuleMatch | None:
    raw = decision_text or ""
    n = norm(raw)
    exp = norm(expediente)
    ordered = [
        ("certidão migração", "J01", lambda: "o presente processo foi migrado para este sistema eletronico" in n, "processo migrado"),
        ("sobrestamento", "J02", lambda: "finalidade: intimar as partes acerca do sobrestamento do processo" in n, "sobrestamento"),
        ("falar prescrição", "J03", lambda: "manifestarem-se sobre a ocorrencia de prescricao intercorrente" in n, "prescrição intercorrente"),
        ("falar EPE", "J04", lambda: "intime-se a credora para se manifestar sobre a epe" in n, "manifestar sobre EPE"),
        ("sentença prescrição/decadência", "J05", lambda: "extingo a presente execucao" in n and "art. 487" in n, "extinção art. 487"),
        ("ajuizada em duplicidade", "J06", lambda: "ajuizada em duplicidade" in n, "duplicidade"),
        ("transformação valores", "J07", lambda: "determino a transformacao em pagamento definitivo" in n, "pagamento definitivo"),
        ("sentença_proc_EPE", "J08", lambda: "acolho a excecao de pre-executividade" in n, "acolho EPE"),
        ("Sentença Resolução CNJ 689/2026", "J09", lambda: "689/2026" in raw and "sentenca" in exp, "689/2026 + expediente sentença"),
        ("Sentença1 Resolução CNJ 689/2026", "J10", lambda: "689/2026" in raw and bool(re.search(r"SENTENÇA\s*\n", raw)), "689/2026 + cabeçalho sentença"),
        ("Resolução CNJ 689/2026", "J11", lambda: "689/2026" in raw, "689/2026"),
        ("citação", "J12", lambda: "citacao" in exp, "expediente citação"),
        ("sentença", "J13", lambda: "sentenca" in exp, "expediente sentença"),
        ("requisitório", "J14", lambda: "intimacao do requisitorio" in exp, "expediente requisitório"),
        ("contrarrazões", "J15", lambda: "intimacao para contrarrazoes" in exp, "expediente contrarrazões"),
        ("contrarrazões1", "J16", lambda: "intimo a(s) parte(s) apelada(s) para apresentar(em) contrarrazoes" in n, "texto contrarrazões"),
        ("falar_docs", "J17", lambda: "manifeste-se acerca do(s) novo(s) documento(s) juntado(s) aos autos" in n, "novos documentos"),
        ("sentença1", "J18", lambda: bool(re.search(r"SENTENÇA\s*\n", raw)), "cabeçalho sentença"),
        ("ato ordinatório", "J19", lambda: bool(re.search(r"ATO ORDINATÓRIO\s*\n", raw)), "cabeçalho ato ordinatório"),
    ]
    for label, rid, pred, evidence in ordered:
        try:
            if pred():
                return RuleMatch(label, rid, evidence)
        except Exception:
            continue
    return None
