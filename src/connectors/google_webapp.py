from __future__ import annotations

import os
import time
from typing import Iterator

import requests


class GoogleWebAppConnector:
    """
    Cliente SOMENTE LEITURA para o Web App da planilha.

    Variáveis:
      SPREADSHEET_API_BASE_URL
      SPREADSHEET_API_TOKEN

    A classe desta release não expõe método de escrita.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        connect_timeout: int = 15,
        read_timeout: int = 180,
        max_retries: int = 5,
        backoff_seconds: float = 2.0,
    ):
        self.base_url = (
            base_url
            or os.getenv("SPREADSHEET_API_BASE_URL", "")
        ).strip()

        self.token = (
            token
            or os.getenv("SPREADSHEET_API_TOKEN", "")
        ).strip()

        if not self.base_url:
            raise ValueError(
                "SPREADSHEET_API_BASE_URL não configurada."
            )

        if not self.token:
            raise ValueError(
                "SPREADSHEET_API_TOKEN não configurado."
            )

        self.timeout = (
            connect_timeout,
            read_timeout,
        )
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.session = requests.Session()

    def _get(self, **params) -> dict:
        params["token"] = self.token
        last_exc = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(
                    self.base_url,
                    params=params,
                    timeout=self.timeout,
                    allow_redirects=True,
                )

                if response.status_code in {
                    429, 500, 502, 503, 504
                }:
                    raise requests.HTTPError(
                        f"HTTP transitório {response.status_code}",
                        response=response,
                    )

                response.raise_for_status()

                try:
                    data = response.json()
                except Exception as exc:
                    raise RuntimeError(
                        "A API da planilha não retornou JSON válido."
                    ) from exc

                if not data.get("success"):
                    raise RuntimeError(
                        f"Erro da API: {data.get('error', data)}"
                    )

                return data

            except (
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError,
            ) as exc:
                last_exc = exc

                if attempt >= self.max_retries:
                    break

                wait = self.backoff_seconds * (2 ** (attempt - 1))
                print(
                    f"API instável: tentativa {attempt}/"
                    f"{self.max_retries} falhou "
                    f"({type(exc).__name__}). "
                    f"Nova tentativa em {wait:.0f}s..."
                )
                time.sleep(wait)

        raise RuntimeError(
            "Falha ao acessar a API da planilha após "
            f"{self.max_retries} tentativas."
        ) from last_exc

    def schema(self) -> dict:
        return self._get(action="schema")

    def audit_page(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        include_decision: bool = False,
    ) -> dict:
        if not 1 <= int(limit) <= 50:
            raise ValueError("limit deve estar entre 1 e 50.")

        return self._get(
            action="audit",
            limit=int(limit),
            offset=max(0, int(offset)),
            include_decision=(
                "1" if include_decision else "0"
            ),
        )

    def iter_audit_pages(
        self,
        *,
        page_size: int = 50,
        include_decision: bool = False,
        max_rows: int = 0,
        start_offset: int = 0,
    ) -> Iterator[dict]:
        offset = max(0, int(start_offset))
        yielded = 0
        page_size = max(1, min(50, int(page_size)))

        while True:
            if max_rows > 0:
                remaining = max_rows - yielded
                if remaining <= 0:
                    break
                limit = min(page_size, remaining)
            else:
                limit = page_size

            page = self.audit_page(
                limit=limit,
                offset=offset,
                include_decision=include_decision,
            )

            rows = page.get("rows", [])
            if not rows:
                break

            yield page

            yielded += len(rows)
            offset = int(
                page.get(
                    "next_offset",
                    offset + len(rows),
                )
            )

            if not page.get("has_more"):
                break

            if max_rows > 0 and yielded >= max_rows:
                break
