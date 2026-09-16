from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import re
from typing import Any

from .deterministic_filters import (
    effective_section,
    heuristic_score,
    infer_category_hint,
    low_value_reason,
)
from .local_llm import LocalLLMClient
from .segmenter import group_units, make_units


ALLOWED_CATEGORIES = [
    "resultado_julgamento",
    "ordem_determinacao",
    "intimacao_manifestacao",
    "tutela",
    "obrigacao",
    "prazo_cumprimento",
    "restituicao_pagamento",
    "honorarios_custas",
    "recurso_proximo_passo",
    "prescricao_decadencia",
    "reconhecimento_concordancia",
    "outro_acionavel",
]


SYSTEM_PROMPT = """
Você é um extrator de RECORTES ACIONÁVEIS de decisões judiciais brasileiras
para apoio humano à Procuradoria-Geral da Fazenda Nacional.

Sua função NÃO é resumir, interpretar o direito ou responder à decisão.
Sua função é escolher IDs de trechos que já existem no documento.

Um trecho é acionável quando, sozinho, comunica uma consequência concreta
da decisão: resultado do julgamento, ordem, intimação, prazo, obrigação,
tutela, pagamento/restituição, honorários/custas, recurso, trânsito,
arquivamento, prescrição ou providência processual relevante.

DISTINÇÃO OBRIGATÓRIA:
- "a parte requereu X" NÃO significa que o juiz determinou X;
- itens como "a) A concessão...", "a) DETERMINE..." e
  "ao final, seja julgado..." podem ser PEDIDOS DA PARTE, não decisão;
- "a decisão/sentença de id. X determinou..." pode apenas relatar ato anterior;
- "indeferiu-se ... no id. X" pode ser histórico, não comando atual;
- "Prazo 5 dias" ou "Cumpra-se com urgência" isolados não são autossuficientes;
- "a defesa alegou X" NÃO significa que X foi decidido;
- explicação abstrata de lei/jurisprudência NÃO é providência;
- prefira DISPOSITIVO e comandos efetivamente adotados AGORA pelo julgador.

REGRAS DE FIDELIDADE:
- selecione somente IDs fornecidos;
- não reescreva texto;
- não invente fatos;
- não use conhecimento externo;
- não é obrigatório selecionar nada;
- evite duplicidade e fragmentos genéricos.
""".strip()


CHUNK_PROMPT = """
Selecione no máximo {max_candidates} unidades acionáveis deste bloco.

Priorize:
1. DISPOSITIVO com ordem/conclusão concreta;
2. providência dirigida à PGFN/PFN/Fazenda Nacional/União;
3. prazo, obrigação ou próximo passo;
4. resultado, tutela, restituição/pagamento, honorários, prescrição.

Não selecione narrativa de pedido, alegação, juntada de documentos,
fundamentação abstrata, cabeçalho ou comando isolado sem conteúdo.
Rejeite também pedido enumerado da parte ("a) DETERMINE...", "seja julgado...")
e mera referência histórica a decisão/sentença anterior.

UNIDADES:
{units}
""".strip()


FINAL_PROMPT = """
Faça a adjudicação FINAL. Escolha no máximo {top_k} candidatos para mostrar
a um procurador.

Um candidato só deve permanecer se o próprio texto comunicar uma consequência
ou providência concreta adotada na decisão.

REJEITE especialmente:
- relato do que uma parte pediu/alegou;
- pedidos enumerados como "a) A concessão...", "a) DETERMINE...",
  "ao final, seja julgado..." quando não forem dispositivo judicial;
- relato histórico: "a decisão/sentença de id. X determinou...",
  "indeferiu-se ... no id. X";
- discussão abstrata de lei/jurisprudência;
- juntada de documentos;
- fragmento órfão como "Prazo 5 dias" ou "Cumpra-se com urgência";
- frase genérica sem efeito operacional;
- duplicata semântica/textual.

O SCORE é apenas heurístico e NÃO prova que o recorte é válido.
A semântica e a distinção pedido x decisão x histórico prevalecem.
Prefira candidatos do DISPOSITIVO quando houver equivalentes.

CANDIDATOS:
{candidates}
""".strip()


@dataclass
class SemanticCandidate:
    unit_ids: list[str]
    text: str
    category: str
    priority: int
    section: str
    heuristic_score: float
    rank: int = 0


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


