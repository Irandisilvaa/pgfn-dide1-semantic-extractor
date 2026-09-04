from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import requests


class LocalLLMClient:
    """
    Cliente OpenAI-compatible com endpoint local.

    Por padrão SOMENTE 127.0.0.1/localhost é aceito.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 420,
        max_retries: int = 2,
    ):
        self.base_url = (
            base_url
            or os.getenv(
                "LOCAL_LLM_BASE_URL",
                "http://127.0.0.1:8081/v1",
            )
        ).rstrip("/")

        allowed = (
            self.base_url.startswith("http://127.0.0.1:")
            or self.base_url.startswith("http://localhost:")
        )

        if not allowed:
            raise ValueError(
                "Segurança: o LLM deve estar em 127.0.0.1/localhost."
            )

        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.model = (
            model
            or os.getenv("LOCAL_LLM_MODEL", "").strip()
        )

        if not self.model:
            self.model = self._discover_model()

    def _discover_model(self) -> str:
        response = self.session.get(
            f"{self.base_url}/models",
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])

        if not data:
            raise RuntimeError(
                "/v1/models não retornou nenhum modelo."
            )

        return str(data[0]["id"])

    def health(self) -> dict:
        return {
            "base_url": self.base_url,
            "model": self.model,
        }

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
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
                text = data["choices"][0]["message"]["content"]
                return self._parse_json(text)

            except Exception as exc:
                last_exc = exc

                if attempt >= self.max_retries:
                    break

                time.sleep(0.5 * attempt)

        raise RuntimeError(
            "Falha ao obter JSON válido do LLM local."
        ) from last_exc

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        text = (text or "").strip()

        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s*```$", "", text).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")

        if start >= 0 and end > start:
            candidate = text[start:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "LLM local não retornou JSON válido."
                ) from exc

        raise RuntimeError(
            "LLM local não retornou objeto JSON."
        )
