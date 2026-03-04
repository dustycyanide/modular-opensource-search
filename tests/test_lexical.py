from v2.adapters.lexical import build_snippet, is_noise_path


def test_build_snippet_returns_line_window() -> None:
    content = "\n".join(
        [
            "line one",
            "setup parser",
            "semantic code search entry point",
            "helper function",
            "line five",
        ]
    )
    snippet, start, end, score = build_snippet(content, "semantic code search")
    assert snippet is not None
    assert start <= 3 <= end
    assert score >= 1


def test_noise_path_detection() -> None:
    assert is_noise_path("vendor/lib/generated/file.py")
    assert not is_noise_path("src/search/engine.py")
