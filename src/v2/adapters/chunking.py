from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..contracts import ArtifactChunk


TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".xml",
    ".html",
    ".css",
    ".sh",
}

NOISE_SEGMENTS = {
    "vendor",
    "node_modules",
    "dist",
    "build",
    "target",
    "third_party",
    "__pycache__",
    ".venv",
    "generated",
}


@dataclass(frozen=True)
class ChunkingConfig:
    max_file_bytes: int = 250_000
    chunk_lines: int = 40
    overlap_lines: int = 8
    min_nonblank_lines: int = 3


class RepositoryChunkBuilder:
    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.config = config or ChunkingConfig()

    def should_include_path(self, rel_path: str) -> bool:
        suffix = Path(rel_path).suffix.lower()
        return suffix in TEXT_EXTENSIONS and not is_noise_path(rel_path)

    def build_chunks(
        self,
        *,
        repo: str,
        commit_sha: str,
        rel_path: str,
        text: str,
        base_metadata: dict[str, object],
    ) -> list[ArtifactChunk]:
        lines = text.splitlines()
        nonblank_lines = [line for line in lines if line.strip()]
        if len(nonblank_lines) < self.config.min_nonblank_lines:
            return []

        chunk_size = max(1, self.config.chunk_lines)
        overlap = min(max(0, self.config.overlap_lines), chunk_size - 1)
        step = chunk_size - overlap

        chunks: list[ArtifactChunk] = []
        for start in range(0, len(lines), step):
            window = lines[start : start + chunk_size]
            if not window:
                break

            start_line = start + 1
            end_line = start + len(window)
            chunks.append(
                ArtifactChunk(
                    repo=repo,
                    commit_sha=commit_sha,
                    path=rel_path,
                    language=language_from_path(rel_path),
                    symbol=None,
                    start_line=start_line,
                    end_line=end_line,
                    content="\n".join(window),
                    metadata=dict(base_metadata),
                )
            )

            if end_line >= len(lines):
                break

        return chunks


def language_from_path(path: str) -> str:
    extension = Path(path).suffix.lower()
    return {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".jsx": "JavaScript",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".rb": "Ruby",
        ".php": "PHP",
        ".cs": "C#",
    }.get(extension, "Text")


def is_noise_path(path: str) -> bool:
    lower = path.lower()
    if ".min." in lower:
        return True
    segments = set(segment for segment in lower.split("/") if segment)
    if segments.intersection(NOISE_SEGMENTS):
        return True
    if lower.endswith(".lock"):
        return True
    return False
