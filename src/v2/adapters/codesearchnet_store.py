from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Iterable
from urllib.parse import urlparse

from .embedding_index import EmbeddingConfig, EmbeddingIndex


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class CodeSearchNetDocument:
    doc_id: str
    repo: str
    language: str
    path: str
    func_name: str
    code: str
    docstring: str
    code_tokens: tuple[str, ...]
    docstring_tokens: tuple[str, ...]
    sha: str
    url: str
    partition: str


class CodeSearchNetStore:
    def __init__(
        self,
        dataset_root: str | Path,
        *,
        languages: Iterable[str] | None = None,
        partitions: Iterable[str] | None = None,
        max_docs: int = 0,
        embedding_model_name: str = "BAAI/bge-base-en-v1.5",
    ) -> None:
        self.dataset_root = Path(dataset_root)
        self.languages = {item.strip().lower() for item in (languages or []) if item.strip()}
        self.partitions = {item.strip().lower() for item in (partitions or []) if item.strip()}
        self.max_docs = max_docs
        self.embedding_model_name = embedding_model_name

        self.documents: list[CodeSearchNetDocument] = []
        self._lexical_postings: dict[str, list[tuple[int, float]]] = {}
        self._lexical_idf: dict[str, float] = {}
        self._semantic_index: EmbeddingIndex | None = None
        self._loaded = False

    def ensure_loaded(self) -> None:
        if self._loaded:
            return

        normalized_dir = self.dataset_root / "normalized"
        if not normalized_dir.exists():
            raise FileNotFoundError(
                f"Missing normalized corpus under {normalized_dir}. Run prepare_codesearchnet.py first."
            )

        normalized_files = sorted(normalized_dir.glob("*.jsonl"))
        if self.languages:
            normalized_files = [
                path for path in normalized_files if path.stem.lower() in self.languages
            ]

        for file_path in normalized_files:
            language = file_path.stem.lower()
            with file_path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    partition = str(row.get("partition", "")).strip().lower()
                    if self.partitions and partition not in self.partitions:
                        continue
                    doc = _row_to_document(row, default_language=language)
                    if not doc:
                        continue
                    self.documents.append(doc)
                    if self.max_docs > 0 and len(self.documents) >= self.max_docs:
                        break
            if self.max_docs > 0 and len(self.documents) >= self.max_docs:
                break

        if not self.documents:
            raise RuntimeError("No normalized CodeSearchNet records available for selected filters")

        self._build_lexical_index()
        self._build_semantic_index()
        self._loaded = True

    def lexical_search(
        self,
        query_text: str,
        *,
        top_k: int,
    ) -> list[tuple[CodeSearchNetDocument, float, tuple[str, ...]]]:
        self.ensure_loaded()
        query_tokens = tokenize(query_text)
        if not query_tokens:
            return []

        scores: dict[int, float] = defaultdict(float)
        for token in query_tokens:
            postings = self._lexical_postings.get(token)
            if not postings:
                continue
            idf = self._lexical_idf.get(token, 1.0)
            for doc_index, term_weight in postings:
                scores[doc_index] += term_weight * idf

        query_phrase = query_text.strip().lower()
        if query_phrase:
            for doc_index in list(scores.keys()):
                doc = self.documents[doc_index]
                if query_phrase in doc.docstring.lower():
                    scores[doc_index] += 1.0
                if query_phrase in doc.code.lower():
                    scores[doc_index] += 0.6

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        out: list[tuple[CodeSearchNetDocument, float, tuple[str, ...]]] = []
        for doc_index, score in ranked[:top_k]:
            out.append((self.documents[doc_index], score, ("lexical_match",)))
        return out

    def semantic_search(
        self,
        query_text: str,
        *,
        top_k: int,
    ) -> list[tuple[CodeSearchNetDocument, float, tuple[str, ...]]]:
        self.ensure_loaded()
        if self._semantic_index is None:
            return []

        out: list[tuple[CodeSearchNetDocument, float, tuple[str, ...]]] = []
        for doc_index, score in self._semantic_index.search(query_text, top_k=top_k):
            out.append((self.documents[doc_index], score, ("semantic_embedding_match",)))
        return out

    def _build_lexical_index(self) -> None:
        df: dict[str, int] = defaultdict(int)
        postings: dict[str, list[tuple[int, float]]] = defaultdict(list)

        for index, doc in enumerate(self.documents):
            term_weights: dict[str, float] = defaultdict(float)
            for token in doc.code_tokens:
                term_weights[token] += 1.0
            for token in doc.docstring_tokens:
                term_weights[token] += 1.0
            for token in tokenize(doc.func_name):
                term_weights[token] += 2.0
            for token in tokenize(doc.path):
                term_weights[token] += 1.5

            for token, weight in term_weights.items():
                postings[token].append((index, weight))
                df[token] += 1

        total_docs = len(self.documents)
        self._lexical_postings = dict(postings)
        self._lexical_idf = {
            token: math.log((total_docs + 1) / (doc_freq + 1)) + 1.0
            for token, doc_freq in df.items()
        }

    def _build_semantic_index(self) -> None:
        self._semantic_index = EmbeddingIndex(
            EmbeddingConfig(model_name=self.embedding_model_name)
        )
        self._semantic_index.build(
            [
                "\n".join(
                    part
                    for part in [doc.func_name, doc.path, doc.docstring, doc.code[:1200]]
                    if part
                )
                for doc in self.documents
            ]
        )


