from __future__ import annotations

import os
from typing import Any

import requests


class GitHubApiError(RuntimeError):
    pass


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str = "https://api.github.com",
        timeout_seconds: int = 15,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "User-Agent": "modular-opensource-v2",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        resolved_token = token or os.getenv("GITHUB_TOKEN")
        if resolved_token:
            self.session.headers["Authorization"] = f"Bearer {resolved_token}"

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        accept: str | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers: dict[str, str] | None = None
        if accept:
            headers = {"Accept": accept}
        response = self.session.get(
            url,
            params=params,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            detail = response.text.strip()
            raise GitHubApiError(f"GitHub API {response.status_code} for {path}: {detail[:240]}")
        return response.json()
