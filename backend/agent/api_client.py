"""Authenticated client used by agent tools to call the existing REST API."""
from __future__ import annotations

from typing import Any

import httpx


class AgentAPIError(RuntimeError):
    """A safe, model-readable API error."""


class AgentAPIClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 35,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.transport = transport

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            with httpx.Client(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.request(method, path, params=params, json=json)
        except httpx.RequestError as exc:
            raise AgentAPIError("The AgriVision API could not be reached.") from exc

        if not response.is_success:
            try:
                detail = response.json().get("detail", "The API rejected this operation.")
            except (ValueError, AttributeError):
                detail = "The API rejected this operation."
            raise AgentAPIError(f"API error {response.status_code}: {detail}")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise AgentAPIError("The API returned an unreadable response.") from exc

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", path, json=payload)

    def patch(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return self.request("PATCH", path, json=payload or {})
