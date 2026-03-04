from __future__ import annotations

from ..contracts import EvidenceItem, QuerySpec
from ..provenance import build_commit_permalink


class CommitEvidencePackager:
    def package(self, query: QuerySpec, chunks):
        packaged: list[EvidenceItem] = []
        for item in chunks:
            chunk = item.chunk
            repo_url = chunk.metadata.get("repo_url")
            permalink = None
            if repo_url and chunk.path and chunk.commit_sha and chunk.commit_sha != "HEAD":
                permalink = build_commit_permalink(
                    repo_url=repo_url,
                    commit_sha=chunk.commit_sha,
                    path=chunk.path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                )

            packaged.append(
                EvidenceItem(
                    repo=chunk.repo,
                    commit_sha=chunk.commit_sha,
                    path=chunk.path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    snippet=chunk.content,
                    score=item.score,
                    reasons=item.reasons,
                    permalink=permalink,
                    metadata={
                        "query": query.text,
                        "source": item.source,
                        "language": chunk.language,
                    },
                )
            )
        return packaged
