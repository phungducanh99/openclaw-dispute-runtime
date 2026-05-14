from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import requests


class SupersetClient:
    def __init__(self, host: str, username: str, password_env: str) -> None:
        password = os.getenv(password_env)
        if not password:
            raise RuntimeError(f"Missing required environment variable: {password_env}")
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.base_url = f"{self.host}/api/v1"
        self._token: str | None = None

    def _headers(self) -> dict[str, str]:
        if not self._token:
            self.login()
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def login(self) -> None:
        response = requests.post(
            f"{self.base_url}/security/login",
            json={
                "username": self.username,
                "password": self.password,
                "provider": "db",
                "refresh": True,
            },
            timeout=30,
        )
        response.raise_for_status()
        self._token = response.json()["access_token"]

    def query(
        self,
        datasource_id: int,
        columns: list[str],
        metrics: list[dict[str, Any]],
        *,
        filters: list[dict[str, Any]] | None = None,
        orderby: list[list[Any]] | None = None,
        row_limit: int = 1000,
        granularity_sqla: str | None = None,
        time_range: str | None = None,
    ) -> list[dict[str, Any]]:
        query_obj: dict[str, Any] = {
            "columns": columns,
            "metrics": metrics,
            "filters": filters or [],
            "orderby": orderby or [],
            "row_limit": row_limit,
        }
        if granularity_sqla:
            query_obj["granularity_sqla"] = granularity_sqla
        if time_range:
            query_obj["time_range"] = time_range

        payload = {
            "datasource": {"id": datasource_id, "type": "table"},
            "queries": [query_obj],
            "result_format": "json",
            "result_type": "full",
        }
        response = requests.post(
            f"{self.base_url}/chart/data",
            json=payload,
            headers=self._headers(),
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["result"][0]["data"]


def superset_time_range(start: datetime, end: datetime) -> str:
    return f"{start.strftime('%Y-%m-%d')} : {end.strftime('%Y-%m-%d')}"
