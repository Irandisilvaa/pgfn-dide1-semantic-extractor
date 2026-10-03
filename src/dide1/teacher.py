from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Any

import requests

from .constants import CATEGORIES
from .text_utils import norm

SYSTEM = """Você é o teacher local do projeto DIDE1/PGFN. Sua função é selecionar, de modo conservador, unidades textuais da DECISÃO ATUAL que contenham informação juridicamente acionável para a triagem/defesa cível.

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
10) Retorne no máximo {max_candidates} seleções.
11) Retorne JSON puro, sem markdown, preferencialmente no formato {{"selected": [...]}}.
"""

RETRY_SUFFIX = """Sua resposta precisa ser JSON válido e conter apenas seleções baseadas nos IDs fornecidos. Use exatamente o formato {"selected":[{"unit_ids":["U0001"],"category":"ordem_determinacao","priority":1,"reason":"curto"}]}. Se não houver recorte válido, use {"selected":[]}."""


class TeacherParseError(ValueError):
    pass


@dataclass
class TeacherResult:
    selected: list[dict]
    status: str
    attempts: int
    response_mode: str
    parse_note: str = ""


def _parse_json(text: str) -> Any:
    """Parse JSON tolerando fences e um pequeno prefixo/sufixo textual."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    if not text:
        raise TeacherParseError("resposta vazia")
    try:
        return json.loads(text)
    except Exception:
        decoder = json.JSONDecoder()
        starts = [i for i, ch in enumerate(text) if ch in "[{"]
        for i in starts:
            try:
                obj, _ = decoder.raw_decode(text[i:])
                return obj
            except Exception:
                continue
        raise TeacherParseError("resposta sem JSON decodificável")


def _extract_selected(data: Any) -> tuple[list[dict], str]:
    """Aceita tanto {selected:[...]} quanto [...] diretamente."""
    if isinstance(data, list):
        raw = data
        note = "top_level_list"
    elif isinstance(data, dict):
        raw = data.get("selected", [])
        note = "selected_object"
    else:
        raise TeacherParseError(f"tipo JSON inesperado: {type(data).__name__}")

    if raw is None:
        return [], note
    if isinstance(raw, dict):
        raw = [raw]
        note += ":single_object_wrapped"
    if not isinstance(raw, list):
        raise TeacherParseError("campo selected não é lista")

    items = [x for x in raw if isinstance(x, dict)]
    return items, note


def _response_format(max_candidates: int) -> dict:
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
                        "maxItems": max_candidates,
                        "items": {
                            "type": "object",
                            "properties": {
                                "unit_ids": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string"},
                                },
                                "category": {"type": "string", "enum": list(CATEGORIES)},
                                "priority": {"type": "integer", "minimum": 1, "maximum": 4},
                                "reason": {"type": "string"},
                            },
                            "required": ["unit_ids", "category", "priority", "reason"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["selected"],
                "additionalProperties": False,
            },
        },
    }


def _post_completion(base: str, payload: dict, timeout: int) -> tuple[str, str]:
    """Tenta JSON Schema; se o servidor não suportar, recua para JSON object e depois plain."""
    modes = ("json_schema", "json_object", "plain")
    last_exc: Exception | None = None
    for mode in modes:
        body = dict(payload)
        if mode == "json_schema":
            body["response_format"] = _response_format(body.pop("_max_candidates"))
        elif mode == "json_object":
            body.pop("_max_candidates", None)
            body["response_format"] = {"type": "json_object"}
        else:
            body.pop("_max_candidates", None)
        try:
            r = requests.post(base + "/v1/chat/completions", json=body, timeout=timeout)
            # 400/404/422 podem indicar response_format não suportado pelo build local.
            if mode != "plain" and r.status_code in {400, 404, 415, 422}:
                last_exc = requests.HTTPError(f"response_format {mode} não suportado: HTTP {r.status_code}")
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"], mode
        except requests.RequestException as exc:
            last_exc = exc
            if mode == "plain":
                raise
    if last_exc:
        raise last_exc
    raise RuntimeError("falha inesperada na chamada ao teacher")


def _is_list_like(text: str) -> bool:
    t = (text or "").lstrip()
    return bool(re.match(r"(?is)^(?:[a-z]\)|\d+[.)])\s+", t))


def _is_action_parent(text: str) -> bool:
    n = norm(text or "")
    return bool(
        (text or "").rstrip().endswith(":")
        and any(v in n for v in (
            "determino", "defiro", "indefiro", "condeno", "fixo", "homologo",
            "intime", "proceda", "promova", "adote", "observe", "considere",
        ))
    )


def _expand_parent_units(ids: list[str], units) -> list[str]:
    """Inclui a ordem-mãe quando o modelo seleciona apenas a lista subordinada."""
    by_id = {u.unit_id: u for u in units}
    index = {u.unit_id: i for i, u in enumerate(units)}
    valid = [x for x in ids if x in by_id]
    if not valid:
        return []
    ordered = sorted(dict.fromkeys(valid), key=lambda x: index[x])
    first = by_id[ordered[0]]
    if _is_list_like(first.text):
        i = index[first.unit_id]
        if i > 0:
            prev = units[i - 1]
            if prev.rejected is None and _is_action_parent(prev.text):
                ordered.insert(0, prev.unit_id)
    return ordered


def _normalize_category(category: str, ids: list[str], units) -> str:
    """Correções semânticas conservadoras para categorias obviamente incompatíveis."""
    text = "\n".join(u.text for u in units if u.unit_id in set(ids))
    n = norm(text)
    cat = category
    # 'defiro habilitação de assistente técnico' não é tutela provisória.
    if cat == "tutela" and not any(k in n for k in ("tutela", "liminar", "cautelar", "efeito suspensivo", "suspendo", "suspensao")):
        if any(k in n for k in ("habilit", "assistente tecnico", "perito", "pericia")):
            cat = "ordem_determinacao"
    return cat


def _validate_items(items: list[dict], visible, all_units, max_candidates: int) -> list[dict]:
    valid_ids = {u.unit_id for u in visible}
    out: list[dict] = []
    seen: set[tuple] = set()

    for item in items:
        raw_ids = item.get("unit_ids", [])
        if isinstance(raw_ids, str):
            raw_ids = [raw_ids]
        if not isinstance(raw_ids, list):
            continue
        ids = [str(x) for x in raw_ids if str(x) in valid_ids]
        ids = _expand_parent_units(ids, all_units)
        # Expansão só pode usar unidades visíveis/não rejeitadas.
        ids = [x for x in ids if x in valid_ids]
        cat = item.get("category")
        if not ids or cat not in CATEGORIES:
            continue
        cat = _normalize_category(cat, ids, all_units)
        try:
            priority = int(item.get("priority", 3))
        except Exception:
            priority = 3
        priority = max(1, min(4, priority))
        key = (tuple(ids), cat)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "unit_ids": ids,
            "category": cat,
            "priority": priority,
            "reason": str(item.get("reason", ""))[:300],
        })
        if len(out) >= max_candidates:
            break
    return out


def call_llama(record, units, routing, rule_match, max_candidates=3) -> TeacherResult:
    base = os.getenv("DIDE1_LLM_BASE_URL", "http://127.0.0.1:8081").rstrip("/")
    model = os.getenv("DIDE1_LLM_MODEL", "Qwen3.5-9B")
    timeout = int(os.getenv("DIDE1_LLM_TIMEOUT", "180"))
    retries = max(0, int(os.getenv("DIDE1_LLM_RETRIES", "1")))

    visible = [u for u in units if not u.rejected]
    unit_text = "\n".join(f"[{u.unit_id}] ({u.section}) {u.text}" for u in visible)
    rule_hint = None if rule_match is None else {"rule_id": rule_match.rule_id, "label": rule_match.label}
    user = {
        "contexto": {
            "processo": record.get("processo"),
            "classe": record.get("classe"),
            "orgao_julgador": record.get("orgao_julgador"),
            "expediente": record.get("expediente"),
            "assunto": record.get("assunto"),
            "secao_subsecao": record.get("secao_subsecao"),
            "nucleo": record.get("nucleo"),
            "routing": routing,
            "regra_previa": rule_hint,
        },
        "categorias_permitidas": CATEGORIES,
        "unidades": unit_text,
        "formato": {"selected": [{"unit_ids": ["U0001"], "category": "uma categoria permitida", "priority": 1, "reason": "curto"}]},
    }

    base_messages = [
        {"role": "system", "content": SYSTEM.format(max_candidates=max_candidates)},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]

    last_exc: Exception | None = None
    for attempt in range(1, retries + 2):
        messages = list(base_messages)
        if attempt > 1:
            messages.append({"role": "user", "content": RETRY_SUFFIX})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "top_p": 0.9,
            "max_tokens": 900,
            "_max_candidates": max_candidates,
        }
        try:
            content, mode = _post_completion(base, payload, timeout)
            data = _parse_json(content)
            items, note = _extract_selected(data)
            selected = _validate_items(items, visible, units, max_candidates)
            status = "RETRY_OK" if attempt > 1 else ("EMPTY_VALID" if not selected else "OK")
            return TeacherResult(selected=selected, status=status, attempts=attempt, response_mode=mode, parse_note=note)
        except (TeacherParseError, KeyError, TypeError, ValueError, requests.RequestException) as exc:
            last_exc = exc
            continue

    if last_exc:
        raise last_exc
    raise TeacherParseError("falha não especificada no teacher")
