from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import requests


class LocalLLMClient:
    """
    Cliente OpenAI-compatible para llama.cpp LOCAL.

    Por segurança, por padrão aceita apenas 127.0.0.1/localhost.
    O pipeline não depende de .env.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8081/v1",
        model: str | None = None,
        timeout: int = 900,
        max_retries: int = 2,
    ):
        self.base_url = base_url.rstrip("/")

        allowed = (
            self.base_url.startswith("http://127.0.0.1:")
            or self.base_url.startswith("http://localhost:")
        )
        if not allowed:
            raise ValueError(
                "Segurança: este piloto aceita LLM apenas em 127.0.0.1/localhost."
            )

        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.model = (model or "").strip() or self._discover_model()

    def _discover_model(self) -> str:
        response = self.session.get(f"{self.base_url}/models", timeout=30)
        response.raise_for_status()
        data = response.json().get("data", [])
        if not data:
            raise RuntimeError("/v1/models não retornou nenhum modelo.")
        return str(data[0]["id"])

    def health(self) -> dict[str, str]:
        return {"base_url": self.base_url, "model": self.model}

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        """
        Usa response_format + JSON Schema do llama.cpp.

        Isso transforma JSON válido em restrição de decodificação, não apenas
        em uma instrução textual. O parser defensivo permanece como fallback.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "response_format": {
                "type": "json_object",
                "schema": schema,
            },
            # Em builds que ainda aceitam esta opção, evita raciocínio explícito
            # em modelos híbridos. O script de servidor também usa --reasoning off.
            "chat_template_kwargs": {
                "enable_thinking": False
            },
        }

        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = self._parse_json(content)
                if not isinstance(parsed, dict):
                    raise RuntimeError("Saída estruturada não é objeto JSON.")
                return parsed
            except Exception as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(0.5 * attempt)

        raise RuntimeError(
            "Falha na inferência estruturada do LLM local."
        ) from last_exc

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        text = (text or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])

        raise RuntimeError("LLM não retornou objeto JSON.")
