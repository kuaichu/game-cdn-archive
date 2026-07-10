#!/usr/bin/env python3
"""Build a detailed NTE-only update summary for Telegram notifications."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CATALOG_PATH = "docs/data/catalog.json"
ANDROID_PATH = "docs/data/android/index.json"
TELEGRAM_SOFT_LIMIT = 3000


@dataclass(frozen=True)
class FileDelta:
    filename: str
    old_size: int
    new_size: int
    old_md5: str
    new_md5: str

    @property
    def size_delta(self) -> int:
        return self.new_size - self.old_size


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
    return tuple((0, int(part)) if part.isdigit() else (1, part.lower()) for part in parts)


def byte_text(size: int | None) -> str:
    if size is None:
        return "未知"
    value = float(size)
    for unit in ["B", "K", "M", "G", "T"]:
        if abs(value) < 1024 or unit == "TiB":
            return f"{value:.2f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    return f"{size}B"


def delta_text(old_size: int | None, new_size: int | None) -> str:
    if old_size is None or new_size is None:
        return ""
    delta = new_size - old_size
    if delta > 0:
        return f" (UP:{byte_text(delta)})"
    if delta < 0:
        return f" (DOWN:{byte_text(abs(delta))})"
    return ""


def catalog_versions(catalog: Any) -> list[dict[str, Any]]:
    if not isinstance(catalog, dict):
        return []
    rows = [row for row in catalog.get("versions") or [] if isinstance(row, dict)]
    return sorted(rows, key=lambda row: version_key(str(row.get("version") or "")))


def available_versions(catalog: Any) -> list[dict[str, Any]]:
    return [
        row
        for row in catalog_versions(catalog)
        if row.get("status") == 200 and row.get("full") and row.get("patches")
    ]


def by_version(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("version")): row for row in rows if row.get("version")}


def latest_version(rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    return str(rows[-1].get("version"))


def latest_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return rows[-1]


def docs_link_to_repo_path(link: str | None) -> str | None:
    if not link:
        return None
    if link.startswith("data/"):
        return f"docs/{link}"
    if link.startswith("docs/"):
        return link
    return f"docs/{link.lstrip('/')}"


def load_linked_json(root: Path, row: dict[str, Any], section: str, ref: str | None = None) -> list[dict[str, Any]]:
    link = ((row.get(section) or {}).get("json") if isinstance(row.get(section), dict) else None)
    repo_path = docs_link_to_repo_path(link)
    if not repo_path:
        return []

    data = load_json_from_git(ref, repo_path) if ref else load_json(root / repo_path)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def entry_size(item: dict[str, Any]) -> int:
    for key in ("filesize", "size", "bytes"):
        value = item.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def entry_md5(item: dict[str, Any]) -> str:
    value = item.get("md5") or item.get("hash") or ""
    return str(value)


def full_key(item: dict[str, Any]) -> str:
    return str(item.get("filename") or item.get("path") or item.get("object") or item.get("url") or "")


def patch_key(item: dict[str, Any]) -> str:
    return str(item.get("patch") or item.get("url") or item.get("newfile") or item.get("oldfile") or "")


def top_items(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return sorted(items, key=entry_size, reverse=True)[:limit]


def compare_full(old_items: list[dict[str, Any]], new_items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[FileDelta], list[dict[str, Any]]]:
    old_by_key = {full_key(item): item for item in old_items if full_key(item)}
    new_by_key = {full_key(item): item for item in new_items if full_key(item)}

    added = [new_by_key[key] for key in sorted(set(new_by_key) - set(old_by_key))]
    removed = [old_by_key[key] for key in sorted(set(old_by_key) - set(new_by_key))]
    changed: list[FileDelta] = []
    for key in sorted(set(old_by_key) & set(new_by_key)):
        old = old_by_key[key]
        new = new_by_key[key]
        old_size = entry_size(old)
        new_size = entry_size(new)
        old_md5 = entry_md5(old)
        new_md5 = entry_md5(new)
        if old_size != new_size or old_md5 != new_md5:
            changed.append(FileDelta(key, old_size, new_size, old_md5, new_md5))

    changed.sort(key=lambda item: abs(item.size_delta), reverse=True)
    added.sort(key=entry_size, reverse=True)
    removed.sort(key=entry_size, reverse=True)
    return added, changed, removed


def availability_text(row: dict[str, Any], section: str) -> str:
    counts = ((row.get("availability_counts") or {}).get(section) or {})
    if not isinstance(counts, dict) or not counts:
        return "not baked"
    parts = [f"{key}={value}" for key, value in sorted(counts.items())]
    return ", ".join(parts)


def section_link(row: dict[str, Any], section: str, key: str) -> str:
    value = ((row.get(section) or {}).get(key) if isinstance(row.get(section), dict) else None)
    return str(value or "")


def summarize_version(root: Path, old_catalog: Any, current_catalog: Any, version: str, base_ref: str) -> list[str]:
    old_rows = available_versions(old_catalog)
    current_rows = available_versions(current_catalog)
    old_latest_row = latest_row(old_rows)
    old_latest = str(old_latest_row.get("version")) if old_latest_row else None
    current_by_version = by_version(current_rows)
    current_row = current_by_version[version]

    full = current_row.get("full") if isinstance(current_row.get("full"), dict) else {}
    patches = current_row.get("patches") if isinstance(current_row.get("patches"), dict) else {}
    old_full = old_latest_row.get("full") if old_latest_row and isinstance(old_latest_row.get("full"), dict) else {}
    old_patches = old_latest_row.get("patches") if old_latest_row and isinstance(old_latest_row.get("patches"), dict) else {}
    interp = ((current_row.get("availability") or {}).get("interpretation") or {})
    status_label = interp.get("display_label") or "未知"
    version_line = f"{old_latest or '首次收录'} => {version}" if old_latest != version else version
    old_full_items = old_full.get("items")
    old_patch_items = old_patches.get("items")
    old_full_bytes = old_full.get("bytes")
    old_patch_bytes = old_patches.get("bytes")
    full_items = full.get("items")
    patch_items = patches.get("items")
    full_bytes = full.get("bytes")
    patch_bytes = patches.get("bytes")

    lines = [
        "异环 Win PC 资源更新!",
        "",
        f"版本: {version_line}",
        f"状态: {status_label}",
        f"本体文件数: {old_full_items if old_full_items is not None else '未知'} => {full_items if full_items is not None else '未知'}",
        f"补丁数: {old_patch_items if old_patch_items is not None else '未知'} => {patch_items if patch_items is not None else '未知'}",
        f"本体大小: {byte_text(old_full_bytes)} => {byte_text(full_bytes)}{delta_text(old_full_bytes, full_bytes)}",
        f"补丁大小: {byte_text(old_patch_bytes)} => {byte_text(patch_bytes)}{delta_text(old_patch_bytes, patch_bytes)}",
        f"CDN时间: {current_row.get('last_modified') or '未知'}",
        "",
        "更新日志:",
        "暂无",
        "",
        "*文件数和大小仅计算官方 ResList 清单",
        "via @NevernessToEvernessVersion",
    ]
    return lines


def android_versions(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    game = (data.get("games") or {}).get("nte") if isinstance(data.get("games"), dict) else None
    if not isinstance(game, dict):
        return []
    rows = [row for row in game.get("versions") or [] if isinstance(row, dict) and row.get("version")]
    return sorted(rows, key=lambda row: version_key(str(row.get("version") or "")))


def available_android_versions(data: Any) -> list[dict[str, Any]]:
    rows = []
    for row in android_versions(data):
        availability = ((row.get("availability") or {}).get("interpretation") or {})
        state = availability.get("state")
        status = row.get("status")
        if state == "available" or status == 200:
            rows.append(row)
    return rows


def summarize_android_version(old_android: Any, current_android: Any, version: str) -> list[str]:
    old_rows = available_android_versions(old_android)
    current_rows = available_android_versions(current_android)
    old_latest_row = latest_row(old_rows)
    current_by_version = by_version(current_rows)
    current_row = current_by_version[version]
    old_version = str(old_latest_row.get("version")) if old_latest_row else None
    old_size = old_latest_row.get("size") if old_latest_row else None
    new_size = current_row.get("size")
    interp = ((current_row.get("availability") or {}).get("interpretation") or {})
    status_label = interp.get("display_label") or ("可用" if current_row.get("status") == 200 else "未知")
    version_line = f"{old_version or '首次收录'} => {version}" if old_version != version else version

    lines = [
        "异环 Android APK 更新!",
        "",
        f"版本: {version_line}",
        f"大小: {byte_text(old_size)} => {byte_text(new_size)}{delta_text(old_size, new_size)}",
        f"渠道: {current_row.get('channel') or 'official'}",
        f"状态: {status_label}",
        f"文件名: {current_row.get('filename') or '未知'}",
        f"CDN时间: {current_row.get('last_modified') or '未知'}",
        "",
        "更新日志:",
        "暂无",
        "",
        "*APK 信息来自官方 Android 下载入口和 CDN 响应",
        "via @NevernessToEvernessVersion",
    ]
    return lines


def trim_lines(lines: list[str], limit: int = TELEGRAM_SOFT_LIMIT) -> str:
    text = "\n".join(lines).strip()
    if len(text) <= limit:
        return text

    trimmed: list[str] = []
    for line in lines:
        candidate = "\n".join(trimmed + [line, "", "...消息过长，已截断。"]).strip()
        if len(candidate) > limit:
            break
        trimmed.append(line)
    trimmed.extend(["", "...消息过长，已截断；完整内容请查看生成的 JSON / URL / aria2 列表。"])
    return "\n".join(trimmed).strip()


def summarize(base_ref: str, root: Path) -> str:
    old_catalog = load_json_from_git(base_ref, CATALOG_PATH)
    current_catalog = load_json(root / CATALOG_PATH)
    old_android = load_json_from_git(base_ref, ANDROID_PATH)
    current_android = load_json(root / ANDROID_PATH)
    old_pc_versions = {str(row.get("version")) for row in available_versions(old_catalog)}
    current_pc_versions = [str(row.get("version")) for row in available_versions(current_catalog)]
    new_pc_versions = [version for version in current_pc_versions if version not in old_pc_versions]
    old_apk_versions = {str(row.get("version")) for row in available_android_versions(old_android)}
    current_apk_versions = [str(row.get("version")) for row in available_android_versions(current_android)]
    new_apk_versions = [version for version in current_apk_versions if version not in old_apk_versions]

    if not new_pc_versions and not new_apk_versions:
        return ""

    lines: list[str] = []
    for version in new_pc_versions:
        if lines:
            lines.extend(["", "----", ""])
        lines.extend(summarize_version(root, old_catalog, current_catalog, version, base_ref))
    for version in new_apk_versions:
        if lines:
            lines.extend(["", "----", ""])
        lines.extend(summarize_android_version(old_android, current_android, version))
    return trim_lines(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="HEAD", help="Git ref used as the previous data snapshot.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--output", help="Optional file to write the summary to.")
    args = parser.parse_args()

    text = summarize(args.base_ref, Path(args.root))
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
