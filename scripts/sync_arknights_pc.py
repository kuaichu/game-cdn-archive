#!/usr/bin/env python3
"""Build static Arknights PC package indexes from Hypergryph launcher API."""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


GAME_ID = "arknights"
APP_CODE = "GzD1CpaWgmSq1wew"
LAUNCHER_APP_CODE = "abYeZZ16BPluCFyT"
OFFICIAL_API = (
    "https://launcher.hypergryph.com/api/game/get_latest"
    f"?appcode={APP_CODE}&launcher_appcode={LAUNCHER_APP_CODE}"
    "&channel=1&sub_channel=1&launcher_sub_channel=1"
)
SOURCE_SITE = "https://ak.hypergryph.com/pcs"


def fetch_json(url: str) -> dict:
    last_error: Exception | None = None
    for attempt in range(4):
        request = urllib.request.Request(url, headers={"User-Agent": "game-cdn-archive/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            last_error = error
            if attempt == 3:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Failed to fetch JSON from {url}") from last_error


def rel(path: Path) -> str:
    return path.as_posix().removeprefix("docs/")


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def write_lists(output_dir: Path, version: str, packages: list[dict]) -> dict[str, str]:
    lists_dir = output_dir / "lists"
    lists_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{version}_packages"

    json_path = lists_dir / f"{stem}.json"
    urls_path = lists_dir / f"{stem}.urls.txt"
    aria2_path = lists_dir / f"{stem}.aria2.txt"

    json_path.write_text(json.dumps(packages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    urls_path.write_text("\n".join(item["url"] for item in packages) + "\n", encoding="utf-8")

    lines: list[str] = []
    for item in packages:
        lines.append(item["url"])
        lines.append(f"  dir=Arknights_{version}")
        lines.append(f"  out={item['name']}")
        if item.get("md5"):
            lines.append(f"  checksum=md5={item['md5']}")
        lines.append("")
    aria2_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "json": rel(json_path),
        "urls": rel(urls_path),
        "aria2": rel(aria2_path),
    }


def build(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    observed_at = datetime.now(timezone.utc).isoformat()
    payload = fetch_json(OFFICIAL_API)
    version = payload["version"]
    pkg = payload.get("pkg") or {}
    raw_packs = pkg.get("packs") or []
    packages = []
    for index, item in enumerate(raw_packs, start=1):
        url = item["url"]
        size = int(item.get("package_size") or 0)
        name = Path(urlparse(url).path).name
        packages.append(
            {
                "name": name,
                "part": index,
                "size": size,
                "md5": item.get("md5") or "",
                "url": url,
            }
        )

    links = write_lists(output_dir, version, packages)
    packed_size = sum(item["size"] for item in packages)
    unpacked_size = int(pkg.get("total_size") or packed_size)
    major_minor = ".".join(version.split(".")[:2])

    versions = {
        version: {
            "version": version,
            "observed_at": observed_at,
            "client_version": payload.get("client_version") or version,
            "file_path": pkg.get("file_path") or "",
            "package_items": len(packages),
            "packed_size": packed_size,
            "unpacked_size": unpacked_size,
            "game_files_md5": pkg.get("game_files_md5") or "",
            "packages": packages,
            "links": {"packages": links},
        }
    }
    summaries = [
        {
            "version": version,
            "observed_at": observed_at,
            "version_family": major_minor,
            "package_items": len(packages),
            "packed_size": packed_size,
            "unpacked_size": unpacked_size,
            "game_files_md5": pkg.get("game_files_md5") or "",
        }
    ]

    index = {
        "source": "Hypergryph launcher API",
        "source_site": SOURCE_SITE,
        "official_api": OFFICIAL_API,
        "last_checked_at": observed_at,
        "generated_at": observed_at,
        "game": {
            "id": GAME_ID,
            "name": "明日方舟",
            "subName": "Arknights",
            "shortName": "AK",
            "icon": "assets/icons/arknights.ico",
            "kind": "arknights",
        },
        "versions": sorted(summaries, key=lambda item: version_key(item["version"]), reverse=True),
    }

    (output_dir / "versions.json").write_text(
        json.dumps(versions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote Arknights PC index for {version}: {len(packages)} packages")


def main() -> None:
    build(Path("docs/data/arknights"))


if __name__ == "__main__":
    main()
