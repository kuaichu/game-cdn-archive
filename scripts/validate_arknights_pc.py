#!/usr/bin/env python3
"""Validate Arknights PC static data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO_ROOT / "docs" / "data" / "arknights"
REQUIRED_INDEX_FIELDS = ("source", "source_site", "official_api", "game", "versions")
REQUIRED_VERSION_FIELDS = (
    "version",
    "observed_at",
    "client_version",
    "package_items",
    "packed_size",
    "unpacked_size",
    "packages",
    "links",
)
REQUIRED_PACKAGE_FIELDS = ("name", "part", "size", "md5", "url")
REQUIRED_LIST_LINKS = ("json", "urls", "aria2")


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


def link_path(root: Path, value: str) -> Path:
    if value.startswith("data/"):
        return REPO_ROOT / "docs" / value
    return root / value


def validate(root: Path) -> tuple[bool, str]:
    root = root.resolve()
    index_path = root / "index.json"
    versions_path = root / "versions.json"
    lines: list[str] = [
        "Arknights PC validation",
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
    game_ok = (
        isinstance(game, dict)
        and game.get("id") == "arknights"
        and game.get("kind") == "arknights"
    )
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
    package_errors: list[str] = []
    link_errors: list[str] = []
    total_packages = 0

    for version, row in versions.items():
        if not isinstance(row, dict):
            field_errors.append(f"{version}:not_object")
            continue
        if row.get("version") != version:
            field_errors.append(f"{version}:version_mismatch:{row.get('version')}")
        for field in REQUIRED_VERSION_FIELDS:
            if not is_present(row.get(field)):
                field_errors.append(f"{version}:{field}")

        packages = row.get("packages")
        if not isinstance(packages, list) or not packages:
            field_errors.append(f"{version}:packages")
            continue
        total_packages += len(packages)

        expected_package_items = as_int(row.get("package_items"))
        if expected_package_items != len(packages):
            count_errors.append(f"{version}:version_package_items:{expected_package_items}!={len(packages)}")

        summary = summary_by_version.get(version) or {}
        summary_package_items = as_int(summary.get("package_items"))
        if summary_package_items != len(packages):
            count_errors.append(f"{version}:summary_package_items:{summary_package_items}!={len(packages)}")

        packed_size = sum(int(item.get("size") or 0) for item in packages if isinstance(item, dict))
        expected_packed_size = as_int(row.get("packed_size"))
        if expected_packed_size != packed_size:
            count_errors.append(f"{version}:packed_size:{expected_packed_size}!={packed_size}")
        summary_packed_size = as_int(summary.get("packed_size"))
        if summary_packed_size != packed_size:
            count_errors.append(f"{version}:summary_packed_size:{summary_packed_size}!={packed_size}")

        seen_parts: set[int] = set()
        for index, package in enumerate(packages, start=1):
            if not isinstance(package, dict):
                package_errors.append(f"{version}:{index}:not_object")
                continue
            missing = [field for field in REQUIRED_PACKAGE_FIELDS if not is_present(package.get(field))]
            if missing:
                package_errors.append(f"{version}:{index}:missing:{','.join(missing)}")
            part = as_int(package.get("part"))
            if part != index:
                package_errors.append(f"{version}:{index}:part:{part}")
            if part is not None:
                seen_parts.add(part)
            size = as_int(package.get("size"))
            if size is None or size <= 0:
                package_errors.append(f"{version}:{index}:size:{package.get('size')}")

        if seen_parts != set(range(1, len(packages) + 1)):
            package_errors.append(f"{version}:parts_not_contiguous")

        links = ((row.get("links") or {}).get("packages") or {})
        for link_name in REQUIRED_LIST_LINKS:
            value = links.get(link_name)
            if not is_present(value):
                link_errors.append(f"{version}:{link_name}:missing")
                continue
            path = link_path(root, str(value))
            if not path.exists():
                link_errors.append(f"{version}:{link_name}:missing_file:{value}")
                continue
            if link_name == "json":
                list_payload = load_json(path)
                if not isinstance(list_payload, list) or len(list_payload) != len(packages):
                    link_errors.append(f"{version}:json_list_count")
            else:
                text = path.read_text(encoding="utf-8")
                if not text.strip():
                    link_errors.append(f"{version}:{link_name}:empty")

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

    if package_errors:
        ok = False
        lines.append("packages=FAIL")
        lines.extend(f"package_error={item}" for item in package_errors[:50])
    else:
        lines.append("packages=PASS")

    if link_errors:
        ok = False
        lines.append("links=FAIL")
        lines.extend(f"link_error={item}" for item in link_errors[:50])
    else:
        lines.append("links=PASS")

    lines.append(f"index_versions={len(summary_versions)}")
    lines.append(f"version_records={len(version_keys)}")
    lines.append(f"total_packages={total_packages}")
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
