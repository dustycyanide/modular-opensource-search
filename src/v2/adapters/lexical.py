from __future__ import annotations

import base64
from pathlib import Path
import re

from ..contracts import ArtifactChunk, QuerySpec, ScoredChunk
from .github_api import GitHubApiError, GitHubClient


TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".xml",
    ".html",
    ".css",
    ".sh",
}

NOISE_SEGMENTS = {
    "vendor",
    "node_modules",
    "dist",
    "build",
    "target",
    "third_party",
    "__pycache__",
    ".venv",
    "generated",
}


class GitHubCodeSearchLexicalRetriever:
    def __init__(
        self,
        client: GitHubClient,
        *,
        per_repo_hits: int = 8,
        max_results: int = 120,
        local_file_limit: int = 250,
    ) -> None:
        self.client = client
        self.per_repo_hits = per_repo_hits
        self.max_results = max_results
        self.local_file_limit = local_file_limit

    def retrieve(self, query: QuerySpec, corpus):
        all_hits: list[ScoredChunk] = []
        for manifest in corpus:
            local_path = manifest.metadata.get("local_path")
            if local_path:
                all_hits.extend(self._search_local_repo(query, manifest, Path(local_path)))
                continue
            all_hits.extend(self._search_github_repo(query, manifest))

        all_hits.sort(key=lambda item: item.score, reverse=True)
        deduped: list[ScoredChunk] = []
        seen: set[str] = set()
        for hit in all_hits:
            key = f"{hit.chunk.repo}:{hit.chunk.path}:{hit.chunk.start_line}:{hit.chunk.end_line}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(hit)
            if len(deduped) >= self.max_results:
                break
        return deduped

    def _search_github_repo(self, query: QuerySpec, manifest: ArtifactChunk) -> list[ScoredChunk]:
        repo_name = manifest.repo
        try:
            payload = self.client.get_json(
                "/search/code",
                params={"q": f"{query.text} repo:{repo_name}", "per_page": self.per_repo_hits},
                accept="application/vnd.github.text-match+json",
            )
        except GitHubApiError:
            return []

        items = payload.get("items", []) if isinstance(payload, dict) else []
        out: list[ScoredChunk] = []
        for item in items:
            path = item.get("path", "")
            if not path or is_noise_path(path):
                continue

            snippet, start_line, end_line, match_score = self._build_snippet_from_github(
                query=query,
                manifest=manifest,
                path=path,
                text_matches=item.get("text_matches", []),
            )
            if not snippet:
                continue

            out.append(
                ScoredChunk(
                    chunk=ArtifactChunk(
                        repo=manifest.repo,
                        commit_sha=manifest.commit_sha,
                        path=path,
                        language=language_from_path(path),
                        symbol=None,
                        start_line=start_line,
                        end_line=end_line,
                        content=snippet,
                        metadata={
                            "repo_url": manifest.metadata.get("repo_url"),
                            "source": "github_code_search",
                        },
                    ),
                    score=float(item.get("score", 0.0)) + (0.1 * match_score),
                    source="github_code_search",
                    reasons=("lexical_match",),
                )
            )
        return out

    def _build_snippet_from_github(
        self,
        *,
        query: QuerySpec,
        manifest: ArtifactChunk,
        path: str,
        text_matches,
    ) -> tuple[str | None, int, int, int]:
        content = self._fetch_file_content(manifest.repo, manifest.commit_sha, path)
        if content:
            snippet, start, end, score = build_snippet(content, query.text)
            if snippet:
                return snippet, start, end, score

        fragment = ""
        if isinstance(text_matches, list) and text_matches:
            first = text_matches[0]
            if isinstance(first, dict):
                fragment = str(first.get("fragment", ""))
        if fragment:
            line_count = max(len(fragment.splitlines()), 1)
            return fragment, 1, line_count, 1

        return None, 1, 1, 0

    def _fetch_file_content(self, repo: str, commit_sha: str, path: str) -> str | None:
        parts = repo.split("/", 1)
        if len(parts) != 2:
            return None
        owner, name = parts
        ref = commit_sha if commit_sha and commit_sha != "HEAD" else None
        params = {"ref": ref} if ref else None
        try:
            payload = self.client.get_json(f"/repos/{owner}/{name}/contents/{path}", params=params)
        except GitHubApiError:
            return None

        if not isinstance(payload, dict):
            return None
        encoded = payload.get("content")
        if not isinstance(encoded, str):
            return None
        try:
            decoded = base64.b64decode(encoded, validate=False)
        except ValueError:
            return None
        return decoded.decode("utf-8", errors="ignore")

    def _search_local_repo(
        self,
        query: QuerySpec,
        manifest: ArtifactChunk,
        local_repo_path: Path,
    ) -> list[ScoredChunk]:
        if not local_repo_path.exists():
            return []

        out: list[ScoredChunk] = []
        scanned = 0
        for file_path in local_repo_path.rglob("*"):
            if scanned >= self.local_file_limit:
                break
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(local_repo_path).as_posix()
            if is_noise_path(rel_path):
                continue
            if file_path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            try:
                if file_path.stat().st_size > 250_000:
                    continue
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            scanned += 1
            snippet, start_line, end_line, match_score = build_snippet(text, query.text)
            if not snippet:
                continue

            out.append(
                ScoredChunk(
                    chunk=ArtifactChunk(
                        repo=manifest.repo,
                        commit_sha=manifest.commit_sha,
                        path=rel_path,
                        language=language_from_path(rel_path),
                        symbol=None,
                        start_line=start_line,
                        end_line=end_line,
                        content=snippet,
                        metadata={
                            "repo_url": manifest.metadata.get("repo_url"),
                            "source": "local_fallback_scan",
                        },
                    ),
                    score=float(match_score),
                    source="local_fallback_scan",
                    reasons=("lexical_match", "local_fallback"),
                )
            )

        out.sort(key=lambda item: item.score, reverse=True)
        return out[: self.per_repo_hits]


def build_snippet(content: str, query_text: str, window_lines: int = 6) -> tuple[str | None, int, int, int]:
    lines = content.splitlines()
    if not lines:
        return None, 1, 1, 0

    query_tokens = [
        token
        for token in re.split(r"\W+", query_text.lower())
        if len(token) >= 3
    ]
    if not query_tokens:
        query_tokens = [query_text.lower().strip()]

    best_index = -1
    best_score = 0
    for index, line in enumerate(lines):
        lowered = line.lower()
        score = sum(1 for token in query_tokens if token in lowered)
        if score > best_score:
            best_score = score
            best_index = index

    if best_index < 0 or best_score == 0:
        return None, 1, 1, 0

    start_line = max(1, (best_index + 1) - window_lines)
    end_line = min(len(lines), (best_index + 1) + window_lines)
    snippet = "\n".join(lines[start_line - 1 : end_line])
    if len(snippet) > 3000:
        snippet = snippet[:3000]
    return snippet, start_line, end_line, best_score


def language_from_path(path: str) -> str:
    extension = Path(path).suffix.lower()
    return {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".jsx": "JavaScript",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".rb": "Ruby",
        ".php": "PHP",
        ".cs": "C#",
    }.get(extension, "Text")


def is_noise_path(path: str) -> bool:
    lower = path.lower()
    if ".min." in lower:
        return True
    segments = set(segment for segment in lower.split("/") if segment)
    if segments.intersection(NOISE_SEGMENTS):
        return True
    if lower.endswith(".lock"):
        return True
    return False
