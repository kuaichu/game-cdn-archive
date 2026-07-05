#!/usr/bin/env python3
"""Sync Wuthering Waves (鸣潮) CN PC CDN metadata."""

from __future__ import annotations

import gzip
import json
import posixpath
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WUWA_DATA = ROOT / "docs" / "data" / "wuwa"
LISTS_DIR = WUWA_DATA / "lists"
INDEX_PATH = WUWA_DATA / "index.json"
VERSIONS_PATH = WUWA_DATA / "versions.json"
VERSIONS_SHARDS_DIR = WUWA_DATA / "versions"
VERSIONS_SHARD_MAX_BYTES = 24_000_000
VERSIONS_SHARD_FORMAT = "wuwa_versions_shards_v1"

GAME_CLIENT_INDEX = (
    "https://prod-cn-alicdn-gamestarter.kurogame.com/launcher/game/G152/"
    "10003_Y8xXrXk65DqFHEDgApn3cpK5lfczpFx5/index.json"
)

SOURCE_DESC = "Official Kuro Game launcher CDN API"
TOMYJAN_ARCHIVE_SOURCE = "https://github.com/TomyJan/GenshinImpact-Client-Version/tree/master/WW/Win/Game/CN"

GAME_INFO = {
    "id": "wuwa",
    "name": "鸣潮",
    "subName": "Wuthering Waves",
    "shortName": "WW",
    "kind": "wuwa",
    "icon": "assets/icons/wuwa.png",
    "platform": "Windows PC",
    "region": "cn",
    "config_url": GAME_CLIENT_INDEX,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fetch_json(url: str, timeout: int = 45) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "game-cdn-archive/1.0",
            "Accept-Encoding": "gzip, deflate",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8"))


def write_json_if_changed(path: Path, data: Any, indent: int = 2) -> bool:
    text = json.dumps(data, ensure_ascii=False, indent=indent) + "\n"
    if path.exists():
        old_text = path.read_text(encoding="utf-8")
        if old_text == text:
            return False
        try:
            if json.loads(old_text) == data:
                return False
        except json.JSONDecodeError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def json_text(data: Any, indent: int = 2) -> str:
    return json.dumps(data, ensure_ascii=False, indent=indent) + "\n"


def json_size(data: Any, indent: int = 2) -> int:
    return len(json_text(data, indent=indent).encode("utf-8"))


def write_text_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def shard_public_path(path: Path) -> str:
    return path.relative_to(ROOT / "docs").as_posix()


def resolve_public_path(path: str) -> Path:
    normalized = path.lstrip("/")
    if normalized.startswith("data/"):
        return ROOT / "docs" / normalized
    return WUWA_DATA / normalized


def load_versions_archive() -> dict[str, Any]:
    if not VERSIONS_PATH.exists():
        return {}

    data = json.loads(VERSIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}

    if data.get("format") != VERSIONS_SHARD_FORMAT:
        return data

    versions: dict[str, Any] = {}
    for shard in data.get("shards", []):
        shard_path = resolve_public_path(str(shard.get("path") or ""))
        if not shard_path.exists():
            continue
        shard_data = json.loads(shard_path.read_text(encoding="utf-8"))
        versions.update(shard_data.get("versions", shard_data))
    return versions


def split_versions_into_shards(versions: dict[str, Any]) -> list[dict[str, Any]]:
    shards: list[dict[str, Any]] = []
    current: dict[str, Any] = {}

    for version, version_data in versions.items():
        candidate = {**current, version: version_data}
        if current and json_size({"versions": candidate}) > VERSIONS_SHARD_MAX_BYTES:
            shards.append(current)
            current = {version: version_data}
        else:
            current = candidate

    if current:
        shards.append(current)
    return shards


def cleanup_old_version_shards(keep: set[Path]) -> None:
    if not VERSIONS_SHARDS_DIR.exists():
        return
    for path in VERSIONS_SHARDS_DIR.glob("versions_*.json"):
        if path not in keep:
            path.unlink()


def write_versions_archive(versions: dict[str, Any], generated_at: str) -> dict[str, Any]:
    VERSIONS_SHARDS_DIR.mkdir(parents=True, exist_ok=True)
    shard_maps = split_versions_into_shards(versions)
    shard_infos: list[dict[str, Any]] = []
    written_paths: set[Path] = set()

    for index, shard_versions in enumerate(shard_maps, start=1):
        shard_path = VERSIONS_SHARDS_DIR / f"versions_{index:03d}.json"
        shard_data = {
            "format": VERSIONS_SHARD_FORMAT,
            "generated_at": generated_at,
            "versions": shard_versions,
        }
        write_json_if_changed(shard_path, shard_data)
        size = shard_path.stat().st_size
        written_paths.add(shard_path)
        shard_infos.append(
            {
                "path": shard_public_path(shard_path),
                "versions": list(shard_versions.keys()),
                "bytes": size,
            }
        )

    cleanup_old_version_shards(written_paths)
    manifest = {
        "format": VERSIONS_SHARD_FORMAT,
        "generated_at": generated_at,
        "version_count": len(versions),
        "max_shard_bytes": VERSIONS_SHARD_MAX_BYTES,
        "shard_count": len(shard_infos),
        "shards": shard_infos,
    }
    write_json_if_changed(VERSIONS_PATH, manifest)
    return manifest


def normalize_cdn(url: str) -> str:
    return url.rstrip("/")


def normalize_dest(dest: str) -> str:
    return dest.replace("\\", "/").lstrip("/")


def join_url(base: str, dest: str) -> str:
    return f"{base.rstrip('/')}/{normalize_dest(dest)}"


def full_url(cdn_urls: list[str], path: str) -> str:
    return join_url(cdn_urls[0], path)


def resource_entries(resource_index: dict[str, Any], base_url: str, cdn_urls: list[str]) -> list[dict[str, Any]]:
    resources = resource_index.get("resource") or resource_index.get("resources") or []
    entries: list[dict[str, Any]] = []
    for item in resources:
        dest = normalize_dest(str(item.get("dest") or item.get("path") or item.get("name") or ""))
        if not dest:
            continue
        urls = [join_url(f"{cdn}/{base_url}", dest) for cdn in cdn_urls]
        entries.append(
            {
                "dest": dest,
                "name": posixpath.basename(dest),
                "md5": item.get("md5", ""),
                "size": int(item.get("size") or item.get("fileSize") or 0),
                "url": urls[0],
                "urls": urls,
            }
        )
    return entries


def write_entry_lists(prefix: str, entries: list[dict[str, Any]], download_root: str) -> dict[str, str]:
    json_path = LISTS_DIR / f"{prefix}.json"
    urls_path = LISTS_DIR / f"{prefix}.urls.txt"
    aria2_path = LISTS_DIR / f"{prefix}.aria2.txt"

    write_json_if_changed(json_path, entries)
    write_text_if_changed(urls_path, "".join(f"{entry['url']}\n" for entry in entries))

    blocks: list[str] = []
    for entry in entries:
        dest = entry["dest"]
        directory = posixpath.dirname(dest)
        target_dir = f"{download_root}/{directory}" if directory else download_root
        block = [*entry["urls"], f"  dir={target_dir}", f"  out={entry['name']}"]
        if entry.get("md5"):
            block.append(f"  checksum=md5={entry['md5']}")
        blocks.append("\n".join(block))
    write_text_if_changed(aria2_path, "\n\n".join(blocks) + ("\n" if blocks else ""))

    return {
        "json": f"data/wuwa/lists/{json_path.name}",
        "urls": f"data/wuwa/lists/{urls_path.name}",
        "aria2": f"data/wuwa/lists/{aria2_path.name}",
    }


def route_from_patch(patch: dict[str, Any], current_version: str, cdn_urls: list[str]) -> dict[str, Any]:
    from_version = str(patch.get("version") or "")
    index_file = str(patch.get("indexFile") or "")
    base_url = str(patch.get("baseUrl") or "")
    route = {
        "from": from_version,
        "to": current_version,
        "size": int(patch.get("size") or 0),
        "uncompressed_size": int(patch.get("unCompressSize") or 0),
        "index_file_md5": patch.get("indexFileMd5", ""),
        "index_file": index_file,
        "index_url": full_url(cdn_urls, index_file) if index_file else "",
        "base_url": base_url,
        "kind": "resource_patch" if "/resources/" in base_url else "file_update",
    }
    if patch.get("ext"):
        route["ext"] = patch["ext"]
    return route


def enrich_route(route: dict[str, Any], cdn_urls: list[str]) -> dict[str, Any]:
    if not route.get("index_url") or not route.get("base_url"):
        return route
    try:
        resource_index = fetch_json(str(route["index_url"]))
        parts = resource_entries(resource_index, str(route["base_url"]), cdn_urls)
        route["file_count"] = len(parts)
        route["parts"] = parts
    except Exception as exc:  # noqa: BLE001 - archive should keep partial route metadata.
        route["fetch_error"] = str(exc)
    return route


def build_current_version(config: dict[str, Any], launcher_url: str, cdn_urls: list[str]) -> dict[str, Any]:
    version = str(config.get("version") or "")
    base_url = str(config.get("baseUrl") or "")
    index_file = str(config.get("indexFile") or "")
    index_url = full_url(cdn_urls, index_file)
    resource_index = fetch_json(index_url)
    files = resource_entries(resource_index, base_url, cdn_urls)
    links = {"files": write_entry_lists(f"{version}-files", files, f"WutheringWaves_{version}")}

    patch_routes = [route_from_patch(patch, version, cdn_urls) for patch in config.get("patchConfig", [])]
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(enrich_route, route, cdn_urls) for route in patch_routes]
        patch_routes = [future.result() for future in as_completed(futures)]
    patch_routes.sort(key=lambda route: version_key(str(route.get("from") or "0.0.0")), reverse=True)

    return {
        "version": version,
        "channel": "live",
        "region": "cn",
        "launcher_index": launcher_url,
        "resource_index": index_url,
        "base_url": base_url,
        "cdn_urls": cdn_urls,
        "index_file_md5": config.get("indexFileMd5", ""),
        "size": int(config.get("size") or sum(item["size"] for item in files)),
        "uncompressed_size": int(config.get("unCompressSize") or 0),
        "file_count": len(files),
        "files": files,
        "patches": patch_routes,
        "links": links,
    }


