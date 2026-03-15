from __future__ import annotations

import subprocess
from pathlib import Path

from v2.cli import build_pipeline
from v2.contracts import QuerySpec


def test_local_pipeline_returns_evidence_from_ingested_chunks(tmp_path: Path) -> None:
    repo_path = _init_git_repo(tmp_path / "demo")
    (repo_path / "src").mkdir()
    (repo_path / "src" / "parser.py").write_text(
        "\n".join(
            [
                "import json",
                "",
                "def parse_json(payload):",
                "    return json.loads(payload)",
            ]
        ),
        encoding="utf-8",
    )
    _git_commit_all(repo_path, "add parser")

    pipeline = build_pipeline(
        mode="lexical",
        dataset_root=None,
        embedding_model="BAAI/bge-base-en-v1.5",
        languages=[],
        max_docs=0,
        max_repos=1,
        per_repo_hits=5,
        max_files_per_repo=10,
        max_file_bytes=250000,
        chunk_lines=20,
        overlap_lines=5,
        local_fallback_dir=str(tmp_path),
        local_only=True,
        github_token=None,
    )

    evidence, trace = pipeline.run_with_trace(QuerySpec(text="parse json", top_k=3))

    assert evidence
    assert evidence[0].path == "src/parser.py"
    assert evidence[0].permalink is None
    assert trace["discover"] >= 0.0
    assert trace["ingest"] >= 0.0
    assert trace["lexical"] >= 0.0


def test_local_pipeline_semantic_mode_returns_evidence(tmp_path: Path) -> None:
    repo_path = _init_git_repo(tmp_path / "demo")
    (repo_path / "src").mkdir()
    (repo_path / "src" / "parser.py").write_text(
        "\n".join(
            [
                "import json",
                "",
                "def parse_json(payload):",
                "    return json.loads(payload)",
            ]
        ),
        encoding="utf-8",
    )
    _git_commit_all(repo_path, "add parser")

    pipeline = build_pipeline(
        mode="semantic",
        dataset_root=None,
        embedding_model="BAAI/bge-base-en-v1.5",
        languages=[],
        max_docs=0,
        max_repos=1,
        per_repo_hits=5,
        max_files_per_repo=10,
        max_file_bytes=250000,
        chunk_lines=20,
        overlap_lines=5,
        local_fallback_dir=str(tmp_path),
        local_only=True,
        github_token=None,
    )

    evidence, trace = pipeline.run_with_trace(QuerySpec(text="parse json", top_k=3))

    assert evidence
    assert evidence[0].path == "src/parser.py"
    assert trace["semantic"] > 0.0


def _init_git_repo(repo_path: Path) -> Path:
    repo_path.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
    return repo_path


def _git_commit_all(repo_path: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo_path, check=True, capture_output=True, text=True)
