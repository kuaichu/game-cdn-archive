#!/usr/bin/env python3
"""Validate Endfield static archive data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO_ROOT / "docs" / "data" / "endfield"
REQUIRED_INDEX_FIELDS = (
    "source",
    "source_site",
    "official_api",
    "last_checked_at",
    "generated_from_observation",
    "game",
    "versions",
)
REQUIRED_VERSION_FIELDS = (
    "version",
    "released_at",
    "observed_at",
    "packed_size",
    "unpacked_size",
    "packages",
    "patches",
    "links",
)
REQUIRED_FILE_FIELDS = ("name", "size", "official_url", "official_available", "preferred_url")
REQUIRED_LINK_FIELDS = ("urls", "aria2")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return True


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def version_key(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def link_path(value: str) -> Path:
    if value.startswith("data/"):
        return REPO_ROOT / "docs" / value
    return DEFAULT_ROOT / value


def validate_file(version: str, label: str, index: int, item: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"{version}:{label}:{index}:not_object"]
    for field in REQUIRED_FILE_FIELDS:
        if not is_present(item.get(field)):
            errors.append(f"{version}:{label}:{index}:missing:{field}")
    if not isinstance(item.get("official_available"), bool):
        errors.append(f"{version}:{label}:{index}:official_available_not_bool")
    size = as_int(item.get("size"))
    if size is None or size <= 0:
        errors.append(f"{version}:{label}:{index}:size:{item.get('size')}")
    preferred = item.get("preferred_url")
    official = item.get("official_url")
    mirror = item.get("mirror_url")
    if preferred and preferred not in {official, mirror}:
        errors.append(f"{version}:{label}:{index}:preferred_url_not_known")
    return errors


def validate_links(version: str, mode: str, links: Any, expected_items: int) -> list[str]:
    errors: list[str] = []
    if expected_items == 0:
        if links not in (None, {}, ""):
            errors.append(f"{version}:{mode}:unexpected_links")
        return errors
    if not isinstance(links, dict):
        return [f"{version}:{mode}:links_not_object"]
    for field in REQUIRED_LINK_FIELDS:
        value = links.get(field)
        if not is_present(value):
            errors.append(f"{version}:{mode}:{field}:missing")
            continue
        path = link_path(str(value))
        if not path.exists():
            errors.append(f"{version}:{mode}:{field}:missing_file:{value}")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"{version}:{mode}:{field}:empty")
        if field == "urls":
            url_count = len([line for line in text.splitlines() if line.strip()])
            if url_count != expected_items:
                errors.append(f"{version}:{mode}:urls_count:{url_count}!={expected_items}")
    return errors


def validate(root: Path) -> tuple[bool, str]:
    root = root.resolve()
    index_path = root / "index.json"
    versions_path = root / "versions.json"
    lines = [
        "Endfield archive validation",
        f"root={root}",
        f"index={index_path}",
        f"versions={versions_path}",
    ]
    ok = True

    if not index_path.exists():
        return False, "\n".join([*lines, "index_exists=FAIL", "result=FAIL"]) + "\n"
    if not versions_path.exists():
        return False, "\n".join([*lines, "versions_exists=FAIL", "result=FAIL"]) + "\n"

    index = load_json(index_path)
    versions = load_json(versions_path)
    summaries = index.get("versions") if isinstance(index, dict) else None
    if not isinstance(index, dict):
        return False, "\n".join([*lines, "index_object=FAIL", "result=FAIL"]) + "\n"
    if not isinstance(versions, dict):
        return False, "\n".join([*lines, "versions_object=FAIL", "result=FAIL"]) + "\n"
    if not isinstance(summaries, list):
        return False, "\n".join([*lines, "index_versions_array=FAIL", "result=FAIL"]) + "\n"

    missing_index_fields = [field for field in REQUIRED_INDEX_FIELDS if not is_present(index.get(field))]
    if missing_index_fields:
        ok = False
        lines.append("index_required_fields=FAIL")
        lines.append("missing_index_fields=" + ",".join(missing_index_fields))
    else:
        lines.append("index_required_fields=PASS")

    game = index.get("game") or {}
    game_ok = isinstance(game, dict) and game.get("id") == "endfield" and game.get("kind") == "endfield"
    lines.append("game_identity=" + ("PASS" if game_ok else "FAIL"))
    ok = ok and game_ok

    summary_versions = [str(item.get("version") or "") for item in summaries if isinstance(item, dict)]
    version_keys = [str(key) for key in versions.keys()]
    duplicate_versions = sorted({version for version in summary_versions if summary_versions.count(version) > 1})
    if duplicate_versions:
        ok = False
        lines.append("index_duplicate_versions=FAIL")
        lines.append("duplicate_versions=" + ",".join(duplicate_versions))
    else:
        lines.append("index_duplicate_versions=PASS")

    missing_from_versions = sorted(set(summary_versions) - set(version_keys), key=version_key)
    missing_from_index = sorted(set(version_keys) - set(summary_versions), key=version_key)
    if missing_from_versions or missing_from_index:
        ok = False
        lines.append("version_set_match=FAIL")
        if missing_from_versions:
            lines.append("missing_from_versions=" + ",".join(missing_from_versions))
        if missing_from_index:
            lines.append("missing_from_index=" + ",".join(missing_from_index))
    else:
        lines.append("version_set_match=PASS")

    summary_by_version = {
        str(item.get("version") or ""): item
        for item in summaries
        if isinstance(item, dict) and item.get("version")
    }
    field_errors: list[str] = []
    count_errors: list[str] = []
    file_errors: list[str] = []
    link_errors: list[str] = []
    total_packages = 0
    total_patch_parts = 0

    for version, row in versions.items():
        if not isinstance(row, dict):
            field_errors.append(f"{version}:not_object")
            continue
        if row.get("version") != version:
            field_errors.append(f"{version}:version_mismatch:{row.get('version')}")
        for field in REQUIRED_VERSION_FIELDS:
            if field == "patches":
                if field not in row or not isinstance(row.get(field), list):
                    field_errors.append(f"{version}:{field}")
                continue
            if not is_present(row.get(field)):
                field_errors.append(f"{version}:{field}")

        packages = row.get("packages")
        if not isinstance(packages, list) or not packages:
            field_errors.append(f"{version}:packages")
            continue
        total_packages += len(packages)
        patches = row.get("patches") if isinstance(row.get("patches"), list) else []
        patch_parts = [
            part
            for route in patches
            if isinstance(route, dict)
            for part in route.get("parts") or []
        ]
        total_patch_parts += len(patch_parts)

        summary = summary_by_version.get(version) or {}
        summary_package_items = as_int(summary.get("package_items"))
        if summary_package_items != len(packages):
            count_errors.append(f"{version}:summary_package_items:{summary_package_items}!={len(packages)}")
        summary_patch_routes = as_int(summary.get("patch_routes"))
        if summary_patch_routes != len(patches):
            count_errors.append(f"{version}:summary_patch_routes:{summary_patch_routes}!={len(patches)}")
        row_packed_size = as_int(row.get("packed_size"))
        if row_packed_size is None or row_packed_size <= 0:
            count_errors.append(f"{version}:packed_size:{row.get('packed_size')}")
        if as_int(summary.get("packed_size")) != row_packed_size:
            count_errors.append(f"{version}:summary_packed_size:{summary.get('packed_size')}!={row_packed_size}")
        mirror_items = sum(1 for item in packages if isinstance(item, dict) and item.get("mirror_url"))
        if as_int(summary.get("mirror_items")) != mirror_items:
            count_errors.append(f"{version}:mirror_items:{summary.get('mirror_items')}!={mirror_items}")

        for index, item in enumerate(packages, start=1):
            file_errors.extend(validate_file(version, "package", index, item))

        for route_index, route in enumerate(patches, start=1):
            if not isinstance(route, dict):
                field_errors.append(f"{version}:patch:{route_index}:not_object")
                continue
            for field in ("from", "to", "size", "unpacked_size", "parts"):
                if field == "parts":
                    if field not in route or not isinstance(route.get(field), list):
                        field_errors.append(f"{version}:patch:{route_index}:parts")
                    continue
                if not is_present(route.get(field)):
                    field_errors.append(f"{version}:patch:{route_index}:{field}")
            if route.get("to") != version:
                field_errors.append(f"{version}:patch:{route_index}:to:{route.get('to')}")
            parts = route.get("parts") if isinstance(route.get("parts"), list) else []
            route_size = sum(int(item.get("size") or 0) for item in parts if isinstance(item, dict))
            if as_int(route.get("size")) != route_size:
                count_errors.append(f"{version}:patch:{route_index}:size:{route.get('size')}!={route_size}")
            for part_index, part in enumerate(parts, start=1):
                file_errors.extend(validate_file(version, f"patch{route_index}", part_index, part))

        links = row.get("links") or {}
        link_errors.extend(validate_links(version, "packages", links.get("packages"), len(packages)))
        link_errors.extend(validate_links(version, "patches", links.get("patches"), len(patch_parts)))

    if field_errors:
        ok = False
        lines.append("version_required_fields=FAIL")
        lines.extend(f"version_field_error={item}" for item in field_errors[:50])
    else:
        lines.append("version_required_fields=PASS")

    if count_errors:
        ok = False
        lines.append("counts=FAIL")
        lines.extend(f"count_error={item}" for item in count_errors[:50])
    else:
        lines.append("counts=PASS")

    if file_errors:
        ok = False
        lines.append("files=FAIL")
        lines.extend(f"file_error={item}" for item in file_errors[:50])
    else:
        lines.append("files=PASS")

    if link_errors:
        ok = False
        lines.append("links=FAIL")
        lines.extend(f"link_error={item}" for item in link_errors[:50])
    else:
        lines.append("links=PASS")

    lines.append(f"index_versions={len(summary_versions)}")
    lines.append(f"version_records={len(version_keys)}")
    lines.append(f"total_packages={total_packages}")
    lines.append(f"total_patch_parts={total_patch_parts}")
    lines.append("result=" + ("PASS" if ok else "FAIL"))
    return ok, "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--log", type=Path, default=None)
    args = parser.parse_args()

    ok, report = validate(args.root)
    print(report, end="")
    if args.log:
        args.log.write_text(report, encoding="utf-8")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
