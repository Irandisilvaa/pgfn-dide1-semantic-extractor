from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Any

import requests

from .constants import CATEGORIAS
from .text_utils import normalizar


PROMPT_SISTEMA = """Você é o teacher local do projeto DIDE1/PGFN. Sua função é selecionar, de modo conservador, unidades textuais da DECISÃO ATUAL que contenham informação juridicamente acionável para a triagem/defesa cível.

Regras obrigatórias:
1) Selecione somente IDs fornecidos. Nunca reescreva nem invente texto.
2) Priorize comando atual, resultado do julgamento, intimação/manifestações, tutela, obrigação, prazo, pagamento/restituição, honorários/custas, recurso/próximo passo, prescrição/decadência e reconhecimento/concordância.
3) NÃO selecione pedido da parte como se fosse decisão judicial.
4) NÃO selecione mera narrativa histórica de decisão anterior, citação de outro processo ou fundamentação sem efeito operacional atual.
5) NÃO selecione assinatura, nome do magistrado/servidor, data/hora de assinatura, URL, identificador eletrônico ou mero fecho protocolar.
6) NÃO selecione isoladamente expressões genéricas como 'Intimações e providências necessárias' ou equivalentes sem dizer quem deve fazer o quê.
7) Quando uma ordem termina em ':' e os itens seguintes (a, b, c... ou 1, 2, 3...) completam a ordem, selecione a unidade da ordem-mãe JUNTO com os itens necessários para formar um recorte autocontido.
8) O trecho precisa ser autocontido e acionável. Evite fragmentos órfãos.
9) Use 'tutela' somente para tutela provisória/urgência/evidência, liminar, suspensão ou providência de natureza cautelar. Um simples 'defiro' não transforma a ordem em tutela.
10) Retorne no máximo {maximo_candidatos} seleções.
11) Retorne JSON puro, sem markdown, preferencialmente no formato {{"selected": [...]}}.
"""

# Usado quando a primeira resposta não vem em JSON válido.
PROMPT_NOVA_TENTATIVA = """Sua resposta precisa ser JSON válido e conter apenas seleções baseadas nos IDs fornecidos. Use exatamente o formato {"selected":[{"unit_ids":["U0001"],"category":"ordem_determinacao","priority":1,"reason":"curto"}]}. Se não houver recorte válido, use {"selected":[]}."""


class ErroLeituraModelo(ValueError):
    pass


@dataclass
class ResultadoModelo:
    selecionados: list[dict]
    situacao: str
    tentativas: int
    modo_resposta: str
    observacao_leitura: str = ""


# Converte a resposta do modelo em JSON, tolerando pequenos desvios de formato.
def _ler_json(texto: str) -> Any:
    """Parse JSON tolerando fences e um pequeno prefixo/sufixo textual."""
    texto = (texto or "").strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.I | re.S).strip()

    if not texto:
        raise ErroLeituraModelo("resposta vazia")

    try:
        return json.loads(texto)

    except Exception:
        decodificador = json.JSONDecoder()
        inicios = [i for i, caractere in enumerate(texto) if caractere in "[{"]

        for i in inicios:
            try:
                objeto, _ = decodificador.raw_decode(texto[i:])
                return objeto
            except Exception:
                continue

        raise ErroLeituraModelo("resposta sem JSON decodificável")


def _extrair_selecoes(dados: Any) -> tuple[list[dict], str]:
    """Aceita tanto {selected:[...]} quanto [...] diretamente."""
    if isinstance(dados, list):
        bruto = dados
        observacao = "top_level_list"

    elif isinstance(dados, dict):
        bruto = dados.get("selected", [])
        observacao = "selected_object"

    else:
        raise ErroLeituraModelo(
            f"tipo JSON inesperado: {type(dados).__name__}"
        )

    if bruto is None:
        return [], observacao

    if isinstance(bruto, dict):
        bruto = [bruto]
        observacao += ":single_object_wrapped"

    if not isinstance(bruto, list):
        raise ErroLeituraModelo("campo selected não é lista")

    itens = [x for x in bruto if isinstance(x, dict)]

    return itens, observacao


# Restringe a resposta do modelo ao formato e às categorias aceitas pelo projeto.
def _formato_resposta(maximo_candidatos: int) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "dide1_teacher_selection",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "selected": {
                        "type": "array",
                        "maxItems": maximo_candidatos,
                        "items": {
                            "type": "object",
                            "properties": {
                                "unit_ids": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string"},
                                },
                                "category": {
                                    "type": "string",
                                    "enum": list(CATEGORIAS)
                                },
                                "priority": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 4
                                },
                                "reason": {
                                    "type": "string"
                                },
                            },
                            "required": [
                                "unit_ids",
                                "category",
                                "priority",
                                "reason"
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["selected"],
                "additionalProperties": False,
            },
        },
    }


