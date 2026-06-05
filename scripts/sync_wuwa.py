#!/usr/bin/env python3
"""Build Wuthering Waves static indexes from launcher configuration."""

from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin


DISCOVERY_URL = (
    "https://gist.githubusercontent.com/yuhkix/"
    "b8796681ac2cd3bab11b7e8cdc022254/raw/"
    "4435fd290c07f7f766a6d2ab09ed3096d83b02e3/wuwa.json"
)
SOURCE_REPO = "https://github.com/yuhkix/wuwa-downloader"


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


def write_lists(output_dir: Path, version: str, items: list[dict]) -> dict[str, str]:
    lists_dir = output_dir / "lists"
    lists_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{version}-files"

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
        lines.append(f"  dir=WutheringWaves_{version}/{parent}" if parent != "." else f"  dir=WutheringWaves_{version}")
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


def build_channel(discovery: dict, channel: str, region: str, output_dir: Path):
    index_url = discovery[channel][region]
    launcher_index = fetch_json(index_url)
    default = launcher_index["default"]
    config = default["config"]
    cdn_urls = [cdn["url"].rstrip("/") for cdn in default.get("cdnList", []) if cdn.get("url")]
    if not cdn_urls:
        raise RuntimeError("No CDN urls found")

    index_file_url = join_url(cdn_urls[0], config["indexFile"])
    resource_index = fetch_json(index_file_url)
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
    return summary, version, index_url


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
    discovery = fetch_json(DISCOVERY_URL)
    summary, version, selected_index_url = build_channel(
        discovery, args.channel, args.region, args.output
    )

    index = {
        "source": SOURCE_REPO,
        "discovery_url": DISCOVERY_URL,
        "selected_launcher_index": selected_index_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "game": {
            "id": "wuwa",
            "name": "鸣潮",
            "subName": "Wuthering Waves",
            "shortName": "WW",
            "icon": "assets/icons/wuwa.png",
            "kind": "wuwa",
        },
        "versions": [summary],
    }
    versions = {version["version"]: version}

    (args.output / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "versions.json").write_text(
        json.dumps(versions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote Wuthering Waves {summary['region']} {summary['channel']} "
        f"{summary['version']} with {summary['file_count']} files"
    )


if __name__ == "__main__":
    main()