def _row_to_document(row: dict[str, object], *, default_language: str) -> CodeSearchNetDocument | None:
    repo = str(row.get("repo") or "").strip()
    path = str(row.get("path") or "").strip().lstrip("/")
    url = str(row.get("url") or "").strip()
    language = str(row.get("language") or default_language or "").strip() or default_language
    if not path and url:
        path = _path_from_url(url)
    if not repo and url:
        repo = _repo_from_url(url)
    if not repo or not path:
        return None

    code = str(row.get("code") or "")
    docstring = str(row.get("docstring") or "")
    code_tokens = tuple(_tokens_from_any(row.get("code_tokens"), fallback=code))
    doc_tokens = tuple(_tokens_from_any(row.get("docstring_tokens"), fallback=docstring))
    func_name = str(row.get("func_name") or "")
    sha = str(row.get("sha") or "")
    partition = str(row.get("partition") or "")
    doc_id = str(row.get("doc_id") or "").strip().lower()
    if not doc_id:
        doc_id = normalize_doc_id(url=url, repo=repo, path=path)

    return CodeSearchNetDocument(
        doc_id=doc_id,
        repo=repo,
        language=language,
        path=path,
        func_name=func_name,
        code=code,
        docstring=docstring,
        code_tokens=code_tokens,
        docstring_tokens=doc_tokens,
        sha=sha,
        url=url,
        partition=partition,
    )


def normalize_doc_id(*, url: str, repo: str, path: str) -> str:
    from_url = _doc_id_from_url(url)
    if from_url:
        return from_url
    clean_repo = repo.strip().lower().strip("/")
    clean_path = path.strip().lower().lstrip("/")
    return f"{clean_repo}/{clean_path}"


def repo_url_from_doc(doc: CodeSearchNetDocument) -> str | None:
    parsed = urlparse(doc.url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) >= 2:
        return f"https://github.com/{parts[0]}/{parts[1]}"
    if "/" in doc.repo:
        return f"https://github.com/{doc.repo}"
    return None


def commit_sha_from_doc(doc: CodeSearchNetDocument) -> str:
    if doc.sha:
        return doc.sha
    parsed = urlparse(doc.url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) >= 5 and parts[2] == "blob":
        return parts[3]
    return "HEAD"


def _repo_from_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return ""


def _path_from_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) >= 5 and parts[2] == "blob":
        return "/".join(parts[4:])
    return ""


def _doc_id_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 5:
        return None
    if parts[2] != "blob":
        return None
    owner, repo = parts[0], parts[1]
    file_path = "/".join(parts[4:])
    if not file_path:
        return None
    return f"{owner.lower()}/{repo.lower()}/{file_path.lower()}"


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text or "")]


def _tokens_from_any(value: object, *, fallback: str) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            token = str(item).strip().lower()
            if token:
                out.append(token)
        if out:
            return out
    return tokenize(fallback)
