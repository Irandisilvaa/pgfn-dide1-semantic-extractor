from collections import Counter
from .input_loader import iterar_registros
from .router import familia_classe
from .pipeline import eh_execucao_fiscal


def inspecionar_dados(caminho: str, aba: str | None = None, limite: int | None = None):
    n = 0; sem_decisao = 0; execucoes_fiscais = 0
    classes_encontradas = Counter(); orgaos = Counter(); familias = Counter()
    for registro_atual in iterar_registros(caminho, aba=aba):
        if limite and n >= limite: break
        n += 1
        d = registro_atual.dados
        if not d.get("decisao", "").strip(): sem_decisao += 1
        if eh_execucao_fiscal(d): execucoes_fiscais += 1
        classes_encontradas[str(d.get("classe", ""))] += 1
        orgaos[str(d.get("orgao_julgador", ""))] += 1
        familias[familia_classe(d.get("classe", ""))] += 1
    return {"rows": n, "empty_decisions": sem_decisao, "execucao_fiscal": execucoes_fiscais, "top_classes": classes_encontradas.most_common(10), "top_organs": orgaos.most_common(10), "class_families": familias.most_common(20)}
