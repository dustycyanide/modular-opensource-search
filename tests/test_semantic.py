from v2.adapters.embedding_index import EmbeddingIndex
from v2.adapters.semantic import EmbeddingSemanticRetriever
from v2.contracts import ArtifactChunk, QuerySpec


def test_embedding_index_ranks_json_text_first() -> None:
    index = EmbeddingIndex()
    index.build(
        [
            "src/parser.py\nPython\ndef parse_json(payload): return json.loads(payload)",
            "src/config.py\nPython\ndef load_yaml(path): return yaml.safe_load(path.read_text())",
        ]
    )

    hits = index.search("parse json payload", top_k=2)

    assert hits
    assert hits[0][0] == 0


def test_embedding_semantic_retriever_prefers_parse_json_chunk() -> None:
    corpus = [
        ArtifactChunk(
            repo="demo/repo",
            commit_sha="abc123",
            path="src/parser.py",
            language="Python",
            symbol=None,
            start_line=1,
            end_line=5,
            content="def parse_json(payload): return json.loads(payload)",
        ),
        ArtifactChunk(
            repo="demo/repo",
            commit_sha="abc123",
            path="src/config.py",
            language="Python",
            symbol=None,
            start_line=1,
            end_line=5,
            content="def load_yaml(path): return yaml.safe_load(path.read_text())",
        ),
    ]

    retriever = EmbeddingSemanticRetriever(candidate_multiplier=2)
    hits = retriever.retrieve(QuerySpec(text="parse json payload", top_k=1), corpus)

    assert hits
    assert hits[0].chunk.path == "src/parser.py"
    assert hits[0].reasons == ("semantic_embedding_match",)
