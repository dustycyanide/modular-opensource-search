from __future__ import annotations

from ..contracts import ArtifactChunk, QuerySpec, ScoredChunk
from .codesearchnet_store import CodeSearchNetStore, commit_sha_from_doc, repo_url_from_doc
from .lexical import build_snippet


class CodeSearchNetLexicalRetriever:
    def __init__(self, store: CodeSearchNetStore, *, candidate_multiplier: int = 5) -> None:
        self.store = store
        self.candidate_multiplier = candidate_multiplier

    def retrieve(self, query: QuerySpec, corpus):
        del corpus
        top_k = max(query.top_k * self.candidate_multiplier, query.top_k)
        matches = self.store.lexical_search(query.text, top_k=top_k)
        out: list[ScoredChunk] = []

        for doc, score, reasons in matches:
            snippet, start_line, end_line, _ = build_snippet(doc.code, query.text, window_lines=20)
            if not snippet:
                snippet = doc.code[:3000]
                start_line = 1
                end_line = max(1, len(snippet.splitlines()))

            out.append(
                ScoredChunk(
                    chunk=ArtifactChunk(
                        repo=doc.repo,
                        commit_sha=commit_sha_from_doc(doc),
                        path=doc.path,
                        language=doc.language,
                        symbol=doc.func_name or None,
                        start_line=start_line,
                        end_line=end_line,
                        content=snippet,
                        metadata={
                            "repo_url": repo_url_from_doc(doc),
                            "url": doc.url,
                            "doc_id": doc.doc_id,
                            "partition": doc.partition,
                            "source": "codesearchnet_lexical",
                        },
                    ),
                    score=score,
                    source="codesearchnet_lexical",
                    reasons=reasons,
                )
            )
        return out
