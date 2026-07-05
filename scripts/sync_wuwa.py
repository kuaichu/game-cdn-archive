#!/usr/bin/env python3
"""Build Wuthering Waves static indexes from launcher configuration."""

from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.error
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit


DISCOVERY_URL = (
    "https://gist.githubusercontent.com/yuhkix/"
    "b8796681ac2cd3bab11b7e8cdc022254/raw/"
    "4435fd290c07f7f766a6d2ab09ed3096d83b02e3/wuwa.json"
)
SOURCE_REPO = "https://github.com/yuhkix/wuwa-downloader"
HEAD_TIMEOUT_SECONDS = 10
CN_LIVE_CDNS = [
    "https://pcdownload-aliyun.aki-game.com",
    "https://pcdownload-huoshan.aki-game.com",
    "https://pcdownload-qcloud.aki-game.com",
]
HISTORICAL_CN_LIVE_INDEXES = [
    {
        "version": "2.3.1",
        "resource_index": "https://pcdownload-huoshan.aki-game.com/launcher/game/G152/2.3.1/xAgwspCwdYJOMlAPyLUCRnoCkGlYgUkv/resource.json",
        "base_url": "launcher/game/G152/2.3.1/xAgwspCwdYJOMlAPyLUCRnoCkGlYgUkv/zip/",
        "source_note": "recorded by external manual-install archive",
    },
    {
        "version": "2.6.2",
        "resource_index": "https://pcdownload-aliyun.aki-game.com/launcher/game/G152/10003/2.6.2/DYINNoSACrMDUahXEhMxmWqVOHJjvFSH/resource/10003/2.6.2/indexFile.json",
        "base_url": "launcher/game/G152/10003/2.6.2/DYINNoSACrMDUahXEhMxmWqVOHJjvFSH/zip/",
        "source_note": "recovered from Wayback launcher index snapshot 20250922105631",
    },
    {
        "version": "2.8.0",
        "resource_index": "https://pcdownload-aliyun.aki-game.com/launcher/game/G152/10003/2.8.0/QqtoWZIMsZkiMQSwcmrYEFqYozeLagjd/resource/10003/2.8.0/indexFile.json",
        "base_url": "launcher/game/G152/10003/2.8.0/QqtoWZIMsZkiMQSwcmrYEFqYozeLagjd/zip/",
        "source_note": "recovered from Wayback launcher index snapshot 20251125142709",
    },
    {
        "version": "3.2.2",
        "resource_index": "https://pcdownload-aliyun.aki-game.com/launcher/game/G152/10003/3.2.2/sUfHBBTqFSGticVyXaeclYjVwoLQhMEE/resource/10003/3.2.2/indexFile.json",
        "base_url": "launcher/game/G152/10003/3.2.2/sUfHBBTqFSGticVyXaeclYjVwoLQhMEE/zip/",
        "source_note": "recovered from Wayback launcher index snapshot 20260418145837",
    },
]
MANUAL_CN_PRELOAD_INDEXES = [
    {
        "version": "3.4.0",
        "resource_index": "https://pcdownload-aliyun.aki-game.com/launcher/game/G152/10003/3.4.0/sMnbFpowGUKLSvELgHzeHWxQcGFgQFOJ/resource/10003/3.4.0/indexFile.json",
        "base_url": "launcher/game/G152/10003/3.4.0/sMnbFpowGUKLSvELgHzeHWxQcGFgQFOJ/zip/",
        "source_note": "captured from official predownload CDN directory",
        "release_stage": "preload",
        "patches": [
            {
                "from": "3.3.0",
                "index_url": "https://pcdownload-aliyun.aki-game.com/launcher/game/G152/10003/3.4.0/sMnbFpowGUKLSvELgHzeHWxQcGFgQFOJ/resource/10003/3.4.0/3.3.0/indexFile.json",
                "base_url": "launcher/game/G152/10003/3.4.0/sMnbFpowGUKLSvELgHzeHWxQcGFgQFOJ/resource/10003/3.4.0/3.3.0/resources/",
            }
        ],
    }
]
HISTORICAL_PCSTARTER_RESOURCES = [
    {
        "version": "1.0.0",
        "resource_index": "https://pcdownload-aliyun.aki-game.com/pcstarter/prod/game/G152/1.0.0/ODPITqJuybUecE9ERVZsY8uV7uMHGIUw/resource.json",
        "base_url": "pcstarter/prod/game/G152/1.0.0/ODPITqJuybUecE9ERVZsY8uV7uMHGIUw/zip/",
        "source_note": "recovered from pcstarter Wangsu mirror path",
    },
    {
        "version": "1.1.1",
        "resource_index": "https://pcdownload-aliyun.aki-game.com/pcstarter/prod/game/G152/1.1.1/a1vBvQhjfBJ6o7uxNFYORQUqH1xIb5pQ/resource.json",
        "base_url": "pcstarter/prod/game/G152/1.1.1/a1vBvQhjfBJ6o7uxNFYORQUqH1xIb5pQ/zip/",
        "source_note": "recovered from pcstarter game index snapshot 20240609102130",
    },
    {
        "version": "2.2.0",
        "resource_index": "https://pcdownload-aliyun.aki-game.com/pcstarter/prod/game/G152/2.2.0/4qOQXRgFtEbYo6glSpYrG6N5yMuscF97/resource.json",
        "base_url": "pcstarter/prod/game/G152/2.2.0/4qOQXRgFtEbYo6glSpYrG6N5yMuscF97/zip/",
        "source_note": "recovered from pcstarter game index referenced by launcher 2.0.0.0",
    },
    {
        "version": "2.2.1",
        "resource_index": "https://pcdownload-aliyun.aki-game.com/pcstarter/prod/game/G152/2.2.1/WpwvP26jdT38AzADIHmpNI95bpCszODv/resource.json",
        "base_url": "pcstarter/prod/game/G152/2.2.1/WpwvP26jdT38AzADIHmpNI95bpCszODv/zip/",
        "source_note": "recovered from pcstarter game index referenced by launcher 2.0.0.0",
    },
]


