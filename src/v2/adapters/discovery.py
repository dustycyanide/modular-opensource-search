from __future__ import annotations

from pathlib import Path
import re

from ..contracts import QuerySpec, RepoCandidate
from .github_api import GitHubApiError, GitHubClient


class GitHubRepoDiscoverer:
    def __init__(
        self,
        client: GitHubClient,
        *,
        max_repos: int = 8,
        exclude_archived: bool = True,
        exclude_forks: bool = True,
        local_fallback_dir: str | Path = "v1-archived/repos",
        local_only: bool = False,
    ) -> None:
        self.client = client
        self.max_repos = max_repos
        self.exclude_archived = exclude_archived
        self.exclude_forks = exclude_forks
        self.local_fallback_dir = Path(local_fallback_dir)
        self.local_only = local_only

    def discover(self, query: QuerySpec):
        if self.local_only:
            return self._discover_from_local(query)
        candidates = self._discover_from_github(query)
        if candidates:
            return candidates
        return self._discover_from_local(query)

    def _discover_from_github(self, query: QuerySpec) -> list[RepoCandidate]:
        try:
            payload = self.client.get_json(
                "/search/repositories",
                params={
                    "q": query.text,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": min(max(self.max_repos, 1), 100),
                },
            )
        except GitHubApiError:
            return []

        items = payload.get("items", []) if isinstance(payload, dict) else []
        out: list[RepoCandidate] = []
        for item in items:
            is_archived = bool(item.get("archived", False))
            is_fork = bool(item.get("fork", False))
            if self.exclude_archived and is_archived:
                continue
            if self.exclude_forks and is_fork:
                continue

            owner = item.get("owner", {}).get("login", "")
            name = item.get("name", "")
            if not owner or not name:
                continue

            out.append(
                RepoCandidate(
                    host="github.com",
                    owner=owner,
                    name=name,
                    clone_url=item.get("clone_url", f"https://github.com/{owner}/{name}.git"),
                    default_branch=item.get("default_branch", "main"),
                    stars=int(item.get("stargazers_count", 0)),
                    forks=int(item.get("forks_count", 0)),
                    is_archived=is_archived,
                    is_fork=is_fork,
                    metadata={
                        "repo_url": item.get("html_url", f"https://github.com/{owner}/{name}"),
                        "language": item.get("language"),
                        "topics": item.get("topics", []),
                        "pushed_at": item.get("pushed_at"),
                    },
                )
            )

        return out[: self.max_repos]

    def _discover_from_local(self, query: QuerySpec) -> list[RepoCandidate]:
        if not self.local_fallback_dir.exists():
            return []

        tokens = {
            token
            for token in re.split(r"\W+", query.text.lower())
            if len(token) >= 3
        }
        if not tokens:
            tokens = {query.text.lower().strip()}

        scored: list[tuple[int, Path]] = []
        for entry in sorted(self.local_fallback_dir.iterdir()):
            if not entry.is_dir() or not (entry / ".git").exists():
                continue
            name = entry.name.lower()
            score = sum(1 for token in tokens if token in name)
            scored.append((score, entry))

        scored.sort(key=lambda item: (item[0], item[1].name), reverse=True)
        out: list[RepoCandidate] = []
        for _, repo_path in scored[: self.max_repos]:
            out.append(
                RepoCandidate(
                    host="local",
                    owner="local",
                    name=repo_path.name,
                    clone_url=str(repo_path),
                    default_branch="HEAD",
                    metadata={"local_path": str(repo_path)},
                )
            )
        return out
