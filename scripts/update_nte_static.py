#!/usr/bin/env python3
"""Refresh NTE static ResList indexes for the current official version range."""

from __future__ import annotations

import json
import shutil
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from archive_reslist_versions import process_version
from nte_downloader import current_version_from_config, fetch_config, version_range, version_sort_key
from nte_versioning import annotate_release_types


ROOT = Path(__file__).resolve().parents[1]
DOCS_DATA = ROOT / "docs" / "data"
CATALOG_PATH = DOCS_DATA / "catalog.json"
URL_LISTS = DOCS_DATA / "url_lists"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_paths(row: dict) -> dict:
    for section in ["full", "patches"]:
        files = row.get(section)
        if not files:
            continue
        for key in ["json", "urls", "aria2"]:
            if files.get(key):
                files[key] = f"data/url_lists/{Path(files[key]).name}"
    if row.get("url"):
        row["reslist_url"] = row.pop("url")
    if row.get("archive_bytes") is not None:
        row["reslist_bytes"] = row.pop("archive_bytes")
    row.pop("archive", None)
    return row


def copy_url_lists(temp_root: Path) -> None:
    URL_LISTS.mkdir(parents=True, exist_ok=True)
    for path in (temp_root / "url_lists").glob("*"):
        if path.is_file():
            shutil.copy2(path, URL_LISTS / path.name)


def stable_compare_catalog(catalog: dict) -> dict:
    stable = deepcopy(catalog)
    stable["generated_at"] = None
    stable["last_checked_at"] = None
    for row in stable.get("versions", []):
        if row.get("status") != 200:
            row.pop("content_length", None)
    return stable


def main() -> None:
    catalog = read_json(CATALOG_PATH)
    checked_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    _, config = fetch_config(timeout=30)
    current = current_version_from_config(config)
    if not current:
        raise RuntimeError("could not read current NTE version from config.xml")

    candidates = version_range("1.0.0", current)
    existing = {row["version"]: row for row in catalog.get("versions", [])}
    rows = []

    with tempfile.TemporaryDirectory(prefix="nte-static-") as temp:
        temp_root = Path(temp)
        for version in candidates:
            old = existing.get(version)
            has_files = old and all(
                not old.get(section) or all(
                    (DOCS_DATA / Path(old[section][key]).relative_to("data")).exists()
                    for key in ["json", "urls", "aria2"]
                    if old[section].get(key)
                )
                for section in ["full", "patches"]
            )
            if has_files and old.get("status") == 200:
                rows.append(old)
                continue
            row = normalize_paths(process_version(version, temp_root, timeout=30))
            if row.get("status") == 0 and old:
                print(
                    f"::warning::Reusing cached NTE {version} metadata after transient "
                    f"ResList fetch failure: {row.get('error') or 'unknown network error'}"
                )
                rows.append(old)
                continue
            if row.get("status") == 0:
                raise RuntimeError(
                    f"could not fetch uncached NTE ResList for {version}: "
                    f"{row.get('error') or 'unknown network error'}"
                )
            rows.append(row)
        copy_url_lists(temp_root)

    rows.sort(key=lambda row: version_sort_key(row["version"]))
    annotate_release_types(rows)
    new_catalog = {
        **catalog,
        "last_checked_at": checked_at,
        "versions": rows,
    }
    if stable_compare_catalog(catalog) == stable_compare_catalog(new_catalog):
        new_catalog["generated_at"] = catalog.get("generated_at")
    else:
        new_catalog["generated_at"] = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")

    CATALOG_PATH.write_text(
        json.dumps(new_catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"NTE current={current}, versions={len(rows)}")


if __name__ == "__main__":
    main()
