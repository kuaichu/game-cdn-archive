#!/usr/bin/env python3
"""Generate staged WuWa version shards from TomyJan's CN archive data."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
WUWA_DIR = REPO_ROOT / "docs" / "data" / "wuwa"
STAGING_DIR = WUWA_DIR / "staging"
TOMYJAN_REPO = "https://github.com/TomyJan/GenshinImpact-Client-Version.git"
TARGET_VERSIONS = [
    "1.0.2",
    "1.1.0",
    "1.2.0",
    "1.3.0",
    "1.4.0",
    "1.4.1",
    "1.4.2",
    "1.4.3",
    "2.0.0",
    "2.0.1",
    "2.0.2",
    "2.0.3",
    "2.1.0",
    "2.1.1",
    "2.3.0",
    "2.4.0",
    "2.4.1",
    "2.5.0",
    "2.5.1",
    "2.6.0",
    "2.6.1",
    "2.7.0",
    "3.0.0",
    "3.0.1",
    "3.0.2",
    "3.0.3",
    "3.1.0",
    "3.1.2",
    "3.1.3",
    "3.2.1",
    "3.3.0",
]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    target = Path(tempfile.mkdtemp(prefix="tomyjan-ww-"))
    run_git(["clone", "--depth", "1", "--filter=blob:none", "--sparse", TOMYJAN_REPO, str(target)])
    run_git(["sparse-checkout", "set", "WW"], cwd=target)
    return target


def repo_commit(source: Path) -> str:
    try:
        return run_git(["rev-parse", "HEAD"], cwd=source)
    except subprocess.CalledProcessError:
        return ""


def clean_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            quote(parts.path, safe="/%"),
            quote(parts.query, safe="=&%:/?+"),
            parts.fragment,
        )
    )


def join_url(base: str, path: str) -> str:
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def normalize_cdn_urls(default: dict) -> list[str]:
    urls = []
    for item in default.get("cdnList") or []:
        url = str(item.get("url") or "").rstrip("/")
        if url and url not in urls:
            urls.append(url)
    return urls


def normalize_dest(value: str) -> str:
    return str(value or "").replace("\\", "/").lstrip("/")


def as_int(value) -> int:
    return int(value or 0)


def unconvertible(version: str, reason: str, detail: str = "") -> dict:
    item = {"version": version, "reason": reason}
    if detail:
        item["detail"] = detail
    return item


def source_paths(version: str) -> list[str]:
    return [
        f"WW/Win/Game/CN/REL{version}.json",
        f"WW/Win/Game/CN/REL{version}_Res.json",
    ]


def convert_file(entry: dict, cdn_urls: list[str], base_url: str) -> dict:
    dest = normalize_dest(entry.get("dest") or "")
    item = {
        "dest": dest,
        "name": Path(dest).name,
        "md5": str(entry.get("md5") or ""),
        "size": as_int(entry.get("size")),
        "url": clean_url(join_url(cdn_urls[0], f"{base_url.rstrip('/')}/{dest}")),
        "urls": [
            clean_url(join_url(cdn, f"{base_url.rstrip('/')}/{dest}"))
            for cdn in cdn_urls
        ],
    }
    if entry.get("sampleHash"):
        item["sample_hash"] = str(entry["sampleHash"])
    return item


def convert_patch(patch: dict, cdn_urls: list[str], to_version: str) -> dict:
    index_file = str(patch.get("indexFile") or "")
    base_url = str(patch.get("baseUrl") or "")
    return {
        "from": str(patch.get("version") or ""),
        "to": to_version,
        "size": as_int(patch.get("size")),
        "uncompressed_size": as_int(patch.get("unCompressSize")),
        "index_file_md5": str(patch.get("indexFileMd5") or ""),
        "index_file": index_file,
        "index_url": clean_url(join_url(cdn_urls[0], index_file)) if index_file else "",
        "base_url": base_url,
    }


def version_source(rel: dict, version: str) -> tuple[str, str, str, int, int, list[dict], str]:
    default = rel.get("default")
    if not isinstance(default, dict):
        raise ValueError("missing default object")

    config = default.get("config")
    if isinstance(config, dict) and config.get("indexFile") and config.get("baseUrl"):
        version_id = str(config.get("version") or version)
        index_file = str(config["indexFile"])
        base_url = str(config["baseUrl"])
        size = as_int(config.get("size"))
        uncompressed_size = as_int(config.get("unCompressSize"))
        patches = [
            convert_patch(item, normalize_cdn_urls(default), version_id)
            for item in config.get("patchConfig") or []
            if isinstance(item, dict)
        ]
        return version_id, index_file, base_url, size, uncompressed_size, patches, str(
            config.get("indexFileMd5") or ""
        )

    if default.get("resources") and default.get("resourcesBasePath"):
        version_id = str(default.get("version") or version)
        return (
            version_id,
            str(default["resources"]),
            str(default["resourcesBasePath"]),
            0,
            0,
            [],
            "",
        )

    raise ValueError("missing config.indexFile/baseUrl or resources/resourcesBasePath")


def convert_version(source: Path, version: str, imported_at: str, source_commit: str) -> tuple[dict | None, dict | None]:
    rel_path = source / "WW" / "Win" / "Game" / "CN" / f"REL{version}.json"
    res_path = source / "WW" / "Win" / "Game" / "CN" / f"REL{version}_Res.json"

    if not rel_path.exists():
        return None, unconvertible(version, "missing REL json", str(rel_path))
    if not res_path.exists():
        return None, unconvertible(version, "missing REL_Res json", str(res_path))

    rel = load_json(rel_path)
    res = load_json(res_path)
    default = rel.get("default") or {}
    cdn_urls = normalize_cdn_urls(default)
    if not cdn_urls:
        return None, unconvertible(version, "missing cdnList urls")

    try:
        version_id, index_file, base_url, size, uncompressed_size, patches, index_file_md5 = version_source(
            rel, version
        )
    except ValueError as exc:
        return None, unconvertible(version, str(exc))

    if version_id != version:
        return None, unconvertible(version, "version mismatch", version_id)

    raw_files = res.get("resource")
    if not isinstance(raw_files, list) or not raw_files:
        return None, unconvertible(version, "missing non-empty resource array")

    files: list[dict] = []
    for index, entry in enumerate(raw_files):
        if not isinstance(entry, dict):
            return None, unconvertible(version, "resource entry is not an object", str(index))
        missing = [
            field
            for field in ["dest", "md5", "size"]
            if entry.get(field) in (None, "")
        ]
        if missing:
            return None, unconvertible(version, "resource entry missing fields", f"{index}:{','.join(missing)}")
        files.append(convert_file(entry, cdn_urls, base_url))

    total_size = sum(item["size"] for item in files)
    if not size:
        size = total_size
    if not uncompressed_size:
        uncompressed_size = total_size

    return (
        {
            "version": version,
            "channel": "live",
            "region": "cn",
            "source": "tomyjan-import",
            "source_repo": TOMYJAN_REPO,
            "source_commit": source_commit,
            "source_files": source_paths(version),
            "imported_at": imported_at,
            "resource_index": clean_url(join_url(cdn_urls[0], index_file)),
            "base_url": base_url,
            "cdn_urls": cdn_urls,
            "index_file_md5": index_file_md5,
            "size": size,
            "uncompressed_size": uncompressed_size,
            "file_count": len(files),
            "files": files,
            "patches": patches,
            "source_note": "converted from TomyJan WW/Win/Game/CN archive into staging only",
        },
        None,
    )


def validate_payload(version: str, payload: dict) -> list[str]:
    errors: list[str] = []
    for field in ["version", "channel", "region", "source", "imported_at", "files", "patches"]:
        if field not in payload:
            errors.append(f"{version}:missing:{field}")
    if payload.get("version") != version:
        errors.append(f"{version}:version_mismatch:{payload.get('version')}")
    if payload.get("source") != "tomyjan-import":
        errors.append(f"{version}:bad_source:{payload.get('source')}")
    if not isinstance(payload.get("files"), list) or not payload.get("files"):
        errors.append(f"{version}:files_not_non_empty")
        return errors
    if not isinstance(payload.get("patches"), list):
        errors.append(f"{version}:patches_not_array")
    if as_int(payload.get("file_count")) != len(payload["files"]):
        errors.append(f"{version}:file_count:{payload.get('file_count')}!={len(payload['files'])}")
    for index, entry in enumerate(payload["files"]):
        if not isinstance(entry, dict):
            errors.append(f"{version}:file:{index}:not_object")
            continue
        for field in ["dest", "md5", "size", "url"]:
            if entry.get(field) in (None, ""):
                errors.append(f"{version}:file:{index}:missing:{field}")
        if as_int(entry.get("size")) <= 0:
            errors.append(f"{version}:file:{index}:bad_size:{entry.get('size')}")
    return errors


def validate_staging(output: Path = STAGING_DIR) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for version in TARGET_VERSIONS:
        path = output / f"{version}.json"
        if not path.exists():
            continue
        errors.extend(validate_payload(version, load_json(path)))
    unconvertible_path = output / "_unconvertible.json"
    if not unconvertible_path.exists():
        errors.append("missing _unconvertible.json")
    return not errors, errors


def generate(source: Path, output: Path) -> tuple[list[str], list[dict]]:
    imported_at = datetime.now(timezone.utc).isoformat()
    source_commit = repo_commit(source)
    converted: list[str] = []
    unconvertible_items: list[dict] = []
    output.mkdir(parents=True, exist_ok=True)

    for version in TARGET_VERSIONS:
        payload, failed = convert_version(source, version, imported_at, source_commit)
        if failed:
            unconvertible_items.append(failed)
            continue
        write_json(output / f"{version}.json", payload)
        converted.append(version)

    write_json(
        output / "_unconvertible.json",
        {
            "source": "tomyjan-import",
            "source_repo": TOMYJAN_REPO,
            "source_commit": source_commit,
            "generated_at": imported_at,
            "items": unconvertible_items,
        },
    )
    return converted, unconvertible_items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=None, help="TomyJan repo checkout path")
    parser.add_argument("--output", type=Path, default=STAGING_DIR)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    if args.validate_only:
        ok, errors = validate_staging(args.output)
        print(f"staging_validation={'PASS' if ok else 'FAIL'}")
        if errors:
            print("\n".join(errors))
            raise SystemExit(1)
        return

    cleanup_path: Path | None = None
    source = args.source
    if source is None:
        source = clone_tomyjan()
        cleanup_path = source
    try:
        converted, unconvertible_items = generate(source, args.output)
        ok, errors = validate_staging(args.output)
        print(f"converted={len(converted)}")
        print("converted_versions=" + ",".join(converted))
        print(f"unconvertible={len(unconvertible_items)}")
        print(f"staging_validation={'PASS' if ok else 'FAIL'}")
        if errors:
            print("\n".join(errors))
            raise SystemExit(1)
    finally:
        if cleanup_path:
            shutil.rmtree(cleanup_path, ignore_errors=True)


if __name__ == "__main__":
    main()
