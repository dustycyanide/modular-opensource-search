from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence


@dataclass(frozen=True)
class QuerySpec:
    text: str
    top_k: int = 20


@dataclass(frozen=True)
class RepoCandidate:
    host: str
    owner: str
    name: str
    clone_url: str
    default_branch: str = "main"
    stars: int = 0
    forks: int = 0
    is_archived: bool = False
    is_fork: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArtifactChunk:
    repo: str
    commit_sha: str
    path: str
    language: str
    symbol: str | None
    start_line: int
    end_line: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoredChunk:
    chunk: ArtifactChunk
    score: float
    source: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceItem:
    repo: str
    commit_sha: str
    path: str
    start_line: int
    end_line: int
    snippet: str
    score: float
    reasons: tuple[str, ...] = ()
    permalink: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Discoverer(Protocol):
    def discover(self, query: QuerySpec) -> Sequence[RepoCandidate]: ...


class Ingestor(Protocol):
    def ingest(self, candidates: Sequence[RepoCandidate]) -> Sequence[ArtifactChunk]: ...


class LexicalRetriever(Protocol):
    def retrieve(self, query: QuerySpec, corpus: Sequence[ArtifactChunk]) -> Sequence[ScoredChunk]: ...


class SemanticRetriever(Protocol):
    def retrieve(self, query: QuerySpec, corpus: Sequence[ArtifactChunk]) -> Sequence[ScoredChunk]: ...


class RankFuser(Protocol):
    def fuse(self, ranked_lists: Sequence[Sequence[ScoredChunk]], top_k: int) -> Sequence[ScoredChunk]: ...


class Reranker(Protocol):
    def rerank(self, query: QuerySpec, chunks: Sequence[ScoredChunk]) -> Sequence[ScoredChunk]: ...


class EvidencePackager(Protocol):
    def package(self, query: QuerySpec, chunks: Sequence[ScoredChunk]) -> Sequence[EvidenceItem]: ...


class Evaluator(Protocol):
    def evaluate(self, annotations_path: str) -> dict[str, float | int]: ...
