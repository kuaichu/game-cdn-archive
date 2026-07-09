#!/usr/bin/env python3
"""Build Aether Gazer Android resource-list static data.

The game exposes plain JSON .bytes manifests. Each resource row is:

    logical/path.ys|md5|size

The downloadable object URL is content-addressed:

    https://download-eo.ys4fun.com/android/resources/{md5}.ys
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_DIR = ROOT / "outputs" / "aethergazer_client_capture" / "bytes_305_121"
DEFAULT_OUTPUT = ROOT / "docs" / "data" / "aethergazer" / "resources"
BASE_URL = "https://download-eo.ys4fun.com/android/resources"

MANIFESTS = {
    "asset": "assethash_305_121_fce1365bee362bc67f0b236ea9eae3c0.bytes",
    "voice_ja": "voice_hash_ja_30500121.bytes",
    "voice_zh": "voice_hash_zh_30500121.bytes",
    "voice_package": "voice_package_list_305_121.bytes",
}


def read_or_download(manifest_dir: Path, filename: str) -> bytes:
    path = manifest_dir / filename
    if path.exists():
        return path.read_bytes()
    manifest_dir.mkdir(parents=True, exist_ok=True)
    url = f"{BASE_URL}/{filename}"
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    path.write_bytes(data)
    return data


def load_manifest(manifest_dir: Path, filename: str) -> dict[str, Any]:
    return json.loads(read_or_download(manifest_dir, filename).decode("utf-8"))


def parse_asset_hash_list(kind: str, manifest_name: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for line in payload.get("assetHashList") or []:
        try:
            path, md5, size_text = str(line).split("|", 2)
        except ValueError as exc:
            raise ValueError(f"invalid resource row in {manifest_name}: {line!r}") from exc
        size = int(size_text)
        records.append({
            "kind": kind,
            "path": path,
            "name": path.rsplit("/", 1)[-1],
            "md5": md5,
            "size": size,
            "url": f"{BASE_URL}/{md5}.ys",
        })
    return records


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def aria2_item(record: dict[str, Any], root_dir: str) -> str:
    return "\n".join([
        record["url"],
        f"  dir={root_dir}",
        f"  out={record['path']}",
        f"  checksum=md5={record['md5']}",
        "",
    ])


def build(manifest_dir: Path, output: Path) -> None:
    asset_manifest = load_manifest(manifest_dir, MANIFESTS["asset"])
    voice_ja_manifest = load_manifest(manifest_dir, MANIFESTS["voice_ja"])
    voice_zh_manifest = load_manifest(manifest_dir, MANIFESTS["voice_zh"])
    voice_package = load_manifest(manifest_dir, MANIFESTS["voice_package"])

    version_name = str(asset_manifest.get("versionName") or "").removeprefix("v") or "unknown"
    app_version = int(asset_manifest.get("appVersion") or 0)
    build_code = int(asset_manifest.get("buildCode") or 0)
    version_key = f"{version_name}_{app_version}_{build_code}"
    root_dir = f"AetherGazer_{version_key}"

    manifest_payloads = [
        ("asset", MANIFESTS["asset"], asset_manifest),
        ("voice_ja", MANIFESTS["voice_ja"], voice_ja_manifest),
        ("voice_zh", MANIFESTS["voice_zh"], voice_zh_manifest),
    ]
    records: list[dict[str, Any]] = []
    manifest_summaries = []
    for kind, name, payload in manifest_payloads:
        parsed = parse_asset_hash_list(kind, name, payload)
        records.extend(parsed)
        manifest_summaries.append({
            "kind": kind,
            "name": name,
            "version": payload.get("version"),
            "version_name": payload.get("versionName"),
            "file_count": len(parsed),
            "size": sum(item["size"] for item in parsed),
            "url": f"{BASE_URL}/{name}",
        })

    records.sort(key=lambda item: (item["kind"], item["path"]))
    kind_counts = Counter(item["kind"] for item in records)
    kind_sizes = Counter()
    for item in records:
        kind_sizes[item["kind"]] += int(item["size"])

    version_path = output / "versions" / f"{version_key}.json"
    urls_path = output / "lists" / f"{version_key}.urls.txt"
    aria2_path = output / "lists" / f"{version_key}.aria2.txt"

    write_json(version_path, {
        "game_id": "aethergazer",
        "game_name": "深空之眼",
        "version": version_name,
        "version_key": version_key,
        "platform": "Android",
        "distribution": "ys4fun_hash_resources",
        "base_url": BASE_URL,
        "unity_version": "2022.3.62f3",
        "app_version": app_version,
        "build_code": build_code,
        "manifest": asset_manifest.get("versionName"),
        "voice_packages": voice_package.get("infos") or [],
        "manifests": manifest_summaries,
        "file_count": len(records),
        "size": sum(item["size"] for item in records),
        "kind_counts": dict(kind_counts),
        "kind_sizes": dict(kind_sizes),
        "records": records,
    })

    write_text(urls_path, "\n".join(item["url"] for item in records) + "\n")
    write_text(aria2_path, "\n".join(aria2_item(item, root_dir) for item in records))

    now = datetime.now(timezone.utc).isoformat()
    index = {
        "generated_at": now,
        "last_checked_at": now,
        "game": {
            "id": "aethergazer",
            "name": "深空之眼",
            "subName": "Aether Gazer",
            "shortName": "SK",
            "icon": "assets/icons/aethergazer.ico",
            "kind": "android",
        },
        "source": "captured Android resource manifests",
        "base_url": BASE_URL,
        "versions": [{
            "version": version_name,
            "version_key": version_key,
            "platform": "Android",
            "app_version": app_version,
            "build_code": build_code,
            "manifest": asset_manifest.get("versionName"),
            "file_count": len(records),
            "size": sum(item["size"] for item in records),
            "asset_count": kind_counts.get("asset", 0),
            "voice_ja_count": kind_counts.get("voice_ja", 0),
            "voice_zh_count": kind_counts.get("voice_zh", 0),
            "unity_version": "2022.3.62f3",
            "manifests": manifest_summaries,
            "links": {
                "json": f"data/aethergazer/resources/versions/{version_key}.json",
                "urls": f"data/aethergazer/resources/lists/{version_key}.urls.txt",
                "aria2": f"data/aethergazer/resources/lists/{version_key}.aria2.txt",
            },
        }],
    }
    write_json(output / "index.json", index)

    print(f"aethergazer_resources_version={version_key}")
    print(f"aethergazer_resources_files={len(records)}")
    print(f"aethergazer_resources_size={sum(item['size'] for item in records)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.manifest_dir, args.output)


if __name__ == "__main__":
    main()