# Faz a chamada ao servidor local e tenta formatos de resposta mais simples se necessário.
def _enviar_requisicao(
    endereco_base: str,
    dados_requisicao: dict,
    tempo_limite: int
) -> tuple[str, str]:

    modos = (
        "json_schema",
        "json_object",
        "plain"
    )

    ultimo_erro: Exception | None = None

    for modo in modos:
        corpo = dict(dados_requisicao)

        if modo == "json_schema":
            corpo["response_format"] = _formato_resposta(
                corpo.pop("_max_candidates")
            )

        elif modo == "json_object":
            corpo.pop("_max_candidates", None)
            corpo["response_format"] = {
                "type": "json_object"
            }

        else:
            corpo.pop("_max_candidates", None)

        try:
            resposta = requests.post(
                endereco_base + "/v1/chat/completions",
                json=corpo,
                timeout=tempo_limite
            )

            if (
                modo != "plain"
                and resposta.status_code in {400, 404, 415, 422}
            ):
                ultimo_erro = requests.HTTPError(
                    f"response_format {modo} não suportado: HTTP {resposta.status_code}"
                )
                continue

            resposta.raise_for_status()

            return (
                resposta.json()["choices"][0]["message"]["content"],
                modo
            )

        except requests.RequestException as exc:
            ultimo_erro = exc

            if modo == "plain":
                raise

    if ultimo_erro:
        raise ultimo_erro

    raise RuntimeError(
        "falha inesperada na chamada ao teacher"
    )


def _parece_item_lista(texto: str) -> bool:
    t = (texto or "").lstrip()

    return bool(
        re.match(
            r"(?is)^(?:[a-z]\)|\d+[.)])\s+",
            t
        )
    )


def _eh_ordem_principal(texto: str) -> bool:
    n = normalizar(texto or "")

    return bool(
        (texto or "").rstrip().endswith(":")
        and any(
            v in n
            for v in (
                "determino",
                "defiro",
                "indefiro",
                "condeno",
                "fixo",
                "homologo",
                "intime",
                "proceda",
                "promova",
                "adote",
                "observe",
                "considere",
            )
        )
    )


# Se o modelo escolher somente itens de uma lista, inclui a ordem que dá sentido a eles.
def _expandir_unidades_pai(
    ids: list[str],
    unidades
) -> list[str]:

    unidade_por_id = {
        u.id_unidade: u
        for u in unidades
    }

    posicao_por_id = {
        u.id_unidade: i
        for i, u in enumerate(unidades)
    }

    validos = [
        x
        for x in ids
        if x in unidade_por_id
    ]

    if not validos:
        return []

    ids_ordenados = sorted(
        dict.fromkeys(validos),
        key=lambda x: posicao_por_id[x]
    )

    primeira_unidade = unidade_por_id[ids_ordenados[0]]

    if _parece_item_lista(primeira_unidade.texto):
        i = posicao_por_id[primeira_unidade.id_unidade]

        if i > 0:
            unidade_anterior = unidades[i - 1]

            if (
                unidade_anterior.rejeitada is None
                and _eh_ordem_principal(unidade_anterior.texto)
            ):
                ids_ordenados.insert(
                    0,
                    unidade_anterior.id_unidade
                )

    return ids_ordenados


# Corrige categorias claramente incompatíveis com o conteúdo selecionado.
def _normalizar_categoria(
    categoria: str,
    ids: list[str],
    unidades
) -> str:

    texto = "\n".join(
        u.texto
        for u in unidades
        if u.id_unidade in set(ids)
    )

    n = normalizar(texto)
    categoria_final = categoria

    if (
        categoria_final == "tutela"
        and not any(
            k in n
            for k in (
                "tutela",
                "liminar",
                "cautelar",
                "efeito suspensivo",
                "suspendo",
                "suspensao"
            )
        )
    ):
        if any(
            k in n
            for k in (
                "habilit",
                "assistente tecnico",
                "perito",
                "pericia"
            )
        ):
            categoria_final = "ordem_determinacao"

    return categoria_final


# Valida a saída do modelo antes de transformá-la em resultado do projeto.
def _validar_itens(
    itens: list[dict],
    unidades_visiveis,
    todas_unidades,
    maximo_candidatos: int
) -> list[dict]:

    ids_validos = {
        u.id_unidade
        for u in unidades_visiveis
    }

    saida: list[dict] = []
    ja_processados: set[tuple] = set()

    for item in itens:
        ids_brutos = item.get(
            "unit_ids",
            []
        )

        if isinstance(
            ids_brutos,
            str
        ):
            ids_brutos = [
                ids_brutos
            ]

        if not isinstance(
            ids_brutos,
            list
        ):
            continue

        ids = [
            str(x)
            for x in ids_brutos
            if str(x) in ids_validos
        ]

        ids = _expandir_unidades_pai(
            ids,
            todas_unidades
        )

        ids = [
            x
            for x in ids
            if x in ids_validos
        ]

        categoria_final = item.get(
            "category"
        )

        if (
            not ids
            or categoria_final not in CATEGORIAS
        ):
            continue

        categoria_final = _normalizar_categoria(
            categoria_final,
            ids,
            todas_unidades
        )

        try:
            prioridade = int(
                item.get(
                    "priority",
                    3
                )
            )
        except Exception:
            prioridade = 3

        prioridade = max(
            1,
            min(
                4,
                prioridade
            )
        )

        chave = (
            tuple(ids),
            categoria_final
        )

        if chave in ja_processados:
            continue

        ja_processados.add(
            chave
        )

        saida.append({
            "unit_ids": ids,
            "category": categoria_final,
            "priority": prioridade,
            "reason": str(
                item.get(
                    "reason",
                    ""
                )
            )[:300],
        })

        if len(saida) >= maximo_candidatos:
            break

    return saida


