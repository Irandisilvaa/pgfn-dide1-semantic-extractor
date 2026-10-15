from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import re
import time

from .input_loader import iterar_registros
from .text_utils import normalizar
from .rules_jovaldo import classificar as classificar_jovaldo
from .segmenter import segmentar, reconstruir_texto_exato
from .router import rotear
from .teacher import chamar_modelo
from .workbook import escrever_planilha_revisao


INICIO_OPERATIVO = re.compile(
    r"^(?:\d+[.)]\s*)?(?:(?:diante|ante) do exposto[,;:]?\s*|isto posto[,;:]?\s*|por tais fundamentos[,;:]?\s*)?"
    r"(?:determino|defiro|indefiro|julgo|homologo|declaro|rejeito|condeno|extingo|acolho|"
    r"intime-se|intimem-se|notifique-se|cite-se|arquive-se|arquivem-se|remeta-se|remetam-se|"
    r"expeca-se|proceda|procedam|aguarde-se|mantenha-se|libere-se|suspenda-se|"
    r"ficam? as partes intimadas|vistas? (?:a|as|ao))\b",
    re.I,
)


def eh_execucao_fiscal(registro: dict) -> bool:
    return "execucao fiscal" in normalizar(registro.get("classe", ""))


def _hash_decisao(decisao: str) -> str:
    return hashlib.sha256((decisao or "").encode("utf-8", errors="replace")).hexdigest()


def _categoria_por_texto(texto: str) -> str:
    n = normalizar(texto)
    if any(v in n for v in ("julgo", "homologo", "declaro", "rejeito", "extingo", "acolho")):
        return "resultado_julgamento"
    if "honorario" in n or "custas" in n:
        return "honorarios_custas"
    if "prescri" in n or "decaden" in n:
        return "prescricao_decadencia"
    if any(v in n for v in ("intim", "notifi", "cit", "vista")):
        return "intimacao_manifestacao"
    if "arquiv" in n or "remeta" in n or "conclus" in n:
        return "recurso_proximo_passo"
    if "requisit" in n or "pagamento" in n or "precatorio" in n or "rpv" in n:
        return "restituicao_pagamento"
    return "ordem_determinacao"


def regras_heuristicas(unidades, maximo_candidatos=3):
    saida = []
    for u in unidades:
        if u.rejeitada:
            continue
        n = normalizar(u.texto)
        if INICIO_OPERATIVO.search(n):
            saida.append({
                "unit_ids": [u.id_unidade],
                "category": _categoria_por_texto(u.texto),
                "priority": 3,
                "reason": "deterministic rules fallback",
            })
        if len(saida) >= maximo_candidatos:
            break
    return saida


def _pontuacao_fallback(texto: str, rotulo: str) -> int:
    """Fallback propositalmente conservador: prefere perder um recorte a inventar ação em narrativa."""
    n = normalizar(texto)
    inicio_texto = n[:180]
    pontuacao = 0

    if INICIO_OPERATIVO.search(n):
        pontuacao += 4

    if "requisitorio" in rotulo and "requisit" in n and any(x in n for x in ("intim", "manifest", "pagamento", "exped")):
        pontuacao += 8
    if "contrarrazo" in rotulo and "contrarrazo" in n and any(x in n for x in ("intim", "manifest")):
        pontuacao += 8
    if "citacao" in rotulo and any(x in inicio_texto for x in ("cite-se", "citacao", "cita", "intim")):
        pontuacao += 8
    if "ato ordinatorio" in rotulo and any(x in inicio_texto for x in ("intim", "vista", "prazo", "arquiv")):
        pontuacao += 6
    if "sobrestamento" in rotulo and "sobrest" in inicio_texto:
        pontuacao += 8
    if "prescricao" in rotulo and "prescri" in inicio_texto and any(x in inicio_texto for x in ("declaro", "julgo", "reconhe")):
        pontuacao += 8
    if "sentenca" in rotulo and any(x in inicio_texto for x in ("julgo", "homologo", "declaro", "extingo", "rejeito", "acolho", "condeno")):
        pontuacao += 8

    # Evita narrativa típica que apareceu no piloto de 100 decisões.
    if inicio_texto.startswith(("sustenta ", "alega ", "a parte sustenta ", "a impetrante sustenta ", "a autora sustenta ")):
        return 0
    if "foi devidamente notificada" in inicio_texto or "culminou no ato declaratorio" in inicio_texto:
        pontuacao = max(0, pontuacao - 6)
    return pontuacao


