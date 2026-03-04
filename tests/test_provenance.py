from v2.provenance import build_commit_permalink


def test_build_commit_permalink_has_line_anchors() -> None:
    url = build_commit_permalink(
        repo_url="https://github.com/org/repo.git",
        commit_sha="abc123",
        path="src/module.py",
        start_line=10,
        end_line=42,
    )
    assert url == "https://github.com/org/repo/blob/abc123/src/module.py#L10-L42"
