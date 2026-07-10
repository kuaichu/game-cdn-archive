#!/usr/bin/env python3
"""Import the latest archived Endfield Windows resource manifests per game version."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = ROOT / "docs"
DEFAULT_ARCHIVE_ROOT = ROOT / "outputs" / "endfield-upstream"
DEFAULT_OUTPUT = DOCS_ROOT / "data" / "endfield" / "resources"
SOURCE_REPO = "https://github.com/daydreamer-json/ak-endfield-api-archive"
SOURCE_SITE = "https://ak-endfield-api-archive.daydreamer-json.cc/"
RESOURCE_INDEX = Path("output/akEndfield/launcher/game_resources/1/Windows/all.json")


def version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def docs_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(DOCS_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"{path} must be inside {DOCS_ROOT}") from exc


def decoded_manifest_path(archive_root: Path, resource_path: str, kind: str) -> Path:
    parsed = urlsplit(resource_path)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"invalid resource path: {resource_path}")
    relative = [unquote(part) for part in parsed.path.split("/") if part]
    return archive_root / "output" / "raw" / parsed.netloc / Path(*relative) / f"index_{kind}_dec.json"


def file_url(resource_path: str, name: str) -> str:
    return f"{resource_path.rstrip('/')}/{quote(name, safe='/')}"


def latest_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        version = str((row.get("req") or {}).get("version") or "")
        updated_at = str(row.get("updatedAt") or "")
        if not version or not updated_at:
            continue
        previous = selected.get(version)
        if previous is None or updated_at > str(previous.get("updatedAt") or ""):
            selected[version] = row
    return selected


def build_version(archive_root: Path, row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    request = row.get("req") or {}
    response = row.get("rsp") or {}
    version = str(request.get("version") or "")
    observed_at = str(row.get("updatedAt") or "")
    resource_version = str(response.get("res_version") or "")
    records: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []

    for resource in response.get("resources") or []:
        kind = str(resource.get("name") or "")
        resource_path = str(resource.get("path") or "")
        if kind not in {"main", "initial"} or not resource_path:
            continue
        decoded_path = decoded_manifest_path(archive_root, resource_path, kind)
        if not decoded_path.exists():
            raise FileNotFoundError(f"missing decoded {kind} manifest for {version}: {decoded_path}")
        payload = load_json(decoded_path)
        files = payload.get("files") or []
        if not isinstance(files, list):
            raise ValueError(f"invalid files array in {decoded_path}")

        start = len(records)
        for item in files:
            name = str(item.get("name") or "")
            if not name:
                raise ValueError(f"missing file name in {decoded_path}")
            records.append({
                "kind": kind,
                "path": name,
                "name": name.rsplit("/", 1)[-1],
                "size": int(item.get("size") or 0),
                "md5": str(item.get("md5") or ""),
                "hash": str(item.get("hash") or ""),
                "type": item.get("type"),
                "manifest": item.get("manifest"),
                "url": file_url(resource_path, name),
            })
        parsed = urlsplit(resource_path)
        manifests.append({
            "kind": kind,
            "resource_version": str(resource.get("version") or ""),
            "file_count": len(records) - start,
            "size": sum(int(item["size"]) for item in records[start:]),
            "source_index_url": f"{resource_path.rstrip('/')}/index_{kind}.json",
            "decoded_index_url": f"{SOURCE_REPO}/blob/main/{decoded_path.relative_to(archive_root).as_posix()}",
            "base_url": f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}",
        })

    records.sort(key=lambda item: (item["kind"], item["path"]))
    version_row = {
        "game_id": "endfield",
        "game_name": "明日方舟：终末地",
        "version": version,
        "platform": "Windows",
        "observed_at": observed_at,
        "resource_version": resource_version,
        "source": SOURCE_REPO,
        "manifests": manifests,
        "file_count": len(records),
        "size": sum(int(item["size"]) for item in records),
        "records": records,
    }
    summary = {
        "version": version,
        "platform": "Windows",
        "observed_at": observed_at,
        "resource_version": resource_version,
        "file_count": version_row["file_count"],
        "size": version_row["size"],
        "main_file_count": next((item["file_count"] for item in manifests if item["kind"] == "main"), 0),
        "initial_file_count": next((item["file_count"] for item in manifests if item["kind"] == "initial"), 0),
        "manifests": manifests,
    }
    return version_row, summary


def aria2_entry(record: dict[str, Any], output_dir: str) -> str:
    lines = [record["url"], f"  dir={output_dir}", f"  out={record['path']}"]
    if record.get("md5"):
        lines.append(f"  checksum=md5={record['md5']}")
    return "\n".join([*lines, ""])


def build(archive_root: Path, output: Path) -> None:
    rows = load_json(archive_root / RESOURCE_INDEX)
    if not isinstance(rows, list):
        raise ValueError(f"expected array in {archive_root / RESOURCE_INDEX}")

    selected = latest_rows(rows)
    summaries = []
    for version in sorted(selected, key=version_key, reverse=True):
        version_row, summary = build_version(archive_root, selected[version])
        version_path = output / "versions" / f"{version}.json"
        urls_path = output / "lists" / f"{version}.urls.txt"
        aria2_path = output / "lists" / f"{version}.aria2.txt"
        write_json(version_path, version_row)
        write_text(urls_path, "\n".join(item["url"] for item in version_row["records"]) + "\n")
        write_text(
            aria2_path,
            "\n".join(aria2_entry(item, f"Endfield_{version}_{version_row['resource_version']}") for item in version_row["records"]),
        )
        summary["links"] = {
            "json": docs_path(version_path),
            "urls": docs_path(urls_path),
            "aria2": docs_path(aria2_path),
        }
        summaries.append(summary)

    now = datetime.now(timezone.utc).isoformat()
    index = {
        "generated_at": now,
        "last_checked_at": now,
        "source": SOURCE_REPO,
        "source_site": SOURCE_SITE,
        "platform": "Windows",
        "selection_policy": "latest upstream observation per game version",
        "game": {
            "id": "endfield",
            "name": "明日方舟：终末地",
            "subName": "Arknights: Endfield",
            "shortName": "EF",
            "icon": "assets/icons/endfield.svg",
            "kind": "endfield",
        },
        "versions": summaries,
    }
    write_json(output / "index.json", index)
    print(f"endfield_resources_versions={len(summaries)}")
    print(f"endfield_resources_files={sum(item['file_count'] for item in summaries)}")
    print(f"endfield_resources_size={sum(item['size'] for item in summaries)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.archive_root, args.output)


if __name__ == "__main__":
    main()
