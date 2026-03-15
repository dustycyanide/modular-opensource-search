from __future__ import annotations

import subprocess
from pathlib import Path

from v2.adapters.ingestion import IngestionConfig, RepositoryChunkIngestor
from v2.adapters.github_api import GitHubClient
from v2.contracts import RepoCandidate


def test_local_ingestor_emits_chunks_from_git_repo(tmp_path: Path) -> None:
    repo_path = _init_git_repo(tmp_path / "demo")
    (repo_path / "src").mkdir()
    (repo_path / "vendor").mkdir()
    (repo_path / "src" / "parser.py").write_text(
        "\n".join(
            [
                "import json",
                "",
                "def parse_json(payload):",
                "    return json.loads(payload)",
                "",
                "def parse_yaml(payload):",
                "    return payload",
            ]
        ),
        encoding="utf-8",
    )
    (repo_path / "vendor" / "copied.py").write_text("print('ignore me')\n", encoding="utf-8")
    _git_commit_all(repo_path, "add parser")

    ingestor = RepositoryChunkIngestor(
        GitHubClient(token="test"),
        config=IngestionConfig(
            max_repos=1,
            max_files_per_repo=10,
            chunk_lines=4,
            overlap_lines=1,
            min_nonblank_lines=1,
        ),
    )
    chunks = ingestor.ingest(
        [
            RepoCandidate(
                host="local",
                owner="local",
                name="demo",
                clone_url=str(repo_path),
                metadata={"local_path": str(repo_path)},
            )
        ]
    )

    assert chunks
    assert {chunk.path for chunk in chunks} == {"src/parser.py"}
    assert all(chunk.commit_sha != "HEAD" for chunk in chunks)
    assert [(chunk.start_line, chunk.end_line) for chunk in chunks] == [(1, 4), (4, 7)]


def test_local_ingestor_respects_max_files_per_repo(tmp_path: Path) -> None:
    repo_path = _init_git_repo(tmp_path / "demo")
    (repo_path / "src").mkdir()
    (repo_path / "src" / "a.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
    (repo_path / "src" / "b.py").write_text("four\nfive\nsix\n", encoding="utf-8")
    _git_commit_all(repo_path, "add files")

    ingestor = RepositoryChunkIngestor(
        GitHubClient(token="test"),
        config=IngestionConfig(max_files_per_repo=1, min_nonblank_lines=1),
    )
    chunks = ingestor.ingest(
        [
            RepoCandidate(
                host="local",
                owner="local",
                name="demo",
                clone_url=str(repo_path),
                metadata={"local_path": str(repo_path)},
            )
        ]
    )

    assert chunks
    assert len({chunk.path for chunk in chunks}) == 1


def _init_git_repo(repo_path: Path) -> Path:
    repo_path.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
    return repo_path


def _git_commit_all(repo_path: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo_path, check=True, capture_output=True, text=True)
