#!/usr/bin/env python3
"""Populate WuWa release_date metadata from traceable local sources."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WUWA_DIR = REPO_ROOT / "docs" / "data" / "wuwa"
TOMYJAN_REPO = "https://github.com/TomyJan/GenshinImpact-Client-Version.git"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def clone_tomyjan() -> Path:
    target = Path(tempfile.mkdtemp(prefix="tomyjan-wuwa-dates-"))
    run_git(["clone", "--filter=blob:none", "--sparse", TOMYJAN_REPO, str(target)])
    run_git(["sparse-checkout", "set", "WW/Win/Game/CN"], cwd=target)
    return target


def parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def source_paths(version: str) -> list[str]:
    return [
        f"WW/Win/Game/CN/REL{version}.json",
        f"WW/Win/Game/CN/REL{version}_Res.json",
    ]


def git_first_added_meta(source: Path, path: str) -> tuple[str, str] | None:
    output = run_git(["log", "--diff-filter=A", "--format=%H%x09%cI", "--", path], cwd=source)
    rows = [line.split("\t", 1) for line in output.splitlines() if "\t" in line]
    if not rows:
        return None
    commit, committed_at = rows[-1]
    return committed_at, commit


def tomyjan_release_meta(source: Path, version: str) -> dict[str, str]:
    candidates = []
    for path in source_paths(version):
        meta = git_first_added_meta(source, path)
        if meta:
            committed_at, commit = meta
            candidates.append((parse_iso_datetime(committed_at), committed_at, commit, path))
    if not candidates:
        raise RuntimeError(f"No TomyJan git date found for WuWa {version}")
    _, committed_at, commit, path = max(candidates, key=lambda item: item[0])
    return {
        "release_date": committed_at,
        "release_date_source": "tomyjan_git_first_added",
        "release_date_source_commit": commit,
        "release_date_note": (
            f"First git-add timestamp for {path} in TomyJan's WW CN archive; "
            "this is an archival timestamp, not an official announcement time."
        ),
    }


def self_collected_release_meta(row: dict[str, Any]) -> dict[str, str]:
    last_modified = row.get("last_modified")
    if not last_modified:
        raise RuntimeError(f"WuWa {row.get('version')} has no last_modified value")
    source = row.get("last_modified_source") or "http"
    return {
        "release_date": last_modified,
        "release_date_source": f"{source}_last_modified",
        "release_date_note": "Derived from the HTTP Last-Modified header of the official WuWa CDN resource.",
    }


def summary_from_version(row: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "version": row["version"],
        "channel": row.get("channel", ""),
        "region": row.get("region", ""),
        "file_count": int(row.get("file_count") or len(row.get("files") or [])),
        "cdn_count": len(row.get("cdn_urls") or []),
        "patch_routes": len(row.get("patches") or []),
        "size": int(row.get("size") or 0),
        "uncompressed_size": int(row.get("uncompressed_size") or 0),
    }
    for key in [
        "source",
        "source_note",
        "release_stage",
        "source_repo",
        "source_commit",
        "imported_at",
        "release_date",
        "release_date_source",
        "last_modified",
        "last_modified_source",
        "last_modified_url",
        "last_modified_status",
    ]:
        if row.get(key):
            summary[key] = row[key]
    return summary


def update_dates(wuwa_dir: Path, tomyjan_source: Path | None) -> None:
    cleanup_path: Path | None = None
    if tomyjan_source is None:
        tomyjan_source = clone_tomyjan()
        cleanup_path = tomyjan_source
    try:
        version_dir = wuwa_dir / "versions"
        versions: dict[str, dict[str, Any]] = {}
        for path in sorted(version_dir.glob("*.json")):
            row = load_json(path)
            source = row.get("source")
            if source == "tomyjan-import":
                row.update(tomyjan_release_meta(tomyjan_source, row["version"]))
            else:
                row.update(self_collected_release_meta(row))
            write_json(path, row)
            versions[row["version"]] = row

        index = load_json(wuwa_dir / "index.json")
        summaries = [summary_from_version(row) for row in versions.values()]
        summaries.sort(key=lambda item: version_key(item["version"]), reverse=True)
        index["versions"] = summaries
        write_json(wuwa_dir / "index.json", index)
        print(f"updated_wuwa_release_dates={len(summaries)}")
    finally:
        if cleanup_path:
            shutil.rmtree(cleanup_path, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wuwa-dir", type=Path, default=WUWA_DIR)
    parser.add_argument("--tomyjan-source", type=Path, default=None)
    args = parser.parse_args()
    update_dates(args.wuwa_dir, args.tomyjan_source)


if __name__ == "__main__":
    main()
