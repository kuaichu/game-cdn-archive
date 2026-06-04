#!/usr/bin/env python3
"""Sync HoYo game metadata from the public HoyoFiles API."""

from __future__ import annotations

import json
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HOYO_DATA = ROOT / "docs" / "data" / "hoyo"
CHUNK_DATA = HOYO_DATA / "chunk"
GAMES_PATH = HOYO_DATA / "games.json"

API_BASE = "https://autopatch.amarea.cn/pkg_version"
SOURCE_URL = "https://hoyo-files.amarea.cn"

GAMES = [
    {
        "id": "hk4e",
        "name": "原神",
        "shortName": "YS",
        "domain": "autopatchcn.yuanshen.com",
    },
    {
        "id": "hkrpg",
        "name": "崩坏：星穹铁道",
        "shortName": "HSR",
        "domain": "autopatchcn.bhsr.com",
    },
    {
        "id": "nap",
        "name": "绝区零",
        "shortName": "ZZZ",
        "domain": "autopatchcn.juequling.com",
    },
    {
        "id": "bh3",
        "name": "崩坏3",
        "shortName": "BH3",
        "domain": "autopatchcn.bh3.com",
    },
]


def fetch_json(url: str, timeout: int = 45) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "game-cdn-archive/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


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


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def item_count_and_bytes(item: Any) -> tuple[int, int]:
    if not item:
        return 0, 0
    if isinstance(item, list):
        count = len(item)
        size = sum(int(entry.get("size") or 0) for entry in item if isinstance(entry, dict))
        return count, size
    if isinstance(item, dict):
        return 1, int(item.get("size") or 0)
    return 0, 0


def version_stats(row: dict[str, Any]) -> dict[str, int | bool]:
    package_items = 0
    update_items = 0
    direct_bytes = 0

    game = row.get("game") or {}
    for key in ["full", "segments"]:
        count, size = item_count_and_bytes(game.get(key))
        package_items += count
        direct_bytes += size

    for voice in (row.get("voice") or {}).values():
        count, size = item_count_and_bytes(voice)
        package_items += count
        direct_bytes += size

    for patch in (row.get("update") or {}).values():
        count, size = item_count_and_bytes((patch or {}).get("game"))
        update_items += count
        direct_bytes += size
        for voice in ((patch or {}).get("voice") or {}).values():
            count, size = item_count_and_bytes(voice)
            update_items += count
            direct_bytes += size

    return {
        "package_items": package_items,
        "update_items": update_items,
        "direct_bytes": direct_bytes,
        "has_chunk": bool(row.get("chunk")),
        "has_decompressed_path": bool(row.get("decompressed_path")),
    }


def stable_compare_games(index: dict[str, Any]) -> dict[str, Any]:
    stable = deepcopy(index)
    stable["generated_at"] = None
    return stable


def main() -> None:
    HOYO_DATA.mkdir(parents=True, exist_ok=True)
    CHUNK_DATA.mkdir(parents=True, exist_ok=True)

    previous = json.loads(GAMES_PATH.read_text(encoding="utf-8")) if GAMES_PATH.exists() else {}
    games_summary = []
    synced_chunks = 0

    for game in GAMES:
        game_id = game["id"]
        versions_url = f"{API_BASE}/{game_id}_versions.json"
        versions = fetch_json(versions_url)
        if not isinstance(versions, dict):
            raise RuntimeError(f"unexpected version payload for {game_id}")

        write_json_if_changed(HOYO_DATA / f"{game_id}_versions.json", versions, indent=4)

        version_rows = []
        direct_items = 0
        update_items = 0
        chunk_versions = 0
        direct_bytes = 0

        for version in sorted(versions, key=version_key):
            stats = version_stats(versions[version])
            version_rows.append({"version": version, **stats})
            direct_items += int(stats["package_items"])
            update_items += int(stats["update_items"])
            direct_bytes += int(stats["direct_bytes"])
            if stats["has_chunk"]:
                chunk_versions += 1
                chunk_url = f"{API_BASE}/chunk/{game_id}_{version}.json"
                chunk = fetch_json(chunk_url)
                if isinstance(chunk, dict) and chunk.get("retcode") == 0:
                    write_json_if_changed(CHUNK_DATA / f"{game_id}_{version}.json", chunk, indent=4)
                    synced_chunks += 1

        games_summary.append(
            {
                **game,
                "versions": version_rows,
                "version_count": len(version_rows),
                "first_version": version_rows[0]["version"] if version_rows else None,
                "latest_version": version_rows[-1]["version"] if version_rows else None,
                "direct_items": direct_items,
                "update_items": update_items,
                "chunk_versions": chunk_versions,
                "direct_bytes": direct_bytes,
                "versions_url": versions_url,
            }
        )

    new_index = {
        "source": SOURCE_URL,
        "api_base": API_BASE,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "games": games_summary,
    }
    if stable_compare_games(previous) == stable_compare_games(new_index):
        new_index["generated_at"] = previous.get("generated_at")

    write_json_if_changed(GAMES_PATH, new_index)
    print(f"synced {len(games_summary)} HoYo games, {synced_chunks} chunk indexes")


if __name__ == "__main__":
    main()
