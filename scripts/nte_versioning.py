"""Helpers for NTE version grouping and release labels."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def version_key(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"NTE version must look like X.Y.Z: {version!r}")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def version_family(version: str) -> str:
    major, minor, _patch = version_key(version)
    return f"{major}.{minor}"


def annotate_release_types(rows: list[dict[str, Any]]) -> None:
    available_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        version = str(row.get("version") or "")
        if row.get("status") != 200 or not row.get("full"):
            row.pop("release_type", None)
            continue
        available_by_family[version_family(version)].append(row)

    base_versions = {
        min(family_rows, key=lambda item: version_key(str(item.get("version") or ""))).get("version")
        for family_rows in available_by_family.values()
        if family_rows
    }
    for row in rows:
        version = row.get("version")
        if row.get("status") == 200 and row.get("full"):
            row["release_type"] = "major" if version in base_versions else "patch"
