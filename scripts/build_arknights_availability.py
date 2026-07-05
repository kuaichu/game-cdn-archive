#!/usr/bin/env python3
"""Bake parallel availability records into Arknights PC package data."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from adapters.arknights import ArknightsAvailabilityAdapter  # noqa: E402
from scripts.availability_schema import availability_block  # noqa: E402
from scripts.probe_scheduler import (  # noqa: E402
    ProbeScheduleConfig,
    previous_probe_by_url,
    schedule_probe_candidates,
)


DEFAULT_ROOT = ROOT / "docs" / "data" / "arknights"
GENERATED_BY = "scripts/build_arknights_availability.py"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def package_records(versions: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for version, row in versions.items():
        for package in row.get("packages") or []:
            if not isinstance(package, dict):
                continue
            package["_availability_context"] = {
                "version": version,
                "name": package.get("name") or "",
                "part": package.get("part"),
            }
            records.append(package)
    return records


def strip_context(versions: dict[str, Any]) -> None:
    for row in versions.values():
        for package in row.get("packages") or []:
            if isinstance(package, dict):
                package.pop("_availability_context", None)


def state_counts(versions: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in versions.values():
        for package in row.get("packages") or []:
            interpretation = ((package.get("availability") or {}).get("interpretation") or {})
            state = str(interpretation.get("state") or "missing")
            counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items()))


def apply_availability(versions: dict[str, Any], config: ProbeScheduleConfig) -> tuple[dict[str, int], dict[str, int]]:
    before_counts = state_counts(versions)
    records = package_records(versions)
    previous = previous_probe_by_url(records)
    adapter = ArknightsAvailabilityAdapter()

    for record in records:
        url = record.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError(f"Arknights package has invalid URL: {record.get('name')}")
        probes = schedule_probe_candidates([url], previous=previous, config=config)
        interpretation = adapter.interpret(probes, record)
        record["availability"] = availability_block(
            candidates=probes,
            source_kind="live_probe",
            interpretation=interpretation,
            generated_by=GENERATED_BY,
        )

    strip_context(versions)
    return before_counts, state_counts(versions)


def compare_semantics(original: dict[str, Any], updated: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    original_urls = [
        package.get("url")
        for row in original.values()
        for package in row.get("packages", [])
        if isinstance(package, dict)
    ]
    updated_packages = [
        package
        for row in updated.values()
        for package in row.get("packages", [])
        if isinstance(package, dict)
    ]
    updated_urls = [package.get("url") for package in updated_packages]
    if original_urls != updated_urls:
        errors.append("package URL order changed")
    if len(original_urls) != len(updated_packages):
        errors.append(f"package count changed: {len(original_urls)} != {len(updated_packages)}")

    unavailable = []
    for package in updated_packages:
        interpretation = ((package.get("availability") or {}).get("interpretation") or {})
        if interpretation.get("state") != "available":
            unavailable.append(f"{package.get('name')}:{interpretation.get('state')}:{interpretation.get('reason')}")
        if interpretation.get("preferred_url") != package.get("url"):
            unavailable.append(f"{package.get('name')}:preferred_url_changed")
    if unavailable:
        errors.extend(unavailable[:20])
    return not errors, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-full", action="store_true")
    args = parser.parse_args()

    versions_path = args.root / "versions.json"
    versions = load_json(versions_path)
    original = deepcopy(versions)
    config = ProbeScheduleConfig.from_env()
    if args.force_full:
        config = ProbeScheduleConfig(
            ttl_hours=config.ttl_hours,
            failed_ttl_hours=config.failed_ttl_hours,
            grace_hours=config.grace_hours,
            rotation_limit=config.rotation_limit,
            force_full=True,
            timeout=config.timeout,
        )

    before_counts, after_counts = apply_availability(versions, config)
    ok, errors = compare_semantics(original, versions)

    print("Arknights availability migration")
    print(f"versions={len(versions)}")
    print(f"packages={sum(len(row.get('packages') or []) for row in versions.values())}")
    print(f"before_states={before_counts}")
    print(f"after_states={after_counts}")
    print(f"semantic_match={'PASS' if ok else 'FAIL'}")
    if errors:
        print("\n".join(f"semantic_error={error}" for error in errors))
        raise SystemExit(1)

    if not args.dry_run:
        write_json(versions_path, versions)
        print(f"wrote={versions_path}")


if __name__ == "__main__":
    main()
