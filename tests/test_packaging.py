from v2.adapters.packaging import CommitEvidencePackager
from v2.contracts import ArtifactChunk, QuerySpec, ScoredChunk


def test_packager_preserves_reasoning_and_metadata() -> None:
    packager = CommitEvidencePackager()
    packaged = packager.package(
        QuerySpec(text="parse json", top_k=1),
        [
            ScoredChunk(
                chunk=ArtifactChunk(
                    repo="demo/repo",
                    commit_sha="abc123",
                    path="src/parser.py",
                    language="Python",
                    symbol=None,
                    start_line=10,
                    end_line=20,
                    content="def parse_json(payload): return json.loads(payload)",
                    metadata={
                        "repo_url": "https://github.com/demo/repo",
                        "topics": ["json", "parser"],
                        "discovery_reasons": ["local_fallback"],
                        "chunk_kind": "source",
                    },
                ),
                score=1.2,
                source="rrf",
                reasons=("lexical_match", "semantic_embedding_match", "rrf_fusion"),
            )
        ],
    )

    assert packaged
    item = packaged[0]
    assert item.permalink == "https://github.com/demo/repo/blob/abc123/src/parser.py#L10-L20"
    assert item.reasons == ("lexical_match", "semantic_embedding_match", "rrf_fusion")
    assert item.metadata["repo_topics"] == ["json", "parser"]
    assert item.metadata["discovery_reasons"] == ["local_fallback"]
    assert item.metadata["chunk_kind"] == "source"


def test_packager_keeps_local_evidence_without_permalink() -> None:
    packager = CommitEvidencePackager()
    packaged = packager.package(
        QuerySpec(text="parse json", top_k=1),
        [
            ScoredChunk(
                chunk=ArtifactChunk(
                    repo="demo",
                    commit_sha="abc123",
                    path="src/parser.py",
                    language="Python",
                    symbol=None,
                    start_line=1,
                    end_line=4,
                    content="def parse_json(payload): return json.loads(payload)",
                    metadata={},
                ),
                score=1.0,
                source="chunk_corpus_scan",
                reasons=("lexical_match",),
            )
        ],
    )

    assert packaged
    assert packaged[0].permalink is None