def _fallback_regra(unidades, regra, maximo_candidatos=3):
    """Fallback conservador quando o teacher falha; nunca força narrativa apenas por haver regra Jovaldo."""
    rotulo = "" if regra is None else normalizar(regra.rotulo)
    preferidos = []
    for u in unidades:
        if u.rejeitada:
            continue
        pontuacao = _pontuacao_fallback(u.texto, rotulo)
        if pontuacao > 0:
            preferidos.append((pontuacao, u.inicio, u))

    preferidos.sort(key=lambda x: (-x[0], x[1]))
    saida = []
    for _, _, u in preferidos[:maximo_candidatos]:
        saida.append({
            "unit_ids": [u.id_unidade],
            "category": _categoria_por_texto(u.texto),
            "priority": 2,
            "reason": "rule fallback conservador" if regra is None else f"rule fallback: {regra.id_regra}/{regra.rotulo}",
        })
    return saida


def _linha_candidato(registro_atual, d, posicao, s, decisao, unidades, regra, roteamento, situacao_modelo, tentativas_modelo, modo_resposta_modelo, hash_decisao, cache_reutilizado):
    texto = reconstruir_texto_exato(decisao, s["unit_ids"], unidades)
    return {
        "source_row": registro_atual.linha_origem,
        "Processo": d.get("processo", ""),
        "candidate_rank": posicao,
        "unit_ids": json.dumps(s["unit_ids"], ensure_ascii=False),
        "candidate_text": texto,
        "teacher_category": s["category"],
        "teacher_priority": s["priority"],
        "teacher_reason": s.get("reason", ""),
        "rule_id": "" if regra is None else regra.id_regra,
        "rule_label": "" if regra is None else regra.rotulo,
        "route_key": roteamento["route_key"],
        "specialist": roteamento["specialist"],
        "teacher_status": situacao_modelo,
        "teacher_attempts": tentativas_modelo,
        "teacher_response_mode": modo_resposta_modelo,
        "decision_sha256": hash_decisao,
        "cache_hit": cache_reutilizado,
        "status_validacao": "",
        "texto_ajustado": "",
        "categoria_ajustada": "",
        "observacao": "",
        "revisor": "",
        "revisado_em": "",
    }


