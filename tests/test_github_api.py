from __future__ import annotations

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import parse_qs, urlparse

from v2.adapters.github_api import GitHubClient
from v2.adapters.ingestion import IngestionConfig, RepositoryChunkIngestor
from v2.contracts import RepoCandidate


def test_github_client_tree_and_text_helpers() -> None:
    server = _start_fixture_server()
    try:
        client = GitHubClient(token="test", base_url=server.base_url)

        tree = client.list_tree("acme", "demo", "abc123")
        text = client.get_text_file("acme", "demo", "src/parser.py", ref="abc123")

        assert tree["truncated"] is False
        assert tree["tree"][0]["path"] == "src/parser.py"
        assert "parse_json" in text
    finally:
        server.close()


def test_remote_ingestor_uses_tree_and_skips_noise_paths() -> None:
    server = _start_fixture_server()
    try:
        ingestor = RepositoryChunkIngestor(
            GitHubClient(token="test", base_url=server.base_url),
            config=IngestionConfig(max_files_per_repo=10, chunk_lines=4, overlap_lines=1, min_nonblank_lines=1),
        )
        chunks = ingestor.ingest(
            [
                RepoCandidate(
                    host="github.com",
                    owner="acme",
                    name="demo",
                    clone_url="https://github.com/acme/demo.git",
                    metadata={"repo_url": "https://github.com/acme/demo"},
                )
            ]
        )

        assert chunks
        assert {chunk.path for chunk in chunks} == {"src/parser.py"}
        assert all(chunk.metadata["tree_truncated"] is False for chunk in chunks)
        assert not any("vendor/copied.py" in path for path in server.requested_paths)
        assert "/repos/acme/demo/git/trees/abc123" in server.requested_paths
    finally:
        server.close()


class _FixtureServer:
    def __init__(self, httpd: ThreadingHTTPServer, thread: threading.Thread, state: dict[str, object]) -> None:
        self.httpd = httpd
        self.thread = thread
        self.state = state
        host, port = httpd.server_address
        self.base_url = f"http://{host}:{port}"

    @property
    def requested_paths(self) -> list[str]:
        return self.state["requested_paths"]  # type: ignore[return-value]

    def close(self) -> None:
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


def _start_fixture_server() -> _FixtureServer:
    state: dict[str, object] = {"requested_paths": []}
    content = base64.b64encode(
        "\n".join(
            [
                "import json",
                "",
                "def parse_json(payload):",
                "    return json.loads(payload)",
            ]
        ).encode("utf-8")
    ).decode("ascii")

    routes: dict[tuple[str, str], dict[str, object]] = {
        ("GET", "/repos/acme/demo/branches/main"): {"commit": {"sha": "abc123"}},
        ("GET", "/repos/acme/demo/git/trees/abc123"): {
            "truncated": False,
            "tree": [
                {"path": "src/parser.py", "type": "blob"},
                {"path": "vendor/copied.py", "type": "blob"},
            ],
        },
        ("GET", "/repos/acme/demo/contents/src/parser.py"): {"content": content},
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            state["requested_paths"].append(parsed.path)  # type: ignore[union-attr]
            key = ("GET", parsed.path)
            payload = routes.get(key)
            if payload is None:
                self.send_response(404)
                self.end_headers()
                return

            if parsed.path.endswith("/contents/src/parser.py"):
                params = parse_qs(parsed.query)
                if params.get("ref") != ["abc123"]:
                    self.send_response(400)
                    self.end_headers()
                    return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            del format, args

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return _FixtureServer(httpd, thread, state)