class ActionOrientedExtractor:
    def __init__(
        self,
        client: LocalLLMClient,
        *,
        max_candidates_per_chunk: int = 4,
        max_chunk_chars: int = 5200,
        max_unit_chars: int = 1200,
        temperature: float = 0.2,
        max_global_candidates: int = 24,
    ):
        self.client = client
        self.max_candidates_per_chunk = max_candidates_per_chunk
        self.max_chunk_chars = max_chunk_chars
        self.max_unit_chars = max_unit_chars
        self.temperature = temperature
        self.max_global_candidates = max_global_candidates

    @staticmethod
    def _chunk_schema(valid_ids: list[str], max_candidates: int) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "recortes": {
                    "type": "array",
                    "maxItems": max_candidates,
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "enum": valid_ids},
                            "categoria": {
                                "type": "string",
                                "enum": ALLOWED_CATEGORIES,
                            },
                            "prioridade": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                            },
                        },
                        "required": ["id", "categoria", "prioridade"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["recortes"],
            "additionalProperties": False,
        }

    @staticmethod
    def _final_schema(valid_ids: list[str], top_k: int) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selecionados": {
                    "type": "array",
                    "maxItems": top_k,
                    "items": {
                        "type": "string",
                        "enum": valid_ids,
                    },
                }
            },
            "required": ["selecionados"],
            "additionalProperties": False,
        }

    def extract(self, decision: str, *, top_k: int = 3) -> dict[str, Any]:
        units = make_units(decision, max_unit_chars=self.max_unit_chars)
        by_id = {u.id: u for u in units}
        chunks = group_units(units, max_chunk_chars=self.max_chunk_chars)

        filter_reasons: Counter[str] = Counter()
        eligible_ids: set[str] = set()

        for unit in units:
            section = effective_section(unit.text, unit.section)
            reason = low_value_reason(unit.text, section=section)
            if reason:
                filter_reasons[reason] += 1
            else:
                eligible_ids.add(unit.id)

        raw: list[SemanticCandidate] = []
        llm_calls = 0

        for chunk in chunks:
            selectable = [u for u in chunk if u.id in eligible_ids]
            if not selectable:
                continue

            rendered = "\n\n".join(
                f"[{u.id}][SECAO={u.section}] {u.text}"
                for u in selectable
            )
            valid_ids = [u.id for u in selectable]

            payload = self.client.chat_json(
                system=SYSTEM_PROMPT,
                user=CHUNK_PROMPT.format(
                    max_candidates=self.max_candidates_per_chunk,
                    units=rendered,
                ),
                schema=self._chunk_schema(
                    valid_ids,
                    self.max_candidates_per_chunk,
                ),
                temperature=self.temperature,
                max_tokens=420,
            )
            llm_calls += 1

            for item in payload.get("recortes", []):
                uid = item["id"]
                unit = by_id[uid]
                section = effective_section(unit.text, unit.section)

                # Defesa em profundidade: revalida filtro no texto escolhido.
                reason = low_value_reason(unit.text, section=section)
                if reason:
                    filter_reasons[f"post_{reason}"] += 1
                    continue

                priority = int(item["prioridade"])
                category = str(item["categoria"])

                # Só sobrescreve quando a regra textual é inequívoca.
                hint = infer_category_hint(unit.text)
                if hint:
                    category = hint

                raw.append(
                    SemanticCandidate(
                        unit_ids=[uid],
                        text=unit.text,
                        category=category,
                        priority=priority,
                        section=section,
                        heuristic_score=heuristic_score(
                            text=unit.text,
                            section=section,
                            model_priority=priority,
                        ),
                    )
                )

        # Deduplicação por TEXTO normalizado (corrige duplicatas vindas de
        # unidades distintas/chunks sobrepostos).
        best_by_text: dict[str, SemanticCandidate] = {}
        for candidate in raw:
            key = _norm(candidate.text)
            prev = best_by_text.get(key)
            if (
                prev is None
                or (candidate.heuristic_score, candidate.priority)
                > (prev.heuristic_score, prev.priority)
            ):
                best_by_text[key] = candidate

        candidates = list(best_by_text.values())
        candidates.sort(
            key=lambda c: (
                -c.heuristic_score,
                -c.priority,
                c.unit_ids[0],
            )
        )
        candidates = candidates[: self.max_global_candidates]

        before_final = len(candidates)
        selected: list[SemanticCandidate] = []

        if candidates:
            mapping: dict[str, SemanticCandidate] = {}
            rendered: list[str] = []

            for i, candidate in enumerate(candidates, start=1):
                cid = f"C{i:02d}"
                mapping[cid] = candidate
                rendered.append(
                    f"[{cid}] SECAO={candidate.section}; "
                    f"CATEGORIA={candidate.category}; "
                    f"PRIORIDADE={candidate.priority}; "
                    f"SCORE={candidate.heuristic_score}\n"
                    f"{candidate.text}"
                )

            payload = self.client.chat_json(
                system=SYSTEM_PROMPT,
                user=FINAL_PROMPT.format(
                    top_k=top_k,
                    candidates="\n\n".join(rendered),
                ),
                schema=self._final_schema(list(mapping), top_k),
                temperature=self.temperature,
                max_tokens=180,
            )
            llm_calls += 1

            seen_text: set[str] = set()
            for cid in payload.get("selecionados", []):
                candidate = mapping[cid]
                key = _norm(candidate.text)
                if key in seen_text:
                    continue
                seen_text.add(key)
                selected.append(candidate)
                if len(selected) >= top_k:
                    break

        selected = [
            SemanticCandidate(
                unit_ids=c.unit_ids,
                text=c.text,
                category=c.category,
                priority=c.priority,
                section=c.section,
                heuristic_score=c.heuristic_score,
                rank=i,
            )
            for i, c in enumerate(selected, start=1)
        ]

        return {
            "recortes": [asdict(c) for c in selected],
            "n_units": len(units),
            "n_chunks": len(chunks),
            "n_eligible_units": len(eligible_ids),
            "filtered_units": sum(filter_reasons.values()),
            "filter_reasons": dict(filter_reasons),
            "n_candidates_before_final": before_final,
            "llm_calls": llm_calls,
        }
