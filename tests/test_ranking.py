from v2.adapters.ranking import HeuristicEvidenceReranker, ReciprocalRankFusion
from v2.contracts import ArtifactChunk, QuerySpec, ScoredChunk


def test_rrf_preserves_reasons_from_multiple_rankers() -> None:
    chunk = ArtifactChunk(
        repo="demo/repo",
        commit_sha="abc123",
        path="src/parser.py",
        language="Python",
        symbol=None,
        start_line=1,
        end_line=4,
        content="def parse_json(payload): return json.loads(payload)",
    )
    lexical_hit = ScoredChunk(chunk=chunk, score=1.0, source="lexical", reasons=("lexical_match",))
    semantic_hit = ScoredChunk(chunk=chunk, score=0.8, source="semantic", reasons=("semantic_embedding_match",))

    fused = ReciprocalRankFusion().fuse([[lexical_hit], [semantic_hit]], top_k=1)

    assert fused
    assert fused[0].reasons == ("lexical_match", "semantic_embedding_match", "rrf_fusion")


def test_reranker_prefers_source_code_with_query_overlap_over_doc_only_match() -> None:
    reranker = HeuristicEvidenceReranker()
    query = QuerySpec(text="parse json", top_k=2)
    code_hit = ScoredChunk(
        chunk=ArtifactChunk(
            repo="demo/repo",
            commit_sha="abc123",
            path="src/parse_json.py",
            language="Python",
            symbol=None,
            start_line=1,
            end_line=4,
            content="def parse_json(payload): return json.loads(payload)",
        ),
        score=0.1,
        source="rrf",
        reasons=("rrf_fusion",),
    )
    docs_hit = ScoredChunk(
        chunk=ArtifactChunk(
            repo="demo/repo",
            commit_sha="abc123",
            path="README.md",
            language="Text",
            symbol=None,
            start_line=1,
            end_line=4,
            content="This project helps parse json payloads from many systems.",
        ),
        score=0.1,
        source="rrf",
        reasons=("rrf_fusion",),
    )

    reranked = reranker.rerank(query, [docs_hit, code_hit])

    assert reranked[0].chunk.path == "src/parse_json.py"
    assert "source_code_boost" in reranked[0].reasons
    assert "path_query_overlap" in reranked[0].reasons
    assert "docs_only_penalty" in reranked[1].reasons
