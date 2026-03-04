#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import re
from typing import Iterator
from urllib.parse import urlparse
import zipfile


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize CodeSearchNet raw archives for v2")
    parser.add_argument(
        "--dataset-root",
        default="data/external/codesearchnet",
        help="CodeSearchNet root directory",
    )
    parser.add_argument(
        "--languages",
        default=None,
        help="Comma-separated language filters (for smoke runs)",
    )
    parser.add_argument("--max-records", type=int, default=0, help="Optional record cap")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset_root = Path(args.dataset_root)
    raw_root = dataset_root / "raw"
    normalized_root = dataset_root / "normalized"
    normalized_root.mkdir(parents=True, exist_ok=True)

    selected_languages = {
        item.strip().lower() for item in (args.languages or "").split(",") if item.strip()
    }

    zip_files = sorted(raw_root.glob("*.zip"))
    if selected_languages:
        zip_files = [path for path in zip_files if path.stem.lower() in selected_languages]
    if not zip_files:
        raise FileNotFoundError(f"No language archives under {raw_root}")

    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    written_total = 0
    summary_records: dict[str, int] = {}

    for zip_path in zip_files:
        language = zip_path.stem.lower()
        out_path = normalized_root / f"{language}.jsonl"
        if out_path.exists():
            out_path.unlink()

        with out_path.open("w", encoding="utf-8") as out_handle:
            for partition, row in iterate_rows_from_zip(zip_path):
                normalized = normalize_row(row=row, language=language, partition=partition)
                if not normalized:
                    continue
                out_handle.write(json.dumps(normalized, ensure_ascii=True) + "\n")
                counts[language][partition] += 1
                written_total += 1
                if args.max_records > 0 and written_total >= args.max_records:
                    break
        summary_records[language] = sum(counts[language].values())
        if args.max_records > 0 and written_total >= args.max_records:
            break

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_root": str(dataset_root),
        "languages": summary_records,
        "partition_counts": {language: dict(partitions) for language, partitions in counts.items()},
        "total_records": written_total,
    }
    summary_path = normalized_root / "prepare_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote normalized corpus to {normalized_root}")
    print(f"Summary: {summary_path}")
    return 0


def iterate_rows_from_zip(zip_path: Path) -> Iterator[tuple[str, dict[str, object]]]:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.namelist():
            lower = member.lower()
            if lower.endswith("/"):
                continue
            if not (lower.endswith(".jsonl") or lower.endswith(".jsonl.gz")):
                continue
            partition = partition_from_member(member)
            with archive.open(member) as zipped_file:
                if lower.endswith(".gz"):
                    stream = gzip.GzipFile(fileobj=zipped_file)
                    text_handle = io.TextIOWrapper(stream, encoding="utf-8")
                else:
                    text_handle = io.TextIOWrapper(zipped_file, encoding="utf-8")

                with text_handle as handle:
                    for raw_line in handle:
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(row, dict):
                            yield partition, row


def normalize_row(*, row: dict[str, object], language: str, partition: str) -> dict[str, object] | None:
    code = str(row.get("code") or row.get("original_string") or "")
    docstring = str(row.get("docstring") or "")
    repo = str(row.get("repo") or "")
    path = str(row.get("path") or "").lstrip("/")
    url = str(row.get("url") or "")

    if not repo and url:
        repo = repo_from_url(url)
    if not path and url:
        path = path_from_url(url)
    if not repo or not path:
        return None

    code_tokens = tokens_from_field(row.get("code_tokens"), fallback=code)
    doc_tokens = tokens_from_field(row.get("docstring_tokens"), fallback=docstring)
    sha = str(row.get("sha") or "")
    func_name = str(row.get("func_name") or "")
    doc_id = normalize_doc_id(url=url, repo=repo, path=path)

    return {
        "doc_id": doc_id,
        "repo": repo,
        "language": language,
        "path": path,
        "func_name": func_name,
        "code": code,
        "docstring": docstring,
        "code_tokens": code_tokens,
        "docstring_tokens": doc_tokens,
        "sha": sha,
        "url": url,
        "partition": partition,
    }


def partition_from_member(member: str) -> str:
    lower = member.lower()
    if "train" in lower:
        return "train"
    if "valid" in lower:
        return "valid"
    if "test" in lower:
        return "test"
    return "unknown"


def normalize_doc_id(*, url: str, repo: str, path: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) >= 5 and parts[2] == "blob":
        owner, name = parts[0], parts[1]
        file_path = "/".join(parts[4:])
        if file_path:
            return f"{owner.lower()}/{name.lower()}/{file_path.lower()}"
    return f"{repo.strip().lower()}/{path.strip().lower()}"


def repo_from_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return ""


def path_from_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) >= 5 and parts[2] == "blob":
        return "/".join(parts[4:])
    return ""


def tokens_from_field(value: object, *, fallback: str) -> list[str]:
    if isinstance(value, list):
        out = [str(item).strip().lower() for item in value if str(item).strip()]
        if out:
            return out
    return [token.lower() for token in TOKEN_PATTERN.findall(fallback)]


if __name__ == "__main__":
    raise SystemExit(main())
