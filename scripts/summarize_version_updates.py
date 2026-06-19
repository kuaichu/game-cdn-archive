#!/usr/bin/env python3
"""Summarize newly archived game versions for GitHub Actions notifications."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_LINES = 12


@dataclass(frozen=True)
class Source:
    path: str
    platform: str
    kind: str


SOURCES = [
    Source("docs/data/catalog.json", "PC", "single"),
    Source("docs/data/hoyo/games.json", "PC", "hoyo"),
    Source("docs/data/endfield/index.json", "PC", "single"),
    Source("docs/data/wuwa/index.json", "PC", "single"),
    Source("docs/data/arknights/index.json", "PC", "single"),
    Source("docs/data/android/index.json", "Android", "android"),
]


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_json_from_git(ref: str, path: str) -> Any | None:
    if not ref:
        return None

    try:
        data = subprocess.check_output(
            ["git", "show", f"{ref}:{path}"],
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def version_key(version: str) -> tuple:
    parts = re.findall(r"\d+|[A-Za-z]+", version)
    key = []
    for part in parts:
        key.append((0, int(part)) if part.isdigit() else (1, part.lower()))
    return tuple(key)


def usable_version(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return None

    version = item.get("version") or item.get("client_version") or item.get("versionName")
    if not version:
        return None

    status = item.get("status")
    if isinstance(status, int) and status >= 400:
        return None

    return str(version)


def sorted_versions(items: list[Any]) -> list[str]:
    versions = {version for item in items if (version := usable_version(item))}
    return sorted(versions, key=version_key)


def display_name(game: dict[str, Any], fallback: str) -> str:
    zh_name = game.get("zh_name")
    name = game.get("name") or fallback
    if zh_name and zh_name != name:
        return f"{zh_name} / {name}"

    sub_name = game.get("subName") or game.get("sub_name") or game.get("shortName")
    if sub_name and sub_name != name:
        return f"{name} / {sub_name}"
    return str(name)


def single_records(data: Any, source: Source, fallback: str) -> dict[str, tuple[str, list[str]]]:
    if not isinstance(data, dict):
        return {}

    game = data.get("game") if isinstance(data.get("game"), dict) else {}
    game_id = str(game.get("id") or fallback)
    name = display_name(game or data, game_id)
    versions = sorted_versions(data.get("versions") or [])
    if not versions:
        return {}
    return {f"{game_id}:{source.platform}": (f"{name} {source.platform}", versions)}


def hoyo_records(data: Any, source: Source) -> dict[str, tuple[str, list[str]]]:
    if not isinstance(data, dict) or not isinstance(data.get("games"), list):
        return {}

    records = {}
    for game in data["games"]:
        if not isinstance(game, dict):
            continue
        versions = sorted_versions(game.get("versions") or [])
        if not versions:
            continue
        game_id = str(game.get("id") or game.get("name") or "hoyo")
        name = display_name(game, game_id)
        records[f"hoyo:{game_id}:{source.platform}"] = (f"{name} {source.platform}", versions)
    return records


def android_records(data: Any, source: Source) -> dict[str, tuple[str, list[str]]]:
    if not isinstance(data, dict) or not isinstance(data.get("games"), dict):
        return {}

    records = {}
    for game_id, game in data["games"].items():
        if not isinstance(game, dict):
            continue
        versions = sorted_versions(game.get("versions") or [])
        if not versions:
            continue
        name = display_name(game, str(game_id))
        records[f"android:{game_id}:{source.platform}"] = (f"{name} {source.platform}", versions)
    return records


def records_for(data: Any, source: Source) -> dict[str, tuple[str, list[str]]]:
    if source.kind == "hoyo":
        return hoyo_records(data, source)
    if source.kind == "android":
        return android_records(data, source)
    fallback = Path(source.path).parent.name or Path(source.path).stem
    return single_records(data, source, fallback)


def summarize(base_ref: str, root: Path, max_lines: int = MAX_LINES) -> list[str]:
    lines: list[str] = []

    for source in SOURCES:
        old = records_for(load_json_from_git(base_ref, source.path), source)
        current = records_for(load_json(root / source.path), source)

        for key in sorted(current):
            label, current_versions = current[key]
            _, old_versions = old.get(key, (label, []))
            new_versions = sorted(set(current_versions) - set(old_versions), key=version_key)
            if not new_versions:
                continue

            old_latest = old_versions[-1] if old_versions else None
            current_latest = current_versions[-1]
            latest_changed = old_latest != current_latest and current_latest in new_versions
            archived_versions = [version for version in new_versions if version != current_latest]
            archived_note = f"（另新增归档: {', '.join(archived_versions)}）" if archived_versions else ""

            if latest_changed and old_latest:
                lines.append(f"{label} 更新: {old_latest} -> {current_latest}{archived_note}")
            elif latest_changed:
                lines.append(f"{label} 新增最新版本: {current_latest}{archived_note}")
            else:
                lines.append(f"{label} 新增归档版本: {', '.join(new_versions)}")

    if max_lines > 0 and len(lines) > max_lines:
        hidden = len(lines) - max_lines
        lines = lines[:max_lines] + [f"...另有 {hidden} 条版本更新"]

    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="HEAD", help="Git ref used as the previous data snapshot.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--max-lines", type=int, default=MAX_LINES, help="Maximum update lines to include; use 0 for no limit.")
    parser.add_argument("--output", help="Optional file to write the summary to.")
    args = parser.parse_args()

    lines = summarize(args.base_ref, Path(args.root), max_lines=args.max_lines)
    text = "\n".join(lines)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
