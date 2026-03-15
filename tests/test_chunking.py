from v2.adapters.chunking import ChunkingConfig, RepositoryChunkBuilder


def test_should_include_path_filters_noise_and_unknown_extensions() -> None:
    builder = RepositoryChunkBuilder()

    assert builder.should_include_path("src/parser.py")
    assert not builder.should_include_path("vendor/lib/generated/file.py")
    assert not builder.should_include_path("assets/app.min.js")
    assert not builder.should_include_path("bin/parser.bin")


def test_build_chunks_splits_with_overlap_and_preserves_metadata() -> None:
    builder = RepositoryChunkBuilder(ChunkingConfig(chunk_lines=3, overlap_lines=1, min_nonblank_lines=1))
    text = "\n".join(
        [
            "line 1",
            "line 2",
            "line 3",
            "line 4",
            "line 5",
        ]
    )

    chunks = builder.build_chunks(
        repo="demo/repo",
        commit_sha="abc123",
        rel_path="src/parser.py",
        text=text,
        base_metadata={"repo_url": "https://github.com/demo/repo"},
    )

    assert [(chunk.start_line, chunk.end_line) for chunk in chunks] == [(1, 3), (3, 5)]
    assert chunks[0].language == "Python"
    assert chunks[0].metadata["repo_url"] == "https://github.com/demo/repo"
    assert "line 3" in chunks[1].content


def test_build_chunks_skips_low_signal_files() -> None:
    builder = RepositoryChunkBuilder(ChunkingConfig(min_nonblank_lines=3))

    chunks = builder.build_chunks(
        repo="demo/repo",
        commit_sha="abc123",
        rel_path="README.md",
        text=" \n\none line only\n",
        base_metadata={},
    )

    assert chunks == []
