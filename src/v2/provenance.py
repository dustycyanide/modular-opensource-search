from __future__ import annotations


def build_commit_permalink(
    repo_url: str,
    commit_sha: str,
    path: str,
    start_line: int,
    end_line: int,
) -> str:
    """Build a GitHub-style commit permalink with line anchors."""
    base = repo_url[:-4] if repo_url.endswith(".git") else repo_url
    clean_base = base.rstrip("/")
    clean_path = path.lstrip("/")
    return f"{clean_base}/blob/{commit_sha}/{clean_path}#L{start_line}-L{end_line}"
