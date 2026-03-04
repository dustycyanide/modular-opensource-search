from __future__ import annotations

from pathlib import Path
import subprocess

from ..contracts import ArtifactChunk, RepoCandidate
from .github_api import GitHubApiError, GitHubClient


class RepositoryManifestIngestor:
    def __init__(self, client: GitHubClient, *, max_repos: int = 8) -> None:
        self.client = client
        self.max_repos = max_repos

    def ingest(self, candidates):
        manifests: list[ArtifactChunk] = []
        for candidate in list(candidates)[: self.max_repos]:
            commit_sha = self._resolve_head_sha(candidate)
            metadata = dict(candidate.metadata)
            metadata.setdefault("repo_url", self._resolve_repo_url(candidate))
            manifests.append(
                ArtifactChunk(
                    repo=f"{candidate.owner}/{candidate.name}" if candidate.owner != "local" else candidate.name,
                    commit_sha=commit_sha,
                    path="",
                    language="repo",
                    symbol=None,
                    start_line=1,
                    end_line=1,
                    content="",
                    metadata=metadata,
                )
            )
        return manifests

    def _resolve_head_sha(self, candidate: RepoCandidate) -> str:
        local_path = candidate.metadata.get("local_path")
        if local_path:
            sha = _git_output(Path(local_path), ["rev-parse", "HEAD"])
            if sha:
                return sha
            return "HEAD"

        try:
            payload = self.client.get_json(
                f"/repos/{candidate.owner}/{candidate.name}/branches/{candidate.default_branch}"
            )
        except GitHubApiError:
            return "HEAD"

        if isinstance(payload, dict):
            commit = payload.get("commit", {})
            sha = commit.get("sha")
            if isinstance(sha, str) and sha:
                return sha
        return "HEAD"

    def _resolve_repo_url(self, candidate: RepoCandidate) -> str | None:
        local_path = candidate.metadata.get("local_path")
        if local_path:
            origin = _git_output(Path(local_path), ["remote", "get-url", "origin"])
            if origin:
                return _normalize_remote_url(origin)
            return None

        if candidate.owner == "local":
            return None
        return f"https://github.com/{candidate.owner}/{candidate.name}"


def _git_output(repo_path: Path, args: list[str]) -> str | None:
    try:
        output = subprocess.check_output(
            ["git", "-C", str(repo_path), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return output or None


def _normalize_remote_url(remote_url: str) -> str:
    stripped = remote_url.strip()
    if stripped.startswith("git@github.com:"):
        path = stripped.split(":", 1)[1]
        if path.endswith(".git"):
            path = path[:-4]
        return f"https://github.com/{path}"
    if stripped.endswith(".git"):
        return stripped[:-4]
    return stripped
