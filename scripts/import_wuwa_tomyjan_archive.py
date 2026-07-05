#!/usr/bin/env python3
"""Import WuWa CN PC version snapshots from TomyJan/GenshinImpact-Client-Version."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sync_wuwa import (
    GAME_INFO,
    INDEX_PATH,
    LISTS_DIR,
    VERSIONS_PATH,
    WUWA_DATA,
    full_url,
    normalize_cdn,
    normalize_dest,
    resource_entries,
    summary_for,
    utc_now,
    version_key,
    write_entry_lists,
    write_json_if_changed,
)

ARCHIVE_SOURCE = "https://github.com/TomyJan/GenshinImpact-Client-Version/tree/master/WW/Win/Game/CN"
ARCHIVE_REPO = "https://github.com/TomyJan/GenshinImpact-Client-Version.git"
ARCHIVE_SUBDIR = Path("WW") / "Win" / "Game" / "CN"
REL_RE = re.compile(r"^REL(?P<version>\d+\.\d+\.\d+)\.json$")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_version(config_path: Path, resource_path: Path) -> dict[str, Any]:
    launcher = load_json(config_path)
    resource_index = load_json(resource_path)
    default = launcher.get("default", launcher)
    version = str(default.get("version") or config_path.stem.removeprefix("REL"))
    cdn_urls = [normalize_cdn(item.get("url", "")) for item in default.get("cdnList", []) if item.get("url")]
    base_url = str(default.get("resourcesBasePath") or default.get("config", {}).get("baseUrl") or "").rstrip("/") + "/"
    resources_path = str(default.get("resources") or "")
    files = resource_entries(resource_index, base_url, cdn_urls)
    links = {"files": write_entry_lists(f"{version}-files", files, f"WutheringWaves_{version}")}

    config = default.get("config") or {}
    index_file = str(config.get("indexFile") or resources_path)
    index_md5 = str(config.get("indexFileMd5") or "")
    resource_index_url = full_url(cdn_urls, index_file) if index_file else ""

    return {
        "version": version,
        "channel": "live",
        "region": "cn",
        "archive_source": ARCHIVE_SOURCE,
        "archive_file": posixpath.join("WW/Win/Game/CN", config_path.name),
        "resource_index": resource_index_url,
        "base_url": base_url,
        "cdn_urls": cdn_urls,
        "index_file_md5": index_md5,
        "size": sum(int(item.get("size") or 0) for item in files),
        "uncompressed_size": int(config.get("unCompressSize") or sum(int(item.get("size") or 0) for item in files)),
        "file_count": len(files),
        "files": files,
        "patches": [],
        "source_note": "imported from TomyJan/GenshinImpact-Client-Version WuWa CN archive",
        "links": links,
    }


def merge_version(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    if not old:
        return new
    merged = dict(old)
    for key in [
        "archive_source",
        "archive_file",
        "resource_index",
        "base_url",
        "cdn_urls",
        "index_file_md5",
        "size",
        "uncompressed_size",
        "file_count",
        "files",
        "links",
    ]:
        merged[key] = new[key]
    if not merged.get("patches"):
        merged["patches"] = new["patches"]
    if not merged.get("source_note"):
        merged["source_note"] = new["source_note"]
    return merged


def clone_archive_source() -> tempfile.TemporaryDirectory[str]:
    temp_dir = tempfile.TemporaryDirectory(prefix="wuwa-tomyjan-")
    target = Path(temp_dir.name) / "repo"
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            ARCHIVE_REPO,
            str(target),
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(target), "sparse-checkout", "set", str(ARCHIVE_SUBDIR).replace("\\", "/")],
        check=True,
    )
    return temp_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-dir",
        help="Path to WW/Win/Game/CN from TomyJan archive. When omitted, the script sparse-clones the upstream repo.",
    )
    args = parser.parse_args()

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.source_dir:
        source_dir = Path(args.source_dir)
    else:
        temp_dir = clone_archive_source()
        source_dir = Path(temp_dir.name) / "repo" / ARCHIVE_SUBDIR

    if not source_dir.exists():
        raise FileNotFoundError(source_dir)

    WUWA_DATA.mkdir(parents=True, exist_ok=True)
    LISTS_DIR.mkdir(parents=True, exist_ok=True)

    versions: dict[str, Any] = {}
    if VERSIONS_PATH.exists():
        versions = load_json(VERSIONS_PATH)

    imported = 0
    for config_path in sorted(source_dir.glob("REL*.json")):
        match = REL_RE.match(config_path.name)
        if not match:
            continue
        version = match.group("version")
        resource_path = source_dir / f"REL{version}_Res.json"
        if not resource_path.exists():
            print(f"skip {version}: missing {resource_path.name}")
            continue
        version_data = build_version(config_path, resource_path)
        versions[version] = merge_version(versions.get(version), version_data)
        imported += 1

    ordered_versions = dict(sorted(versions.items(), key=lambda pair: version_key(pair[0]), reverse=True))
    summaries = [summary_for(item) for item in ordered_versions.values()]
    current_version = summaries[0]["version"] if summaries else None
    generated_at = utc_now()
    current = ordered_versions.get(current_version or "", {})
    index_data = {
        "source": "Official Kuro Game launcher CDN API + TomyJan WuWa CN archive",
        "archive_source": ARCHIVE_SOURCE,
        "selected_launcher_index": current.get("launcher_index", ""),
        "last_checked_at": generated_at,
        "generated_at": generated_at,
        "game": GAME_INFO,
        "current_version": current_version,
        "version_count": len(summaries),
        "first_version": summaries[-1]["version"] if summaries else None,
        "latest_version": current_version,
        "total_file_bytes": sum(item["size"] for item in summaries),
        "total_patch_route_bytes": sum(route.get("size", 0) for route in current.get("patches", [])),
        "cdn_urls": current.get("cdn_urls", []),
        "versions": summaries,
    }

    write_json_if_changed(VERSIONS_PATH, ordered_versions)
    write_json_if_changed(INDEX_PATH, index_data)
    print(f"Imported {imported} WuWa CN versions from {source_dir}")
    if temp_dir:
        temp_dir.cleanup()


if __name__ == "__main__":
    main()
