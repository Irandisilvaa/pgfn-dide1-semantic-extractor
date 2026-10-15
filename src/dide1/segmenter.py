from dataclasses import dataclass
import re
from .filters import motivo_rejeicao

@dataclass
class UnidadeTexto:
    id_unidade: str
    inicio: int
    fim: int
    texto: str
    secao: str
    rejeitada: str | None = None

CABECALHOS_SECAO = {
    "RELATÓRIO": "RELATORIO",
    "RELATORIO": "RELATORIO",
    "FUNDAMENTAÇÃO": "FUNDAMENTACAO",
    "FUNDAMENTACAO": "FUNDAMENTACAO",
    "DECIDO": "DECISAO",
    "DECISÃO": "DECISAO",
    "DECISAO": "DECISAO",
    "DISPOSITIVO": "DISPOSITIVO",
}
DIVISAO_TEXTO_LONGO = re.compile(r"(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])")


def segmentar(texto: str, limite_texto_longo: int = 1200):
    unidades = []
    secao = "OUTRO"
    contador_unidade = 1
    # Preserva as posições originais separando o texto pelos espaços entre blocos.
    intervalos = []
    ultimo_fim = 0
    for m in re.finditer(r"\n\s*\n+", texto):
        if m.start() > ultimo_fim:
            intervalos.append((ultimo_fim, m.start()))
        ultimo_fim = m.end()
    if ultimo_fim < len(texto): intervalos.append((ultimo_fim, len(texto)))
    if not intervalos and texto: intervalos = [(0, len(texto))]

    for s, e in intervalos:
        bloco = texto[s:e]
        texto_limpo = bloco.strip()
        if not texto_limpo:
            continue
        titulo_secao = texto_limpo.upper().strip(" :-")
        if titulo_secao in CABECALHOS_SECAO:
            secao = CABECALHOS_SECAO[titulo_secao]
            continue
        subintervalos = [(s, e)]
        if len(bloco) > limite_texto_longo:
            subintervalos = []
            posicao_busca = s
            for parte in DIVISAO_TEXTO_LONGO.split(bloco):
                indice = texto.find(parte, posicao_busca, e)
                if indice < 0: continue
                subintervalos.append((indice, indice + len(parte)))
                posicao_busca = indice + len(parte)
        for ss, ee in subintervalos:
            bruto = texto[ss:ee].strip()
            if not bruto: continue
            # Recupera os limites exatos do trecho depois de remover espaços nas bordas.
            espacos_esquerda = len(texto[ss:ee]) - len(texto[ss:ee].lstrip())
            espacos_direita = len(texto[ss:ee]) - len(texto[ss:ee].rstrip())
            a = ss + espacos_esquerda
            b = ee - espacos_direita
            bruto = texto[a:b]
            unidades.append(UnidadeTexto(f"U{contador_unidade:04d}", a, b, bruto, secao, motivo_rejeicao(bruto)))
            contador_unidade += 1
    return unidades


def reconstruir_texto_exato(fonte: str, ids_unidades, unidades):
    selecionados = [u for u in unidades if u.id_unidade in set(ids_unidades)]
    if not selecionados:
        return ""
    selecionados.sort(key=lambda u: u.inicio)
    # Mantém apenas trechos contínuos ou quase contínuos para não juntar partes sem relação.
    inicio, fim = selecionados[0].inicio, selecionados[0].fim
    for u in selecionados[1:]:
        lacuna = fonte[fim:u.inicio]
        if len(lacuna) > 8 and lacuna.strip():
            return "\n".join(x.texto for x in selecionados)
        fim = u.fim
    return fonte[inicio:fim]
