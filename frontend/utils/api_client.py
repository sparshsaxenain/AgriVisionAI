"""Small resilient client for the local FastAPI service."""
from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


class APIError(RuntimeError):
    pass


class APIClient:
    def __init__(self, token: str | None = None):
        self.token = token

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = {**self.headers, **kwargs.pop("headers", {})}
        timeout = kwargs.pop("timeout", 35)
        try:
            response = requests.request(method, f"{BASE_URL}{path}", headers=headers, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            raise APIError("AgriVision service is not reachable. Start it with python run.py.") from exc
        if not response.ok:
            try:
                message = response.json().get("detail", "Request could not be completed.")
            except ValueError:
                message = "Request could not be completed."
            raise APIError(str(message))
        return response.json() if response.content else None

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Any:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)