#  monta o contexto, chama o Qwen e devolve os recortes validados.
def chamar_modelo(
    registro,
    unidades,
    roteamento,
    regra_encontrada,
    maximo_candidatos=3
) -> ResultadoModelo:

    endereco_base = os.getenv(
        "DIDE1_LLM_BASE_URL",
        "http://127.0.0.1:8081"
    ).rstrip("/")

    modelo = os.getenv(
        "DIDE1_LLM_MODEL",
        "Qwen3.5-9B"
    )

    tempo_limite = int(
        os.getenv(
            "DIDE1_LLM_TIMEOUT",
            "180"
        )
    )

    novas_tentativas = max(
        0,
        int(
            os.getenv(
                "DIDE1_LLM_RETRIES",
                "1"
            )
        )
    )

    # Só envia ao modelo as unidades que passaram pelos filtros anteriores.
    unidades_visiveis = [
        u
        for u in unidades
        if not u.rejeitada
    ]

    # Cada trecho recebe um ID. O modelo escolhe IDs em vez de reescrever a decisão.
    texto_unidades = "\n".join(
        f"[{u.id_unidade}] ({u.secao}) {u.texto}"
        for u in unidades_visiveis
    )

    # Se uma regra determinística tiver sido identificada, ela é enviada como contexto.
    dica_regra = (
        None
        if regra_encontrada is None
        else {
            "rule_id": regra_encontrada.id_regra,
            "label": regra_encontrada.rotulo
        }
    )

    mensagem_usuario = {
        "contexto": {
            "processo": registro.get(
                "processo"
            ),
            "classe": registro.get(
                "classe"
            ),
            "orgao_julgador": registro.get(
                "orgao_julgador"
            ),
            "expediente": registro.get(
                "expediente"
            ),
            "assunto": registro.get(
                "assunto"
            ),
            "secao_subsecao": registro.get(
                "secao_subsecao"
            ),
            "nucleo": registro.get(
                "nucleo"
            ),
            "routing": roteamento,
            "regra_previa": dica_regra,
        },

        "categorias_permitidas": CATEGORIAS,

        "unidades": texto_unidades,

        "formato": {
            "selected": [
                {
                    "unit_ids": [
                        "U0001"
                    ],
                    "category": "uma categoria permitida",
                    "priority": 1,
                    "reason": "curto"
                }
            ]
        },
    }

    mensagens_base = [
        {
            "role": "system",
            "content": PROMPT_SISTEMA.format(
                maximo_candidatos=maximo_candidatos
            )
        },
        {
            "role": "user",
            "content": json.dumps(
                mensagem_usuario,
                ensure_ascii=False
            )
        },
    ]

    ultimo_erro: Exception | None = None

    for tentativa in range(
        1,
        novas_tentativas + 2
    ):
        mensagens = list(
            mensagens_base
        )

        if tentativa > 1:
            mensagens.append({
                "role": "user",
                "content": PROMPT_NOVA_TENTATIVA
            })

        # Temperatura zero ajuda a reduzir variação entre execuções.
        dados_requisicao = {
            "model": modelo,
            "messages": mensagens,
            "temperature": 0.0,
            "top_p": 0.9,
            "max_tokens": 900,
            "_max_candidates": maximo_candidatos,
        }

        try:
            conteudo, modo = _enviar_requisicao(
                endereco_base,
                dados_requisicao,
                tempo_limite
            )

            dados = _ler_json(
                conteudo
            )

            itens, observacao = _extrair_selecoes(
                dados
            )

            selecionados = _validar_itens(
                itens,
                unidades_visiveis,
                unidades,
                maximo_candidatos
            )

            situacao = (
                "RETRY_OK"
                if tentativa > 1
                else (
                    "EMPTY_VALID"
                    if not selecionados
                    else "OK"
                )
            )

            return ResultadoModelo(
                selecionados=selecionados,
                situacao=situacao,
                tentativas=tentativa,
                modo_resposta=modo,
                observacao_leitura=observacao
            )

        except (
            ErroLeituraModelo,
            KeyError,
            TypeError,
            ValueError,
            requests.RequestException
        ) as exc:
            ultimo_erro = exc
            continue

    if ultimo_erro:
        raise ultimo_erro

    raise ErroLeituraModelo(
        "falha não especificada no teacher"
    )
