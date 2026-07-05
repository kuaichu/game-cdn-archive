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


def main() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    updated = replace_current_coverage(readme, generate_block())
    if updated != readme:
        README_PATH.write_text(updated, encoding="utf-8")
        print("README.md coverage summary updated")
    else:
        print("README.md coverage summary already up to date")


if __name__ == "__main__":
    main()
