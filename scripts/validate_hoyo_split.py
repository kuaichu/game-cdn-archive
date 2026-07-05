#!/usr/bin/env python3
"""Validate split HoYo version metadata shards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HOYO_DIR = ROOT / "docs" / "data" / "hoyo"
GAMES_PATH = HOYO_DIR / "games.json"
VERSIONS_DIR = HOYO_DIR / "versions"
CHUNK_DIR = HOYO_DIR / "chunk"
GAME_IDS = ("hk4e", "hkrpg", "nap", "bh3")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> list[Any]:
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def item_count_and_bytes(item: Any) -> tuple[int, int]:
    if not item:
        return 0, 0
    if isinstance(item, list):
        return len(item), sum(int(entry.get("size") or 0) for entry in item if isinstance(entry, dict))
    if isinstance(item, dict):
        return 1, int(item.get("size") or 0)
    return 0, 0


def download_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    game = row.get("game") or {}
    for key in ("full", "segments"):
        items.extend(item for item in as_list(game.get(key)) if isinstance(item, dict))
    for voice in (row.get("voice") or {}).values():
        items.extend(item for item in as_list(voice) if isinstance(item, dict))
    for patch in (row.get("update") or {}).values():
        items.extend(item for item in as_list((patch or {}).get("game")) if isinstance(item, dict))
        for voice in ((patch or {}).get("voice") or {}).values():
            items.extend(item for item in as_list(voice) if isinstance(item, dict))
    return [item for item in items if item.get("url")]


def shard_stats(row: dict[str, Any]) -> dict[str, Any]:
    package_items = 0
    update_items = 0
    direct_bytes = 0

    game = row.get("game") or {}
    for key in ("full", "segments"):
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
        "unavailable_items": sum(1 for item in download_items(row) if int(item.get("size") or 0) <= 0),
    }


def validate() -> list[str]:
    errors: list[str] = []
    index = load_json(GAMES_PATH)
    games = {game.get("id"): game for game in index.get("games", []) if isinstance(game, dict)}

    for game_id in GAME_IDS:
        game = games.get(game_id)
        if not game:
            errors.append(f"{game_id}:missing_game_summary")
            continue

        aggregate_path = HOYO_DIR / f"{game_id}_versions.json"
        if aggregate_path.exists():
            errors.append(f"{game_id}:legacy_aggregate_still_exists:{aggregate_path.relative_to(ROOT).as_posix()}")

        shard_dir = VERSIONS_DIR / game_id
        if not shard_dir.is_dir():
            errors.append(f"{game_id}:missing_shard_dir")
            continue

        summaries = game.get("versions") or []
        summary_versions = [str(item.get("version") or "") for item in summaries]
        if len(summary_versions) != len(set(summary_versions)):
            errors.append(f"{game_id}:duplicate_summary_versions")

        shard_versions = sorted(path.stem for path in shard_dir.glob("*.json"))
        missing_shards = sorted(set(summary_versions) - set(shard_versions))
        extra_shards = sorted(set(shard_versions) - set(summary_versions))
        if missing_shards:
            errors.append(f"{game_id}:missing_shards:{','.join(missing_shards)}")
        if extra_shards:
            errors.append(f"{game_id}:extra_shards:{','.join(extra_shards)}")

        if int(game.get("version_count") or 0) != len(summary_versions):
            errors.append(f"{game_id}:version_count:{game.get('version_count')}!={len(summary_versions)}")

        for summary in summaries:
            version = str(summary.get("version") or "")
            shard_path = shard_dir / f"{version}.json"
            if not shard_path.exists():
                continue
            shard = load_json(shard_path)
            if shard.get("version") != version:
                errors.append(f"{game_id}:{version}:version_mismatch:{shard.get('version')}")
            stats = shard_stats(shard)
            for key, value in stats.items():
                if summary.get(key) != value:
                    errors.append(f"{game_id}:{version}:{key}:{summary.get(key)}!={value}")
            if shard.get("chunk") and not (CHUNK_DIR / f"{game_id}_{version}.json").exists():
                errors.append(f"{game_id}:{version}:missing_chunk_index")

    return errors


def main() -> None:
    errors = validate()
    print("HoYo split validation")
    print(f"root={HOYO_DIR}")
    for game_id in GAME_IDS:
        game_dir = VERSIONS_DIR / game_id
        count = len(list(game_dir.glob("*.json"))) if game_dir.exists() else 0
        print(f"{game_id}_shards={count}")
    if errors:
        print("result=FAIL")
        print("\n".join(errors))
        raise SystemExit(1)
    print("result=PASS")


if __name__ == "__main__":
    main()
