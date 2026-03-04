#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import requests


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch CodeSearchNet assets with resume + checksums")
    parser.add_argument(
        "--output-root",
        default="data/external/codesearchnet",
        help="Dataset output directory",
    )
    parser.add_argument(
        "--manifest",
        default="scripts/datasets/manifest_codesearchnet.json",
        help="Path to manifest JSON",
    )
    parser.add_argument(
        "--languages",
        default=None,
        help="Comma-separated languages for raw archives (resources always included)",
    )
    parser.add_argument(
        "--skip-resources",
        action="store_true",
        help="Skip downloading queries.csv and annotationStore.csv",
    )
    parser.add_argument("--timeout", type=int, default=120, help="HTTP timeout seconds")
    parser.add_argument("--force", action="store_true", help="Redownload files even if present")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    manifest_path = Path(args.manifest)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets = payload.get("assets", [])
    if not isinstance(assets, list) or not assets:
        raise ValueError(f"No assets in manifest: {manifest_path}")

    selected_languages = {
        part.strip().lower() for part in (args.languages or "").split(",") if part.strip()
    }

    session = requests.Session()
    session.headers.update({"User-Agent": "modular-opensource-v2-dataset-fetch"})

    local_entries: list[dict[str, object]] = []
    selected_assets = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and _asset_selected(
            str(asset.get("name") or ""),
            selected_languages=selected_languages,
            include_resources=not args.skip_resources,
        )
    ]
    if not selected_assets:
        raise ValueError("No assets selected after applying filters")

    for asset in selected_assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "").strip()
        url = str(asset.get("url") or "").strip()
        if not name or not url:
            continue

        expected_sha = str(asset.get("sha256") or "").strip().lower() or None
        expected_size = _parse_optional_int(asset.get("size_bytes"))

        destination = output_root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        download_with_resume(
            session=session,
            url=url,
            destination=destination,
            timeout=args.timeout,
            force=args.force,
        )
        actual_size = destination.stat().st_size
        actual_sha = sha256_file(destination)
        if expected_sha and actual_sha.lower() != expected_sha:
            raise ValueError(
                f"Checksum mismatch for {name}: expected {expected_sha}, got {actual_sha}"
            )
        if expected_size is not None and actual_size != expected_size:
            raise ValueError(
                f"Size mismatch for {name}: expected {expected_size}, got {actual_size}"
            )
        local_entries.append(
            {
                "name": name,
                "url": url,
                "size_bytes": actual_size,
                "sha256": actual_sha,
                "expected_size_bytes": expected_size,
                "expected_sha256": expected_sha,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    local_manifest = {
        "dataset": payload.get("dataset", "codesearchnet-v2"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entries": local_entries,
    }
    local_manifest_path = output_root / "manifest.local.json"
    local_manifest_path.write_text(json.dumps(local_manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(local_entries)} assets and manifest: {local_manifest_path}")
    return 0


def _asset_selected(name: str, *, selected_languages: set[str], include_resources: bool) -> bool:
    clean_name = name.strip().lower()
    if not clean_name:
        return False
    if clean_name.startswith("resources/"):
        return include_resources
    if clean_name.startswith("raw/") and clean_name.endswith(".zip"):
        if not selected_languages:
            return True
        language = Path(clean_name).stem
        return language in selected_languages
    return True


def _parse_optional_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def download_with_resume(
    *,
    session: requests.Session,
    url: str,
    destination: Path,
    timeout: int,
    force: bool,
) -> None:
    if force and destination.exists():
        destination.unlink()

    existing_size = destination.stat().st_size if destination.exists() else 0
    headers: dict[str, str] = {}
    if existing_size > 0:
        headers["Range"] = f"bytes={existing_size}-"

    response = session.get(url, stream=True, timeout=timeout, headers=headers)
    response.raise_for_status()

    if response.status_code == 200 and existing_size > 0:
        destination.unlink(missing_ok=True)
        existing_size = 0

    mode = "ab" if existing_size > 0 and response.status_code == 206 else "wb"
    with destination.open(mode) as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            handle.write(chunk)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
