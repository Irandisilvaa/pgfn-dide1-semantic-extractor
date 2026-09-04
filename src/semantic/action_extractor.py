from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, replace
from typing import Iterable

from .deterministic_filters import (
    heuristic_score,
    infer_category_hint,
    low_value_reason,
)
from .local_llm import LocalLLMClient
from .segmenter import TextUnit, group_units, make_units


ALLOWED_CATEGORIES = {
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
}


SYSTEM_PROMPT = """
Você atua como FILTRO EXTRATIVO de decisões judiciais para apoio à
Procuradoria-Geral da Fazenda Nacional.

OBJETIVO:
Selecionar somente passagens do próprio documento que possam ajudar um
procurador a saber, avaliar ou fazer algo.

PERGUNTA CENTRAL:
"Este próprio trecho contém uma conclusão, ordem, prazo, consequência,
obrigação, manifestação, resultado ou outro fato operacional concreto?"

PRIORIDADE:
5 = consequência operacional direta/importante para PGFN/Fazenda/União.
4 = consequência processual relevante.
3 = informação potencialmente útil sem providência imediata.
1-2 = relevância residual; normalmente não selecionar.

NÃO selecionar:
- cabeçalho;
- identificação isolada;
- data/hora;
- assinatura;
- simples narrativa de pedido/alegação;
- transcrição normativa sem consequência concreta;
- frase preparatória que apenas introduz o próximo trecho;
- comando genérico isolado como "Cumpra-se";
- texto apenas porque contém linguagem jurídica.

ATOMICIDADE:
Cada candidato selecionado nesta etapa deve conter EXATAMENTE UM ID.

REGRAS:
1. Não reescreva o trecho.
2. Não invente IDs.
3. Não use conhecimento externo.
4. Não é necessário preencher o máximo.
5. Responda SOMENTE JSON válido.
""".strip()


CHUNK_PROMPT = """
Analise as unidades abaixo.

Formato:
[ID][SECAO=...] texto

Selecione NO MÁXIMO {max_candidates} unidades realmente acionáveis.

Categorias permitidas:
resultado_julgamento
ordem_determinacao
intimacao_manifestacao
tutela
obrigacao
prazo_cumprimento
restituicao_pagamento
honorarios_custas
recurso_proximo_passo
prescricao_decadencia
reconhecimento_concordancia
outro_acionavel

Retorne SOMENTE:
{{
  "recortes": [
    {{
      "id": "P0001",
      "categoria": "ordem_determinacao",
      "prioridade": 5
    }}
  ]
}}

Cada objeto deve conter UM ÚNICO id.
Se nada for acionável: {{"recortes":[]}}.

UNIDADES:
{units}
""".strip()


VALIDATOR_PROMPT = """
Avalie SOMENTE os candidatos literais abaixo.

MANter=true somente se o próprio texto:
- contém ação, consequência, resultado, prazo, obrigação, intimação,
  manifestação, tutela, pagamento/restituição, recurso, prescrição,
  honorários/custas ou outro fato operacional concreto; E
- é compreensível o suficiente para ser mostrado ao procurador.

MANter=false se:
- for cabeçalho/data/assinatura/identificação;
- for frase preparatória;
- for fragmento incompleto;
- for simples narrativa do pedido/alegação;
- for comando genérico isolado.

Retorne TODOS os candidatos recebidos, sem omitir nenhum.

Formato:
{{
  "avaliacoes": [
    {{
      "candidate": "C01",
      "manter": true,
      "relevancia": 5
    }}
  ]
}}

CANDIDATOS:
{candidates}
""".strip()