def fetch_json(url: str):
    last_error: Exception | None = None
    for attempt in range(4):
        request = urllib.request.Request(url, headers={"User-Agent": "game-cdn-archive/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                if body[:2] == b"\x1f\x8b":
                    body = gzip.decompress(body)
                return json.loads(body.decode("utf-8"))
        except Exception as error:
            last_error = error
            if attempt == 3:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Failed to fetch JSON from {url}") from last_error


def url_for_request(url: str) -> str:
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


def fetch_head_metadata(url: str, timeout: int = HEAD_TIMEOUT_SECONDS) -> dict:
    if not url:
        return {}
    request = urllib.request.Request(
        url_for_request(url),
        headers={"User-Agent": "game-cdn-archive/1.0"},
        method="HEAD",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "status": response.status,
                "last_modified": response.headers.get("Last-Modified") or "",
                "content_length": int(response.headers.get("Content-Length") or 0),
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "last_modified": exc.headers.get("Last-Modified") or "",
            "content_length": int(exc.headers.get("Content-Length") or 0),
        }
    except Exception as exc:
        return {"status": None, "last_modified": "", "content_length": 0, "error": str(exc)}


def apply_last_modified(version: dict, summary: dict) -> None:
    candidates = [
        (version.get("resource_index") or "", "resource_index"),
        (((version.get("files") or [{}])[0] or {}).get("url") or "", "pc_file"),
    ]
    for url, source in candidates:
        if not url:
            continue
        metadata = fetch_head_metadata(url)
        version["last_modified_url"] = url
        version["last_modified_source"] = source
        if metadata.get("status") is not None:
            version["last_modified_status"] = metadata["status"]
        if metadata.get("last_modified"):
            version["last_modified"] = metadata["last_modified"]
            summary["last_modified"] = metadata["last_modified"]
            summary["last_modified_source"] = source
            summary["last_modified_url"] = url
            summary["last_modified_status"] = metadata.get("status")
            return


def load_cached_versions(output_dir: Path) -> dict:
    versions_path = output_dir / "versions.json"
    try:
        return json.loads(versions_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def cached_link_exists(output_dir: Path, value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        if not value.startswith("data/wuwa/"):
            return True
        docs_dir = output_dir.parents[1]
        return (docs_dir / value).exists()
    if isinstance(value, dict):
        return all(cached_link_exists(output_dir, item) for item in value.values())
    if isinstance(value, list):
        return all(cached_link_exists(output_dir, item) for item in value)
    return True


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
    for key in ["source_note", "release_stage"]:
        if version.get(key):
            summary[key] = version[key]
    for key in ["last_modified", "last_modified_source", "last_modified_url", "last_modified_status"]:
        if version.get(key):
            summary[key] = version[key]
    return summary


def cached_version(
    cached_versions: dict,
    output_dir: Path,
    version: str,
    reason: Exception,
):
    cached = cached_versions.get(version)
    if not isinstance(cached, dict):
        return None
    if not cached_link_exists(output_dir, cached.get("links")):
        return None
    print(f"::warning::Reusing cached Wuthering Waves {version} data: {reason}")
    return summary_from_version(cached), deepcopy(cached)


def join_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def normalize_resource(item: dict, cdn_urls: list[str], base_url: str) -> dict:
    dest = item["dest"].replace("\\", "/").lstrip("/")
    urls = [join_url(join_url(cdn, base_url), dest) for cdn in cdn_urls]
    return {
        "dest": dest,
        "name": Path(dest).name,
        "md5": item.get("md5") or "",
        "size": int(item.get("size") or 0),
        "url": urls[0],
        "urls": urls,
    }


def normalize_pcstarter_resource(item: dict, cdn_urls: list[str], base_url: str) -> dict:
    dest = item["dest"].replace("\\", "/").lstrip("/")
    urls = [join_url(join_url(cdn, base_url), dest) for cdn in cdn_urls]
    return {
        "dest": dest,
        "name": Path(dest).name,
        "md5": item.get("md5") or "",
        "sample_hash": item.get("sampleHash") or "",
        "size": int(item.get("size") or 0),
        "url": urls[0],
        "urls": urls,
    }


def normalize_patch_resource(item: dict, cdn_urls: list[str], base_url: str) -> dict:
    dest = item["dest"].replace("\\", "/").lstrip("/")
    urls = [join_url(join_url(cdn, base_url), dest) for cdn in cdn_urls]
    return {
        "dest": dest,
        "name": Path(dest).name,
        "md5": item.get("md5") or "",
        "size": int(item.get("size") or 0),
        "url": urls[0],
        "urls": urls,
    }


def write_named_lists(output_dir: Path, stem: str, root_dir: str, items: list[dict]) -> dict[str, str]:
    lists_dir = output_dir / "lists"
    lists_dir.mkdir(parents=True, exist_ok=True)

    json_path = lists_dir / f"{stem}.json"
    urls_path = lists_dir / f"{stem}.urls.txt"
    aria2_path = lists_dir / f"{stem}.aria2.txt"

    json_path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    urls_path.write_text("\n".join(item["url"] for item in items) + "\n", encoding="utf-8")

    lines: list[str] = []
    for item in items:
        dest = item["dest"]
        parent = Path(dest).parent.as_posix()
        out = Path(dest).name
        for url in item["urls"]:
            lines.append(url)
        lines.append(f"  dir={root_dir}/{parent}" if parent != "." else f"  dir={root_dir}")
        lines.append(f"  out={out}")
        if item["md5"]:
            lines.append(f"  checksum=md5={item['md5']}")
        lines.append("")
    aria2_path.write_text("\n".join(lines), encoding="utf-8")

    prefix = "data/wuwa/lists"
    return {
        "json": f"{prefix}/{json_path.name}",
        "urls": f"{prefix}/{urls_path.name}",
        "aria2": f"{prefix}/{aria2_path.name}",
    }


def write_lists(output_dir: Path, version: str, items: list[dict]) -> dict[str, str]:
    return write_named_lists(output_dir, f"{version}-files", f"WutheringWaves_{version}", items)


def build_channel(
    discovery: dict,
    channel: str,
    region: str,
    output_dir: Path,
    cached_versions: dict,
):
    index_url = discovery[channel][region]
    launcher_index = fetch_json(index_url)
    default = launcher_index["default"]
    config = default["config"]
    cdn_urls = [cdn["url"].rstrip("/") for cdn in default.get("cdnList", []) if cdn.get("url")]
    if not cdn_urls:
        raise RuntimeError("No CDN urls found")

    index_file_url = join_url(cdn_urls[0], config["indexFile"])
    try:
        resource_index = fetch_json(index_file_url)
    except RuntimeError as exc:
        cached = cached_version(cached_versions, output_dir, config["version"], exc)
        if cached:
            summary, version = cached
            return summary, version, index_url
        raise
    raw_items = resource_index.get("resource") or []
    items = [normalize_resource(item, cdn_urls, config["baseUrl"]) for item in raw_items]
    links = write_lists(output_dir, config["version"], items)

    patches = []
    for patch in config.get("patchConfig", []):
        patches.append(
            {
                "from": patch.get("version") or "",
                "to": config["version"],
                "size": int(patch.get("size") or 0),
                "uncompressed_size": int(patch.get("unCompressSize") or 0),
                "index_file_md5": patch.get("indexFileMd5") or "",
                "index_file": patch.get("indexFile") or "",
                "index_url": join_url(cdn_urls[0], patch.get("indexFile") or ""),
                "base_url": patch.get("baseUrl") or "",
            }
        )
    patches.sort(key=lambda item: version_key(item["from"]), reverse=True)

    total_size = sum(item["size"] for item in items)
    version = {
        "version": config["version"],
        "channel": channel,
        "region": region,
        "launcher_index": index_url,
        "resource_index": index_file_url,
        "base_url": config["baseUrl"],
        "cdn_urls": cdn_urls,
        "index_file_md5": config.get("indexFileMd5") or "",
        "size": int(config.get("size") or total_size),
        "uncompressed_size": int(config.get("unCompressSize") or total_size),
        "file_count": len(items),
        "files": items,
        "patches": patches,
        "links": {"files": links},
    }
    summary = {
        "version": version["version"],
        "channel": channel,
        "region": region,
        "file_count": len(items),
        "cdn_count": len(cdn_urls),
        "patch_routes": len(patches),
        "size": version["size"],
        "uncompressed_size": version["uncompressed_size"],
    }
    apply_last_modified(version, summary)
    return summary, version, index_url


def build_historical_cn_live(spec: dict, output_dir: Path, cached_versions: dict):
    try:
        resource_index = fetch_json(spec["resource_index"])
    except RuntimeError as exc:
        cached = cached_version(cached_versions, output_dir, spec["version"], exc)
        if cached:
            return cached
        raise
    raw_items = resource_index.get("resource") or []
    items = [normalize_resource(item, CN_LIVE_CDNS, spec["base_url"]) for item in raw_items]
    links = write_lists(output_dir, spec["version"], items)
    total_size = sum(item["size"] for item in items)
    version = {
        "version": spec["version"],
        "channel": "live",
        "region": "cn",
        "resource_index": spec["resource_index"],
        "base_url": spec["base_url"],
        "cdn_urls": CN_LIVE_CDNS,
        "index_file_md5": "",
        "size": total_size,
        "uncompressed_size": total_size,
        "file_count": len(items),
        "files": items,
        "patches": [],
        "source_note": spec["source_note"],
        "links": {"files": links},
    }
    summary = {
        "version": version["version"],
        "channel": version["channel"],
        "region": version["region"],
        "file_count": len(items),
        "cdn_count": len(CN_LIVE_CDNS),
        "patch_routes": 0,
        "size": total_size,
        "uncompressed_size": total_size,
        "source_note": spec["source_note"],
    }
    apply_last_modified(version, summary)
    return summary, version


def build_pcstarter_resource(spec: dict, output_dir: Path, cached_versions: dict):
    try:
        resource_index = fetch_json(spec["resource_index"])
    except RuntimeError as exc:
        cached = cached_version(cached_versions, output_dir, spec["version"], exc)
        if cached:
            return cached
        raise
    raw_items = resource_index.get("resource") or []
    items = [normalize_pcstarter_resource(item, CN_LIVE_CDNS, spec["base_url"]) for item in raw_items]
    links = write_lists(output_dir, spec["version"], items)
    total_size = sum(item["size"] for item in items)
    version = {
        "version": spec["version"],
        "channel": "live",
        "region": "cn",
        "resource_index": spec["resource_index"],
        "base_url": spec["base_url"],
        "cdn_urls": CN_LIVE_CDNS,
        "index_file_md5": "",
        "size": total_size,
        "uncompressed_size": total_size,
        "file_count": len(items),
        "files": items,
        "patches": [],
        "source_note": spec["source_note"],
        "links": {"files": links},
    }
    summary = {
        "version": version["version"],
        "channel": version["channel"],
        "region": version["region"],
        "file_count": len(items),
        "cdn_count": len(CN_LIVE_CDNS),
        "patch_routes": 0,
        "size": total_size,
        "uncompressed_size": total_size,
        "source_note": spec["source_note"],
    }
    apply_last_modified(version, summary)
    return summary, version


def index_path_from_url(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def build_manual_cn_preload(spec: dict, output_dir: Path, cached_versions: dict):
    try:
        resource_index = fetch_json(spec["resource_index"])
    except RuntimeError as exc:
        cached = cached_version(cached_versions, output_dir, spec["version"], exc)
        if cached:
            return cached
        raise
    raw_items = resource_index.get("resource") or []
    items = [normalize_resource(item, CN_LIVE_CDNS, spec["base_url"]) for item in raw_items]
    total_size = sum(item["size"] for item in items)

    patch_routes = []
    patch_parts_all = []
    try:
        for patch in spec.get("patches", []):
            patch_index = fetch_json(patch["index_url"])
            patch_raw = patch_index.get("resource") or []
            parts = [
                normalize_patch_resource(item, CN_LIVE_CDNS, patch["base_url"])
                for item in patch_raw
                if str(item.get("dest") or "").endswith(".krpdiff")
            ]
            patch_parts_all.extend(parts)
            patch_routes.append(
                {
                    "from": patch["from"],
                    "to": spec["version"],
                    "size": sum(item["size"] for item in parts),
                    "uncompressed_size": 0,
                    "index_file_md5": "",
                    "index_file": index_path_from_url(patch["index_url"]),
                    "index_url": patch["index_url"],
                    "base_url": patch["base_url"],
                    "parts": parts,
                }
            )
    except RuntimeError as exc:
        cached = cached_version(cached_versions, output_dir, spec["version"], exc)
        if cached:
            return cached
        raise

    links = write_lists(output_dir, spec["version"], items)
    for route in patch_routes:
        parts = route["parts"]
        route["links"] = write_named_lists(
            output_dir,
            f"{spec['version']}_{route['from']}_patches",
            f"WutheringWaves_{spec['version']}_patches/{route['from']}_to_{spec['version']}",
            parts,
        ) if parts else None

    combined_patch_links = write_named_lists(
        output_dir,
        f"{spec['version']}-patches",
        f"WutheringWaves_{spec['version']}_patches",
        patch_parts_all,
    ) if patch_parts_all else None

    version = {
        "version": spec["version"],
        "channel": "live",
        "region": "cn",
        "resource_index": spec["resource_index"],
        "base_url": spec["base_url"],
        "cdn_urls": CN_LIVE_CDNS,
        "index_file_md5": "",
        "size": total_size,
        "uncompressed_size": total_size,
        "file_count": len(items),
        "files": items,
        "patches": patch_routes,
        "source_note": spec["source_note"],
        "release_stage": spec.get("release_stage") or "",
        "links": {"files": links, "patches": combined_patch_links},
    }
    summary = {
        "version": version["version"],
        "channel": version["channel"],
        "region": version["region"],
        "file_count": len(items),
        "cdn_count": len(CN_LIVE_CDNS),
        "patch_routes": len(patch_routes),
        "size": total_size,
        "uncompressed_size": total_size,
        "source_note": spec["source_note"],
        "release_stage": spec.get("release_stage") or "",
    }
    apply_last_modified(version, summary)
    return summary, version


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default="live", choices=["live", "beta"])
    parser.add_argument("--region", default="cn", choices=["cn", "os"])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "data" / "wuwa",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    cached_versions = load_cached_versions(args.output)
    discovery = fetch_json(DISCOVERY_URL)
    summary, version, selected_index_url = build_channel(
        discovery, args.channel, args.region, args.output, cached_versions
    )
    summaries = [summary]
    versions = {version["version"]: version}

    if args.channel == "live" and args.region == "cn":
        for spec in HISTORICAL_CN_LIVE_INDEXES:
            if spec["version"] in versions:
                continue
            historical_summary, historical_version = build_historical_cn_live(
                spec, args.output, cached_versions
            )
            summaries.append(historical_summary)
            versions[historical_version["version"]] = historical_version
        for spec in HISTORICAL_PCSTARTER_RESOURCES:
            if spec["version"] in versions:
                continue
            pcstarter_summary, pcstarter_version = build_pcstarter_resource(
                spec, args.output, cached_versions
            )
            summaries.append(pcstarter_summary)
            versions[pcstarter_version["version"]] = pcstarter_version
        for spec in MANUAL_CN_PRELOAD_INDEXES:
            if spec["version"] in versions:
                continue
            preload_summary, preload_version = build_manual_cn_preload(
                spec, args.output, cached_versions
            )
            summaries.append(preload_summary)
            versions[preload_version["version"]] = preload_version

    summaries.sort(key=lambda item: version_key(item["version"]), reverse=True)

    index = {
        "source": SOURCE_REPO,
        "discovery_url": DISCOVERY_URL,
        "selected_launcher_index": selected_index_url,
        "last_checked_at": datetime.now(timezone.utc).isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "game": {
            "id": "wuwa",
            "name": "鸣潮",
            "subName": "Wuthering Waves",
            "shortName": "WW",
            "icon": "assets/icons/wuwa.png",
            "kind": "wuwa",
        },
        "versions": summaries,
    }

    (args.output / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "versions.json").write_text(
        json.dumps(versions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote Wuthering Waves {args.region} {args.channel} "
        f"{len(summaries)} versions"
    )


if __name__ == "__main__":
    main()
