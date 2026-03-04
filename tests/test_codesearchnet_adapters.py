from __future__ import annotations

import json
from pathlib import Path

from v2.adapters.codesearchnet_lexical import CodeSearchNetLexicalRetriever
from v2.adapters.codesearchnet_semantic import CodeSearchNetSemanticRetriever
from v2.adapters.codesearchnet_store import CodeSearchNetStore
from v2.contracts import QuerySpec


def test_codesearchnet_retrievers_return_expected_hits(tmp_path: Path) -> None:
    dataset_root = tmp_path / "codesearchnet"
    normalized = dataset_root / "normalized"
    normalized.mkdir(parents=True)

    records = [
        {
            "doc_id": "foo/bar/src/parser.py",
            "repo": "foo/bar",
            "language": "python",
            "path": "src/parser.py",
            "func_name": "parse_json",
            "code": "def parse_json(payload):\n    return json.loads(payload)",
            "docstring": "Parse JSON payload string",
            "code_tokens": ["def", "parse_json", "payload", "json", "loads"],
            "docstring_tokens": ["parse", "json", "payload", "string"],
            "sha": "abc123",
            "url": "https://github.com/foo/bar/blob/abc123/src/parser.py",
            "partition": "test",
        },
        {
            "doc_id": "foo/bar/src/config.py",
            "repo": "foo/bar",
            "language": "python",
            "path": "src/config.py",
            "func_name": "load_yaml",
            "code": "def load_yaml(path):\n    return yaml.safe_load(path.read_text())",
            "docstring": "Load yaml config from file",
            "code_tokens": ["def", "load_yaml", "yaml", "safe_load"],
            "docstring_tokens": ["load", "yaml", "config"],
            "sha": "abc123",
            "url": "https://github.com/foo/bar/blob/abc123/src/config.py",
            "partition": "test",
        },
    ]
    with (normalized / "python.jsonl").open("w", encoding="utf-8") as handle:
        for row in records:
            handle.write(json.dumps(row) + "\n")

    store = CodeSearchNetStore(dataset_root)
    lexical = CodeSearchNetLexicalRetriever(store)
    semantic = CodeSearchNetSemanticRetriever(store)

    lexical_hits = lexical.retrieve(QuerySpec(text="parse json", top_k=2), corpus=[])
    semantic_hits = semantic.retrieve(QuerySpec(text="yaml config", top_k=2), corpus=[])

    assert lexical_hits
    assert lexical_hits[0].chunk.path == "src/parser.py"
    assert lexical_hits[0].chunk.metadata["doc_id"] == "foo/bar/src/parser.py"

    assert semantic_hits
    assert semantic_hits[0].chunk.path == "src/config.py"