def executar(
    arquivo_entrada_xlsx: str,
    diretorio_saida: str,
    limite: int | None = None,
    indice_inicial: int = 0,
    aba: str | None = None,
    modo_modelo: str = "llama",
    maximo_candidatos: int = 3,
    incluir_execucao_fiscal: bool = False,
    limite_unicos: int | None = None,
):
    pasta_saida = Path(diretorio_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    caminho_predicoes = pasta_saida / "predictions.jsonl"
    caminho_erros = pasta_saida / "errors.jsonl"
    registros_saida = []
    candidatos_saida = []
    erros = []
    cache: dict[str, dict] = {}
    decisoes_unicas: set[str] = set()
    varridos = 0
    processados = 0
    acertos_cache = 0
    inferencias_unicas = 0
    tentativas_recuperadas = 0
    fallbacks_regra = 0
    fallback_regra_vazio = 0
    vazios_validos = 0
    decisoes_vazias_ignoradas = 0
    inicio_execucao = time.time()

    for indice, registro_atual in enumerate(iterar_registros(arquivo_entrada_xlsx, aba=aba)):
        if indice < indice_inicial:
            continue
        if limite is not None and varridos >= limite:
            break
        if limite_unicos is not None and len(decisoes_unicas) >= limite_unicos:
            break

        varridos += 1
        d = registro_atual.dados

        if (not incluir_execucao_fiscal) and eh_execucao_fiscal(d):
            registros_saida.append({
                "source_row": registro_atual.linha_origem, **d,
                "status_documento": "EXCLUIDO_EXECUCAO_FISCAL",
                "rule_label": "", "route_key": "", "teacher_recortes_count": 0,
                "teacher_status": "", "teacher_attempts": 0, "teacher_response_mode": "",
                "decision_sha256": "", "cache_hit": False,
            })
            continue

        decisao = d.get("decisao", "") or ""
        if not decisao.strip():
            decisoes_vazias_ignoradas += 1
            registros_saida.append({
                "source_row": registro_atual.linha_origem, **d,
                "status_documento": "SEM_DECISAO",
                "rule_label": "", "route_key": "", "teacher_recortes_count": 0,
                "teacher_status": "", "teacher_attempts": 0, "teacher_response_mode": "",
                "decision_sha256": "", "cache_hit": False,
            })
            continue

        hash_decisao = _hash_decisao(decisao)
        decisoes_unicas.add(hash_decisao)
        unidades = segmentar(decisao)
        regra = classificar_jovaldo(decisao, d.get("expediente", ""))
        roteamento = rotear(d)
        cache_reutilizado = False

        try:
            if modo_modelo == "llama" and hash_decisao in cache:
                registro_cache = cache[hash_decisao]
                selecionados = registro_cache["selected"]
                situacao_modelo = registro_cache["teacher_status"]
                tentativas_modelo = registro_cache["teacher_attempts"]
                modo_resposta_modelo = registro_cache["teacher_response_mode"]
                cache_reutilizado = True
                acertos_cache += 1
            elif modo_modelo == "llama":
                inferencias_unicas += 1
                try:
                    resultado = chamar_modelo(d, unidades, roteamento, regra, maximo_candidatos=maximo_candidatos)
                    selecionados = resultado.selecionados
                    situacao_modelo = resultado.situacao
                    tentativas_modelo = resultado.tentativas
                    modo_resposta_modelo = resultado.modo_resposta
                    if situacao_modelo == "RETRY_OK":
                        tentativas_recuperadas += 1
                    if situacao_modelo == "EMPTY_VALID":
                        vazios_validos += 1
                except Exception as erro_modelo:
                    selecionados = _fallback_regra(unidades, regra, maximo_candidatos=maximo_candidatos)
                    tentativas_modelo = int(os.getenv("DIDE1_LLM_RETRIES", "1")) + 1
                    modo_resposta_modelo = "fallback"
                    if selecionados:
                        situacao_modelo = "RULE_FALLBACK"
                        fallbacks_regra += 1
                    else:
                        situacao_modelo = "RULE_FALLBACK_EMPTY"
                        fallback_regra_vazio += 1
                    erros.append({
                        "source_row": registro_atual.linha_origem,
                        "processo": d.get("processo", ""),
                        "severity": "RECOVERED",
                        "teacher_status": situacao_modelo,
                        "error": repr(erro_modelo),
                    })
                cache[hash_decisao] = {
                    "selected": selecionados,
                    "teacher_status": situacao_modelo,
                    "teacher_attempts": tentativas_modelo,
                    "teacher_response_mode": modo_resposta_modelo,
                }
            elif modo_modelo == "rules":
                selecionados = regras_heuristicas(unidades, maximo_candidatos=maximo_candidatos)
                situacao_modelo = "EMPTY_VALID" if not selecionados else "OK"
                tentativas_modelo = 0
                modo_resposta_modelo = "rules"
            else:
                raise ValueError("teacher_mode deve ser 'llama' ou 'rules'")

            for posicao, s in enumerate(selecionados, start=1):
                candidatos_saida.append(_linha_candidato(
                    registro_atual, d, posicao, s, decisao, unidades, regra, roteamento,
                    situacao_modelo, tentativas_modelo, modo_resposta_modelo,
                    hash_decisao, cache_reutilizado,
                ))

            if not selecionados:
                candidatos_saida.append({
                    "source_row": registro_atual.linha_origem, "Processo": d.get("processo", ""), "candidate_rank": 0,
                    "unit_ids": "[]", "candidate_text": "", "teacher_category": "", "teacher_priority": "", "teacher_reason": "",
                    "rule_id": "" if regra is None else regra.id_regra, "rule_label": "" if regra is None else regra.rotulo,
                    "route_key": roteamento["route_key"], "specialist": roteamento["specialist"],
                    "teacher_status": situacao_modelo, "teacher_attempts": tentativas_modelo,
                    "teacher_response_mode": modo_resposta_modelo, "decision_sha256": hash_decisao,
                    "cache_hit": cache_reutilizado,
                    "status_validacao": "", "texto_ajustado": "", "categoria_ajustada": "", "observacao": "", "revisor": "", "revisado_em": "",
                })

            processados += 1
            registros_saida.append({
                "source_row": registro_atual.linha_origem, **d,
                "status_documento": "PENDENTE_REVISAO",
                "rule_id": "" if regra is None else regra.id_regra,
                "rule_label": "" if regra is None else regra.rotulo,
                "route_key": roteamento["route_key"],
                "specialist": roteamento["specialist"],
                "teacher_status": situacao_modelo,
                "teacher_attempts": tentativas_modelo,
                "teacher_response_mode": modo_resposta_modelo,
                "decision_sha256": hash_decisao,
                "cache_hit": cache_reutilizado,
                "teacher_recortes_count": len(selecionados),
                "observacao_documento": "", "revisor_documento": "", "revisado_em": "",
            })
        except Exception as e:
            erros.append({
                "source_row": registro_atual.linha_origem, "processo": d.get("processo", ""),
                "severity": "FATAL", "teacher_status": "ERROR", "error": repr(e),
            })
            registros_saida.append({
                "source_row": registro_atual.linha_origem, **d,
                "status_documento": "ERRO",
                "rule_id": "" if regra is None else regra.id_regra,
                "rule_label": "" if regra is None else regra.rotulo,
                "route_key": roteamento["route_key"], "specialist": roteamento["specialist"],
                "teacher_status": "ERROR", "teacher_attempts": 0, "teacher_response_mode": "",
                "decision_sha256": hash_decisao, "cache_hit": cache_reutilizado,
                "teacher_recortes_count": 0,
            })

    with caminho_predicoes.open("w", encoding="utf-8") as f:
        for x in candidatos_saida:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with caminho_erros.open("w", encoding="utf-8") as f:
        for x in erros:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    caminho_revisao = pasta_saida / "review.xlsx"
    escrever_planilha_revisao(caminho_revisao, registros_saida, candidatos_saida)
    erros_fatais = sum(1 for e in erros if e.get("severity") == "FATAL")
    erros_recuperados = sum(1 for e in erros if e.get("severity") == "RECOVERED")
    manifesto = {
        "version": "4.2.0-review-metrics",
        "input": str(arquivo_entrada_xlsx), "sheet": aba, "teacher_mode": modo_modelo,
        "start_index": indice_inicial, "limit": limite, "unique_limit": limite_unicos,
        "scanned": varridos, "processed": processados,
        "unique_decisions": len(decisoes_unicas),
        "errors": erros_fatais, "recovered_errors": erros_recuperados,
        "max_candidates": maximo_candidatos,
        "unique_inferences": inferencias_unicas,
        "cache_hits": acertos_cache,
        "teacher_retries_ok": tentativas_recuperadas,
        "rule_fallbacks": fallbacks_regra,
        "rule_fallback_empty": fallback_regra_vazio,
        "empty_valid": vazios_validos,
        "skipped_empty_decisions": decisoes_vazias_ignoradas,
        "elapsed_seconds": round(time.time() - inicio_execucao, 3),
        "review_workbook": str(caminho_revisao),
        "review_sheet": "revisao_consolidada",
        "metrics_sheet": "metricas",
    }
    (pasta_saida / "manifest.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifesto
