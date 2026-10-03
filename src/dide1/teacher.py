import json
import os
import re
import requests
from .constants import CATEGORIES

SYSTEM = """Você é o teacher local do projeto DIDE1/PGFN. Sua função é selecionar, de modo conservador, unidades textuais da DECISÃO ATUAL que contenham informação juridicamente acionável para a triagem/defesa cível.

Regras obrigatórias:
1) Selecione somente IDs fornecidos. Nunca reescreva nem invente texto.
2) Priorize comando atual, resultado do julgamento, intimação/manifestações, tutela, obrigação, prazo, pagamento/restituição, honorários/custas, recurso/próximo passo, prescrição/decadência e reconhecimento/concordância.
3) NÃO selecione pedido da parte como se fosse decisão judicial.
4) NÃO selecione mera narrativa histórica de decisão anterior, citação de outro processo ou fundamentação sem efeito operacional atual.
5) O trecho precisa ser autocontido e acionável. Evite fragmentos órfãos.
6) Retorne no máximo {max_candidates} seleções.
7) Retorne JSON puro, sem markdown.
"""


def _parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
    try:
        return json.loads(text)
    except Exception:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a:
            return json.loads(text[a:b+1])
        raise


def call_llama(record, units, routing, rule_match, max_candidates=3):
    base = os.getenv("DIDE1_LLM_BASE_URL", "http://127.0.0.1:8081").rstrip("/")
    model = os.getenv("DIDE1_LLM_MODEL", "Qwen3.5-9B")
    timeout = int(os.getenv("DIDE1_LLM_TIMEOUT", "180"))
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
        "formato": {"selected": [{"unit_ids": ["U0001"], "category": "uma categoria permitida", "priority": 1, "reason": "curto"}]}
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM.format(max_candidates=max_candidates)},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        "temperature": 0.0,
        "top_p": 0.9,
        "max_tokens": 900,
    }
    r = requests.post(base + "/v1/chat/completions", json=payload, timeout=timeout)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    data = _parse_json(content)
    selected = data.get("selected", [])
    valid_ids = {u.unit_id for u in visible}
    out = []
    for item in selected[:max_candidates]:
        ids = [x for x in item.get("unit_ids", []) if x in valid_ids]
        cat = item.get("category")
        if not ids or cat not in CATEGORIES:
            continue
        try: priority = int(item.get("priority", 3))
        except Exception: priority = 3
        out.append({"unit_ids": ids, "category": cat, "priority": max(1, min(4, priority)), "reason": str(item.get("reason", ""))[:300]})
    return out
