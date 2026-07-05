#!/usr/bin/env python3
"""Refresh README coverage versions from generated archive data."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
DOCS_DATA = ROOT / "docs" / "data"

START = "<!-- README_VERSION_SUMMARY_START -->"
END = "<!-- README_VERSION_SUMMARY_END -->"
PROGRESS_START = "<!-- README_PROGRESS_SNAPSHOT_START -->"
PROGRESS_END = "<!-- README_PROGRESS_SNAPSHOT_END -->"
ANDROID_START = "<!-- README_ANDROID_PROGRESS_START -->"
ANDROID_END = "<!-- README_ANDROID_PROGRESS_END -->"

HOYO_ENGLISH_NAMES = {
    "hk4e": "Genshin Impact",
    "hkrpg": "Honkai: Star Rail",
    "nap": "Zenless Zone Zero",
    "bh3": "Honkai Impact 3",
}


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def version_key(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    return tuple(int(part) for part in re.findall(r"\d+", value))


def latest_version(rows: list[dict[str, Any]], field: str = "version") -> str | None:
    versions = [str(row[field]) for row in rows if row.get(field)]
    if not versions:
        return None
    return max(versions, key=version_key)


def markdown_time(*values: Any) -> str:
    for value in values:
        if value:
            return f"`{value}`"
    return "`unknown`"


def version_range_text(rows: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    versions = [str(row["version"]) for row in rows if row.get("version")]
    if not versions:
        return None, None
    return min(versions, key=version_key), max(versions, key=version_key)


def nte_row() -> tuple[str, str, str] | None:
    catalog = load_json(DOCS_DATA / "catalog.json")
    if not catalog:
        return None
    versions = catalog.get("versions") or []
    ok_versions = [row for row in versions if row.get("status") == 200]
    latest = latest_version(ok_versions)
    if not latest:
        return None
    status = (
        f"Version manifests decoded and indexed through `{latest}` "
        f"({len(ok_versions)} available / {len(versions)} probed)"
    )
    return ("Neverness to Everness / 异环", "Windows PC", status)


def endfield_row() -> tuple[str, str, str] | None:
    index = load_json(DOCS_DATA / "endfield" / "index.json")
    if not index:
        return None
    versions = index.get("versions") or []
    latest = latest_version(versions)
    if not latest:
        return None
    status = (
        f"Official launcher API history and archive mirrors indexed through "
        f"`{latest}` ({len(versions)} versions)"
    )
    return ("Arknights: Endfield / 明日方舟：终末地", "Windows PC", status)


def arknights_row() -> tuple[str, str, str] | None:
    index = load_json(DOCS_DATA / "arknights" / "index.json")
    if not index:
        return None
    versions = index.get("versions") or []
    latest = latest_version(versions)
    if not latest:
        return None
    count = index.get("version_count") or len(versions)
    status = f"Official launcher package metadata indexed through `{latest}` ({count} versions)"
    return ("Arknights / 明日方舟", "Windows PC", status)


def wuwa_row() -> tuple[str, str, str] | None:
    index = load_json(DOCS_DATA / "wuwa" / "index.json")
    if not index:
        return None
    versions = index.get("versions") or []
    latest = latest_version(versions) or index.get("latest_version") or index.get("current_version")
    if not latest:
        return None
    count = index.get("version_count") or len(versions)
    status = f"Official launcher resource indexes and CDN mirrors indexed through `{latest}` ({count} versions)"
    return ("Wuthering Waves / 鸣潮", "Windows PC", status)


def hoyo_rows() -> list[tuple[str, str, str]]:
    index = load_json(DOCS_DATA / "hoyo" / "games.json")
    if not index:
        return []
    rows = []
    for game in index.get("games") or []:
        game_id = game.get("id")
        latest = game.get("latest_version") or latest_version(game.get("versions") or [])
        if not latest:
            continue
        english = HOYO_ENGLISH_NAMES.get(game_id, str(game.get("name") or game_id))
        name = f"{english} / {game.get('name')}"
        count = game.get("version_count") or len(game.get("versions") or [])
        status = f"HoyoFiles version metadata migrated through `{latest}` ({count} versions)"
        rows.append((name, "Windows PC", status))
    return rows


def progress_block() -> str:
    catalog = load_json(DOCS_DATA / "catalog.json") or {}
    hoyo = load_json(DOCS_DATA / "hoyo" / "games.json") or {}
    endfield = load_json(DOCS_DATA / "endfield" / "index.json") or {}
    arknights = load_json(DOCS_DATA / "arknights" / "index.json") or {}
    wuwa = load_json(DOCS_DATA / "wuwa" / "index.json") or {}
    android = load_json(DOCS_DATA / "android" / "index.json") or {}

    rows: list[tuple[str, str]] = []

    nte_versions = catalog.get("versions") or []
    nte_ok = [row for row in nte_versions if row.get("status") == 200]
    nte_first, nte_latest = version_range_text(nte_ok)
    if nte_first and nte_latest:
        rows.append((
            "NTE / 异环 PC",
            f"Indexed official Windows manifests from `{nte_first}` through `{nte_latest}`; "
            f"{len(nte_ok)} available versions out of {len(nte_versions)} probed entries",
        ))

    end_versions = endfield.get("versions") or []
    end_latest = latest_version(end_versions)
    if end_latest:
        rows.append((
            "Endfield / 终末地 PC",
            f"Imported `{len(end_versions)}` CN launcher-history snapshots through `{end_latest}`; "
            "official signed package URLs and archive mirrors are both preserved",
        ))

    ak_versions = arknights.get("versions") or []
    ak_latest = latest_version(ak_versions)
    if ak_latest:
        latest_row = next((row for row in ak_versions if str(row.get("version")) == ak_latest), {})
        rows.append((
            "Arknights / 明日方舟 PC",
            f"Indexed official launcher package metadata through `{ak_latest}`; "
            f"{latest_row.get('package_items') or 0} package items in the latest snapshot",
        ))

    wuwa_versions = wuwa.get("versions") or []
    wuwa_latest = latest_version(wuwa_versions)
    if wuwa_latest:
        rows.append((
            "Wuthering Waves / 鸣潮 PC",
            f"Indexed `{len(wuwa_versions)}` CN launcher/resource-index snapshots through `{wuwa_latest}`; "
            "file URLs, CDN mirrors, and patch routes are preserved when official indexes expose them",
        ))

    hoyo_parts = []
    for game in hoyo.get("games") or []:
        versions = game.get("versions") or []
        first, latest = version_range_text(versions)
        if first and latest:
            hoyo_parts.append(f"{game.get('name')} `{first}-{latest}` (`{len(versions)}` versions)")
    if hoyo_parts:
        rows.append(("HoYo CN PC catalog", "Migrated public HoyoFiles metadata for " + ", ".join(hoyo_parts)))

    android_games = android.get("games") or {}
    android_records = sum(len((game or {}).get("versions") or []) for game in android_games.values())
    if android_games:
        rows.append((
            "Android APK archive",
            f"Preserves `{android_records}` confirmed or historically verified official APK CDN records "
            f"across `{len(android_games)}` games",
        ))

    lines = [
        PROGRESS_START,
        "<!-- This block is generated by scripts/update_readme_summary.py. Do not edit by hand. -->",
        "",
        f"Current repository snapshot from generated data checked on {markdown_time(catalog.get('last_checked_at'), catalog.get('generated_at'))}:",
        "",
        "| Area | Current progress |",
        "| --- | --- |",
    ]
    lines.extend(f"| {area} | {status} |" for area, status in rows)
    lines.append(PROGRESS_END)
    return "\n".join(lines)


def android_progress_block() -> str:
    android = load_json(DOCS_DATA / "android" / "index.json") or {}
    games = android.get("games") or {}
    rows: list[tuple[str, str, str, str]] = []

    for game_id, game in sorted(games.items()):
        entries = game.get("versions") or []
        if not entries:
            continue
        unique_versions = [{"version": version} for version in sorted({str(entry.get("version")) for entry in entries if entry.get("version")}, key=version_key)]
        first, latest = version_range_text(unique_versions)
        available = sum(1 for entry in entries if int(entry.get("status") or 0) == 200)
        unavailable = len(entries) - available
        name = game.get("name") or game_id
        sub_name = game.get("subName")
        display_name = f"{name} / {sub_name}" if sub_name and sub_name != name else str(name)
        range_text = f"`{first}` -> `{latest}`" if first and latest and first != latest else f"`{latest or first}`"
        rows.append((
            display_name,
            range_text,
            f"`{len(unique_versions)}` version buckets / `{len(entries)}` records",
            f"`{available}` available; `{unavailable}` unavailable or historical dead-link records",
        ))

    lines = [
        ANDROID_START,
        "<!-- This block is generated by scripts/update_readme_summary.py. Do not edit by hand. -->",
        "",
        "| Game | Indexed versions | Records | Notes |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(f"| {game} | {versions} | {records} | {notes} |" for game, versions, records, notes in rows)
    lines.append(ANDROID_END)
    return "\n".join(lines)


def generated_at_line() -> str:
    catalog = load_json(DOCS_DATA / "catalog.json") or {}
    hoyo = load_json(DOCS_DATA / "hoyo" / "games.json") or {}
    endfield = load_json(DOCS_DATA / "endfield" / "index.json") or {}
    arknights = load_json(DOCS_DATA / "arknights" / "index.json") or {}
    wuwa = load_json(DOCS_DATA / "wuwa" / "index.json") or {}
    return (
        "_Last refreshed from generated archive data: "
        f"NTE {markdown_time(catalog.get('last_checked_at'), catalog.get('generated_at'))}; "
        f"HoYo {markdown_time(hoyo.get('last_checked_at'), hoyo.get('generated_at'))}; "
        f"Endfield {markdown_time(endfield.get('last_checked_at'), endfield.get('generated_at'))}; "
        f"Arknights {markdown_time(arknights.get('last_checked_at'), arknights.get('generated_at'))}; "
        f"WuWa {markdown_time(wuwa.get('last_checked_at'), wuwa.get('generated_at'))}._"
    )


def generate_block() -> str:
    rows = [
        row
        for row in [
            nte_row(),
            endfield_row(),
            arknights_row(),
            wuwa_row(),
        ]
        if row
    ]
    rows.extend(hoyo_rows())

    lines = [
        START,
        "<!-- This block is generated by scripts/update_readme_summary.py. Do not edit by hand. -->",
        "",
        "| Game | Platform | Status |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {game} | {platform} | {status} |" for game, platform, status in rows)
    lines.extend(["", generated_at_line(), END])
    return "\n".join(lines)


def replace_current_coverage(readme: str, block: str) -> str:
    if START in readme and END in readme:
        return re.sub(
            rf"{re.escape(START)}.*?{re.escape(END)}",
            block,
            readme,
            count=1,
            flags=re.DOTALL,
        )

    heading = re.search(r"(## Current Coverage\s*\n+)", readme)
    if not heading:
        raise RuntimeError("README.md does not contain a '## Current Coverage' section")

    after_heading = heading.end()
    table = re.match(r"(?:\|[^\n]*\|\n)+", readme[after_heading:])
    if table:
        start = after_heading
        end = after_heading + table.end()
        return readme[:start] + block + "\n" + readme[end:]

    return readme[:after_heading] + block + "\n\n" + readme[after_heading:]


def replace_progress_snapshot(readme: str, block: str) -> str:
    if PROGRESS_START in readme and PROGRESS_END in readme:
        return re.sub(
            rf"{re.escape(PROGRESS_START)}.*?{re.escape(PROGRESS_END)}",
            block,
            readme,
            count=1,
            flags=re.DOTALL,
        )

    match = re.search(r"(## Progress Snapshot\s*\n+).*?(?=\n## Android APK Progress)", readme, flags=re.DOTALL)
    if not match:
        return readme
    return readme[: match.start(1)] + match.group(1) + block + "\n" + readme[match.end() :]


def replace_android_progress(readme: str, block: str) -> str:
    if ANDROID_START in readme and ANDROID_END in readme:
        return re.sub(
            rf"{re.escape(ANDROID_START)}.*?{re.escape(ANDROID_END)}",
            block,
            readme,
            count=1,
            flags=re.DOTALL,
        )

    match = re.search(
        r"(\nThe Android side is now beyond \"latest link only\".*?ranges are:\s*\n+)(?:\|[^\n]*\|\n)+",
        readme,
        flags=re.DOTALL,
    )
    if not match:
        return readme
    return readme[: match.end(1)] + block + "\n" + readme[match.end() :]


def main() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    updated = replace_current_coverage(readme, generate_block())
    updated = replace_progress_snapshot(updated, progress_block())
    updated = replace_android_progress(updated, android_progress_block())
    if updated != readme:
        README_PATH.write_text(updated, encoding="utf-8")
        print("README.md coverage summary updated")
    else:
        print("README.md coverage summary already up to date")


if __name__ == "__main__":
    main()
