#!/usr/bin/env python3
"""Promote staged TomyJan WuWa shards into the formal static data set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WUWA_DIR = REPO_ROOT / "docs" / "data" / "wuwa"

BATCHES = {
    "1.x": ["1.0.2", "1.1.0", "1.2.0", "1.3.0", "1.4.0", "1.4.1", "1.4.2", "1.4.3"],
    "2.0-2.4": ["2.0.0", "2.0.1", "2.0.2", "2.0.3", "2.1.0", "2.1.1", "2.3.0", "2.4.0", "2.4.1"],
    "2.5-2.7": ["2.5.0", "2.5.1", "2.6.0", "2.6.1", "2.7.0"],
    "3.x": ["3.0.0", "3.0.1", "3.0.2", "3.0.3", "3.1.0", "3.1.2", "3.1.3", "3.2.1", "3.3.0"],
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def summary_from_version(version: dict) -> dict:
    summary = {
        "version": version["version"],
        "channel": version.get("channel", ""),
        "region": version.get("region", ""),
        "file_count": int(version.get("file_count") or len(version.get("files") or [])),
        "cdn_count": len(version.get("cdn_urls") or []),
        "patch_routes": len(version.get("patches") or []),
        "size": int(version.get("size") or 0),
        "uncompressed_size": int(version.get("uncompressed_size") or 0),
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
        if version.get(key):
            summary[key] = version[key]
    return summary


def write_named_lists(output_dir: Path, stem: str, root_dir: str, items: list[dict]) -> dict[str, str]:
    lists_dir = output_dir / "lists"
    lists_dir.mkdir(parents=True, exist_ok=True)

    json_path = lists_dir / f"{stem}.json"
    urls_path = lists_dir / f"{stem}.urls.txt"
    aria2_path = lists_dir / f"{stem}.aria2.txt"

    write_json(json_path, items)
    urls_path.write_text("\n".join(item["url"] for item in items) + "\n", encoding="utf-8")

    lines: list[str] = []
    for item in items:
        dest = item["dest"]
        parent = Path(dest).parent.as_posix()
        out = Path(dest).name
        lines.extend(item["urls"])
        lines.append(f"  dir={root_dir}/{parent}" if parent != "." else f"  dir={root_dir}")
        lines.append(f"  out={out}")
        if item.get("md5"):
            lines.append(f"  checksum=md5={item['md5']}")
        lines.append("")
    aria2_path.write_text("\n".join(lines), encoding="utf-8")

    prefix = "data/wuwa/lists"
    return {
        "json": f"{prefix}/{json_path.name}",
        "urls": f"{prefix}/{urls_path.name}",
        "aria2": f"{prefix}/{aria2_path.name}",
    }


def refresh_index(output_dir: Path) -> int:
    index_path = output_dir / "index.json"
    index = load_json(index_path)
    versions = []
    total_files = 0
    for shard_path in (output_dir / "versions").glob("*.json"):
        row = load_json(shard_path)
        versions.append(summary_from_version(row))
        total_files += len(row.get("files") or [])
    versions.sort(key=lambda item: version_key(item["version"]), reverse=True)
    index["versions"] = versions
    index["total_file_count"] = total_files
    write_json(index_path, index)
    return total_files


def mark_existing_self_collected(output_dir: Path) -> None:
    for shard_path in (output_dir / "versions").glob("*.json"):
        row = load_json(shard_path)
        row.setdefault("source", "self-collected")
        write_json(shard_path, row)
    refresh_index(output_dir)


def promote_versions(output_dir: Path, versions: list[str]) -> None:
    staging_dir = output_dir / "staging"
    version_dir = output_dir / "versions"
    for version in versions:
        source_path = staging_dir / f"{version}.json"
        target_path = version_dir / f"{version}.json"
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        if target_path.exists():
            raise FileExistsError(target_path)
        row = load_json(source_path)
        row["links"] = {
            "files": write_named_lists(
                output_dir,
                f"{version}-files",
                f"WutheringWaves_{version}",
                row.get("files") or [],
            )
        }
        write_json(target_path, row)
    refresh_index(output_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=WUWA_DIR)
    parser.add_argument("--mark-existing", action="store_true")
    parser.add_argument("--batch", choices=sorted(BATCHES))
    args = parser.parse_args()

    if args.mark_existing:
        mark_existing_self_collected(args.output)
        print("marked_existing=self-collected")
    if args.batch:
        promote_versions(args.output, BATCHES[args.batch])
        print(f"promoted_batch={args.batch}")
        print("promoted_versions=" + ",".join(BATCHES[args.batch]))
    if not args.mark_existing and not args.batch:
        parser.error("choose --mark-existing and/or --batch")


if __name__ == "__main__":
    main()