FINAL_PROMPT = """
Escolha NO MÁXIMO {top_k} candidatos para mostrar ao procurador.

PREFIRA:
1. ordem/intimação/prazo/manifestaçao dirigida à PFN/PGFN/Fazenda/União;
2. obrigação concreta;
3. tutela com efeito concreto;
4. resultado do julgamento;
5. recurso, trânsito, arquivamento ou próximo passo;
6. honorários/custas e demais consequências operacionais.

Regras:
- prefira DISPOSITIVO quando houver conteúdo acionável equivalente;
- evite narrativa do relatório;
- evite redundância;
- mantenha ações independentes separadas;
- não é obrigatório preencher {top_k} posições.

Retorne SOMENTE:
{{
  "selecionados": ["C01", "C02"]
}}

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
    validator_relevance: int
    validator_status: str
    heuristic_score: float
    context_expanded: bool = False


class ActionOrientedExtractor:
    def __init__(
        self,
        client: LocalLLMClient,
        *,
        max_candidates_per_chunk: int = 4,
        max_chunk_chars: int = 3000,
        max_unit_chars: int = 1000,
        temperature: float = 0.0,
        validator_batch_size: int = 6,
        max_global_candidates: int = 30,
        enable_context_expansion: bool = True,
    ):
        self.client = client
        self.max_candidates_per_chunk = max_candidates_per_chunk
        self.max_chunk_chars = max_chunk_chars
        self.max_unit_chars = max_unit_chars
        self.temperature = temperature
        self.validator_batch_size = max(
            1,
            int(validator_batch_size),
        )
        self.max_global_candidates = max(
            1,
            int(max_global_candidates),
        )
        self.enable_context_expansion = enable_context_expansion

    def extract(
        self,
        decision: str,
        *,
        top_k: int = 3,
    ) -> dict:
        units = make_units(
            decision,
            max_unit_chars=self.max_unit_chars,
        )
        by_id = {u.id: u for u in units}
        by_index = {u.index: u for u in units}
        chunks = group_units(
            units,
            max_chunk_chars=self.max_chunk_chars,
        )

        filter_reasons: Counter[str] = Counter()
        eligible_ids: set[str] = set()

        for unit in units:
            reason = low_value_reason(unit.text)

            if reason:
                filter_reasons[reason] += 1
            else:
                eligible_ids.add(unit.id)

        raw_candidates: list[SemanticCandidate] = []
        invalid_ids = 0
        post_filter_rejected = 0

        for chunk in chunks:
            selectable = [
                unit
                for unit in chunk
                if unit.id in eligible_ids
            ]

            if not selectable:
                continue

            rendered = "\n\n".join(
                f"[{u.id}][SECAO={u.section}] {u.text}"
                for u in selectable
            )

            payload = self.client.chat_json(
                system=SYSTEM_PROMPT,
                user=CHUNK_PROMPT.format(
                    max_candidates=self.max_candidates_per_chunk,
                    units=rendered,
                ),
                temperature=self.temperature,
                max_tokens=420,
            )

            for item in payload.get("recortes", []):
                unit_id = str(item.get("id", "")).strip()

                if unit_id not in by_id:
                    invalid_ids += 1
                    continue

                unit = by_id[unit_id]

                reason = low_value_reason(unit.text)
                if reason:
                    filter_reasons[f"post_{reason}"] += 1
                    post_filter_rejected += 1
                    continue

                try:
                    priority = int(item.get("prioridade", 3))
                except Exception:
                    priority = 3

                priority = max(1, min(5, priority))

                category = str(
                    item.get("categoria", "outro_acionavel")
                ).strip()

                if category not in ALLOWED_CATEGORIES:
                    category = "outro_acionavel"

                hint = infer_category_hint(unit.text)
                if hint:
                    category = hint

                candidate = SemanticCandidate(
                    unit_ids=[unit.id],
                    text=unit.text,
                    category=category,
                    priority=priority,
                    section=unit.section,
                    validator_relevance=0,
                    validator_status="NOT_RUN",
                    heuristic_score=heuristic_score(
                        text=unit.text,
                        section=unit.section,
                        model_priority=priority,
                    ),
                    context_expanded=False,
                )

                if self.enable_context_expansion:
                    candidate = self._expand_context_if_needed(
                        candidate,
                        by_id=by_id,
                        by_index=by_index,
                    )

                raw_candidates.append(candidate)

        # dedup por combinação exata de IDs
        best: dict[tuple[str, ...], SemanticCandidate] = {}

        for candidate in raw_candidates:
            key = tuple(candidate.unit_ids)
            prev = best.get(key)

            if (
                prev is None
                or (candidate.priority, candidate.heuristic_score)
                > (prev.priority, prev.heuristic_score)
            ):
                best[key] = candidate

        candidates = list(best.values())

        candidates.sort(
            key=lambda c: (
                -c.heuristic_score,
                -c.priority,
                c.unit_ids[0],
            )
        )

        candidates = candidates[: self.max_global_candidates]
        before_validator = len(candidates)

        (
            candidates,
            validator_rejected,
            validator_failed,
        ) = self._validate_in_batches(candidates)

        # Recalcula score com relevância do validador.
        rescored: list[SemanticCandidate] = []

        for candidate in candidates:
            score = heuristic_score(
                text=candidate.text,
                section=candidate.section,
                model_priority=candidate.priority,
                validator_relevance=candidate.validator_relevance,
            )
            rescored.append(
                replace(
                    candidate,
                    heuristic_score=score,
                )
            )

        candidates = rescored
        candidates.sort(
            key=lambda c: (
                c.validator_status != "PASSED",
                -c.validator_relevance,
                -c.heuristic_score,
                -c.priority,
                c.unit_ids[0],
            )
        )

        if len(candidates) > top_k:
            candidates = self._rerank(
                candidates,
                top_k=top_k,
            )

        return {
            "recortes": [
                asdict(c)
                for c in candidates[:top_k]
            ],
            "n_units": len(units),
            "n_chunks": len(chunks),
            "n_eligible_units": len(eligible_ids),
            "filtered_units": sum(filter_reasons.values()),
            "filter_reasons": dict(filter_reasons),
            "n_candidates_before_validator": before_validator,
            "validator_rejected": validator_rejected,
            "validator_failed": validator_failed,
            "rejected_invalid_ids": invalid_ids,
            "rejected_post_filter": post_filter_rejected,
        }

    def _needs_next_context(self, text: str) -> bool:
        stripped = text.strip()
        lower = stripped.lower()

        if stripped.endswith(":"):
            # Só expande se a frase contém decisão forte.
            return any(
                word in lower
                for word in (
                    "homologo",
                    "julgo",
                    "determino",
                    "condeno",
                    "declaro",
                )
            )

        return False

    def _expand_context_if_needed(
        self,
        candidate: SemanticCandidate,
        *,
        by_id: dict[str, TextUnit],
        by_index: dict[int, TextUnit],
    ) -> SemanticCandidate:
        if not self._needs_next_context(candidate.text):
            return candidate

        unit = by_id[candidate.unit_ids[0]]
        nxt = by_index.get(unit.index + 1)

        if nxt is None:
            return candidate

        if low_value_reason(nxt.text):
            return candidate

        combined = f"{candidate.text}\n{nxt.text}".strip()

        if len(combined) > 1800:
            return candidate

        return replace(
            candidate,
            unit_ids=[unit.id, nxt.id],
            text=combined,
            context_expanded=True,
        )

    def _validate_batch(
        self,
        candidates: list[SemanticCandidate],
    ) -> tuple[list[SemanticCandidate], int, int]:
        """
        Retorna (mantidos, rejeitados, falhas_individuais).

        Se um lote falhar, divide recursivamente.
        Se até um candidato isolado falhar, ele é mantido com status ERROR
        para não mascarar a falha como validação positiva.
        """
        if not candidates:
            return [], 0, 0

        mapping: dict[str, SemanticCandidate] = {}
        rendered: list[str] = []

        for i, candidate in enumerate(candidates, start=1):
            cid = f"C{i:02d}"
            mapping[cid] = candidate
            rendered.append(
                f"[{cid}] secao={candidate.section}; "
                f"categoria={candidate.category}; "
                f"prioridade={candidate.priority}\n"
                f"{candidate.text}"
            )

        try:
            payload = self.client.chat_json(
                system=SYSTEM_PROMPT,
                user=VALIDATOR_PROMPT.format(
                    candidates="\n\n".join(rendered),
                ),
                temperature=self.temperature,
                max_tokens=500,
            )

            evaluations = payload.get("avaliacoes", [])

            if not isinstance(evaluations, list):
                raise RuntimeError(
                    "Campo avaliacoes inválido."
                )

            by_candidate = {
                str(item.get("candidate", "")).strip(): item
                for item in evaluations
                if isinstance(item, dict)
            }

            # O prompt exige que todos sejam devolvidos.
            if any(cid not in by_candidate for cid in mapping):
                raise RuntimeError(
                    "Validador omitiu candidato(s)."
                )

            kept: list[SemanticCandidate] = []
            rejected = 0

            for cid, candidate in mapping.items():
                item = by_candidate[cid]
                keep = bool(item.get("manter", False))

                try:
                    relevance = int(
                        item.get("relevancia", 3)
                    )
                except Exception:
                    relevance = 3

                relevance = max(1, min(5, relevance))

                if keep:
                    kept.append(
                        replace(
                            candidate,
                            validator_relevance=relevance,
                            validator_status="PASSED",
                        )
                    )
                else:
                    rejected += 1

            return kept, rejected, 0

        except Exception:
            if len(candidates) > 1:
                middle = len(candidates) // 2
                left = self._validate_batch(
                    candidates[:middle]
                )
                right = self._validate_batch(
                    candidates[middle:]
                )

                return (
                    left[0] + right[0],
                    left[1] + right[1],
                    left[2] + right[2],
                )

            candidate = candidates[0]
            return [
                replace(
                    candidate,
                    validator_relevance=0,
                    validator_status="ERROR",
                )
            ], 0, 1

    def _validate_in_batches(
        self,
        candidates: list[SemanticCandidate],
    ) -> tuple[list[SemanticCandidate], int, int]:
        kept: list[SemanticCandidate] = []
        rejected = 0
        failed = 0

        for start in range(
            0,
            len(candidates),
            self.validator_batch_size,
        ):
            batch = candidates[
                start:start + self.validator_batch_size
            ]
            batch_kept, batch_rejected, batch_failed = (
                self._validate_batch(batch)
            )
            kept.extend(batch_kept)
            rejected += batch_rejected
            failed += batch_failed

        return kept, rejected, failed

    def _rerank(
        self,
        candidates: list[SemanticCandidate],
        *,
        top_k: int,
    ) -> list[SemanticCandidate]:
        mapping: dict[str, SemanticCandidate] = {}
        rendered: list[str] = []

        for i, candidate in enumerate(candidates, start=1):
            cid = f"C{i:02d}"
            mapping[cid] = candidate

            rendered.append(
                f"[{cid}] secao={candidate.section}; "
                f"categoria={candidate.category}; "
                f"prioridade={candidate.priority}; "
                f"validacao={candidate.validator_relevance}; "
                f"status={candidate.validator_status}; "
                f"score={candidate.heuristic_score}\n"
                f"{candidate.text}"
            )

        try:
            payload = self.client.chat_json(
                system=SYSTEM_PROMPT,
                user=FINAL_PROMPT.format(
                    top_k=top_k,
                    candidates="\n\n".join(rendered),
                ),
                temperature=self.temperature,
                max_tokens=220,
            )

            selected = [
                str(x).strip()
                for x in payload.get("selecionados", [])
            ]

            chosen: list[SemanticCandidate] = []
            seen: set[str] = set()

            for cid in selected:
                if cid in mapping and cid not in seen:
                    chosen.append(mapping[cid])
                    seen.add(cid)

            if chosen:
                return chosen[:top_k]

        except Exception:
            pass

        return candidates[:top_k]