def summary_for(version_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": version_data["version"],
        "channel": version_data.get("channel", "live"),
        "region": version_data.get("region", "cn"),
        "file_count": int(version_data.get("file_count") or len(version_data.get("files") or [])),
        "cdn_count": len(version_data.get("cdn_urls") or []),
        "patch_routes": len(version_data.get("patches") or []),
        "size": int(version_data.get("size") or 0),
        "uncompressed_size": int(version_data.get("uncompressed_size") or 0),
        "index_file_md5": version_data.get("index_file_md5", ""),
        "resource_index": version_data.get("resource_index", ""),
        "base_url": version_data.get("base_url", ""),
        "links": version_data.get("links", {}),
        **({"source_note": version_data["source_note"]} if version_data.get("source_note") else {}),
        **({"release_stage": version_data["release_stage"]} if version_data.get("release_stage") else {}),
    }


def main() -> None:
    WUWA_DATA.mkdir(parents=True, exist_ok=True)
    LISTS_DIR.mkdir(parents=True, exist_ok=True)

    old_versions = load_versions_archive()

    print("Fetching WuWa CN launcher index...")
    raw = fetch_json(GAME_CLIENT_INDEX)
    default = raw.get("default", {})
    config = default.get("config", default)
    current_version = str(config.get("version") or default.get("version") or "unknown")
    cdn_urls = [normalize_cdn(item.get("url", "")) for item in default.get("cdnList", []) if item.get("url")]

    current = build_current_version(config, GAME_CLIENT_INDEX, cdn_urls)
    versions = dict(old_versions)
    versions[current_version] = current

    ordered_versions = dict(
        sorted(versions.items(), key=lambda pair: version_key(pair[0]), reverse=True)
    )
    generated_at = utc_now()
    summaries = [summary_for(item) for item in ordered_versions.values()]

    index_data = {
        "source": f"{SOURCE_DESC} + TomyJan WuWa CN archive",
        "archive_source": TOMYJAN_ARCHIVE_SOURCE,
        "selected_launcher_index": GAME_CLIENT_INDEX,
        "last_checked_at": generated_at,
        "generated_at": generated_at,
        "game": GAME_INFO,
        "current_version": current_version,
        "version_count": len(summaries),
        "first_version": summaries[-1]["version"] if summaries else None,
        "latest_version": summaries[0]["version"] if summaries else None,
        "total_file_bytes": sum(item["size"] for item in summaries),
        "total_patch_route_bytes": sum(route.get("size", 0) for route in current.get("patches", [])),
        "cdn_urls": cdn_urls,
        "versions": summaries,
    }

    versions_archive = write_versions_archive(ordered_versions, generated_at)
    write_json_if_changed(INDEX_PATH, index_data)

    print(f"Current: {current_version}")
    print(f"Files: {current['file_count']}")
    print(f"Patch routes: {len(current['patches'])}")
    print(f"Versions kept: {len(ordered_versions)}")
    print(f"Version shards: {versions_archive['shard_count']}")


if __name__ == "__main__":
    main()
