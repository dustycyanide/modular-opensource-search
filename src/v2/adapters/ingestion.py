from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from ..contracts import ArtifactChunk, RepoCandidate
from .chunking import ChunkingConfig, RepositoryChunkBuilder
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


@dataclass(frozen=True)
class IngestionConfig:
    max_repos: int = 8
    max_files_per_repo: int = 400
    max_file_bytes: int = 250_000
    chunk_lines: int = 40
    overlap_lines: int = 8
    min_nonblank_lines: int = 3


class RepositoryChunkIngestor:
    def __init__(self, client: GitHubClient, *, config: IngestionConfig | None = None) -> None:
        self.client = client
        self.config = config or IngestionConfig()
        self.chunk_builder = RepositoryChunkBuilder(
            ChunkingConfig(
                max_file_bytes=self.config.max_file_bytes,
                chunk_lines=self.config.chunk_lines,
                overlap_lines=self.config.overlap_lines,
                min_nonblank_lines=self.config.min_nonblank_lines,
            )
        )

    def ingest(self, candidates):
        chunks: list[ArtifactChunk] = []
        for candidate in list(candidates)[: self.config.max_repos]:
            if candidate.metadata.get("local_path"):
                chunks.extend(self._ingest_local_repo(candidate))
                continue
            chunks.extend(self._ingest_github_repo(candidate))
        return chunks

    def _ingest_local_repo(self, candidate: RepoCandidate) -> list[ArtifactChunk]:
        local_path_raw = candidate.metadata.get("local_path")
        if not isinstance(local_path_raw, str) or not local_path_raw:
            return []

        local_path = Path(local_path_raw)
        if not local_path.exists():
            return []

        commit_sha = _resolve_head_sha(self.client, candidate)
        repo = candidate.name if candidate.owner == "local" else f"{candidate.owner}/{candidate.name}"
        base_metadata = dict(candidate.metadata)
        base_metadata.setdefault("repo_url", _resolve_repo_url(candidate))

        chunks: list[ArtifactChunk] = []
        files_seen = 0
        for file_path in local_path.rglob("*"):
            if files_seen >= self.config.max_files_per_repo:
                break
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(local_path).as_posix()
            if not self.chunk_builder.should_include_path(rel_path):
                continue

            try:
                if file_path.stat().st_size > self.config.max_file_bytes:
                    continue
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            files_seen += 1
            chunks.extend(
                self.chunk_builder.build_chunks(
                    repo=repo,
                    commit_sha=commit_sha,
                    rel_path=rel_path,
                    text=text,
                    base_metadata=base_metadata,
                )
            )

        return chunks

    def _ingest_github_repo(self, candidate: RepoCandidate) -> list[ArtifactChunk]:
        commit_sha = _resolve_head_sha(self.client, candidate)
        tree_payload = self.client.list_tree(candidate.owner, candidate.name, commit_sha)
        tree = tree_payload.get("tree", []) if isinstance(tree_payload, dict) else []
        if not isinstance(tree, list):
            return []

        repo = f"{candidate.owner}/{candidate.name}"
        base_metadata = dict(candidate.metadata)
        base_metadata.setdefault("repo_url", _resolve_repo_url(candidate))
        base_metadata["tree_truncated"] = bool(tree_payload.get("truncated", False))

        chunks: list[ArtifactChunk] = []
        files_seen = 0
        for item in tree:
            if files_seen >= self.config.max_files_per_repo:
                break
            if not isinstance(item, dict):
                continue
            if item.get("type") != "blob":
                continue

            rel_path = str(item.get("path") or "")
            if not rel_path or not self.chunk_builder.should_include_path(rel_path):
                continue

            text = self.client.get_text_file(candidate.owner, candidate.name, rel_path, ref=commit_sha)
            if text is None:
                continue

            files_seen += 1
            chunks.extend(
                self.chunk_builder.build_chunks(
                    repo=repo,
                    commit_sha=commit_sha,
                    rel_path=rel_path,
                    text=text,
                    base_metadata=base_metadata,
                )
            )

        return chunks


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


def _resolve_head_sha(client: GitHubClient, candidate: RepoCandidate) -> str:
    local_path = candidate.metadata.get("local_path")
    if local_path:
        sha = _git_output(Path(local_path), ["rev-parse", "HEAD"])
        if sha:
            return sha
        return "HEAD"

    try:
        payload = client.get_json(
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


def _resolve_repo_url(candidate: RepoCandidate) -> str | None:
    local_path = candidate.metadata.get("local_path")
    if local_path:
        origin = _git_output(Path(local_path), ["remote", "get-url", "origin"])
        if origin:
            return _normalize_remote_url(origin)
        return None

    if candidate.owner == "local":
        return None
    return f"https://github.com/{candidate.owner}/{candidate.name}"
