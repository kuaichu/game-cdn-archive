#!/usr/bin/env python3
"""Bake parallel availability records into Tower of Fantasy catalog and URL lists."""

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

from adapters.tof import TofAvailabilityAdapter  # noqa: E402
from scripts.availability_schema import ProbeResult, availability_block, probe_fact_defaults  # noqa: E402


DEFAULT_ROOT = ROOT / "docs" / "data" / "tof"
GENERATED_BY = "scripts/build_tof_availability.py"
STATES = ("available", "mirror_only", "unavailable", "unknown")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def old_reslist_state(row: dict[str, Any]) -> str:
    status = int_value(row.get("status"))
    if status == 200 and row.get("full"):
        return "available"
    if status >= 400:
        return "unavailable"
    return "unknown"


def status_error(row: dict[str, Any]) -> str:
    status = int_value(row.get("status"))
    if row.get("error"):
        return str(row.get("error"))
    if status >= 400:
        return f"HTTP {status}"
    if status == 0:
        return "not_probed"
    return ""


def reslist_probe(row: dict[str, Any], checked_at: str) -> ProbeResult:
    status = int_value(row.get("status"))
    url = str(row.get("reslist_url") or row.get("url") or f"tof-reslist://{row.get('version') or 'unknown'}")
    ok = 200 <= status < 400
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=status,
            method="GET",
            checked_at=checked_at,
            final_url=url,
            content_type="application/zip" if ok else "",
            size=int_value(row.get("reslist_bytes") or row.get("content_length")),
            last_modified=str(row.get("last_modified") or ""),
            error=status_error(row),
            stale=False,
            scheduler_confidence="high" if status else "low",
        ),
    }


def object_probe(item: dict[str, Any], checked_at: str) -> ProbeResult:
    url = str(item.get("url") or "")
    size = int_value(item.get("filesize"))
    ok = bool(url) and size > 0
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=0,
            method="RESLIST_METADATA",
            checked_at=checked_at,
            final_url=url,
            content_type="",
            size=size,
            error="" if ok else ("metadata_size_missing" if "filesize" not in item else "size_zero"),
            stale=False,
            scheduler_confidence="medium" if ok else "low",
        ),
    }


def state_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {state: 0 for state in STATES}
    for item in items:
        state = str(((item.get("availability") or {}).get("interpretation") or {}).get("state") or "unknown")
        counts[state] = counts.get(state, 0) + 1
    return {key: value for key, value in counts.items() if value}


def reason_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = str(((item.get("availability") or {}).get("interpretation") or {}).get("reason") or "")
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def load_section_items(root: Path, section: dict[str, Any] | None) -> tuple[Path | None, list[dict[str, Any]]]:
    if not isinstance(section, dict) or not section.get("json"):
        return None, []
    rel = Path(str(section["json"]))
    if rel.parts and rel.parts[0] == "data":
        path = root.parent / rel.relative_to("data")
    else:
        path = root / rel
    if not path.exists():
        raise FileNotFoundError(path)
    items = load_json(path)
    if not isinstance(items, list):
        raise ValueError(f"{path} must contain a JSON list")
    return path, [item for item in items if isinstance(item, dict)]


def apply_object_availability(items: list[dict[str, Any]], checked_at: str, adapter: TofAvailabilityAdapter) -> None:
    for item in items:
        probes = [object_probe(item, checked_at)]
        interpretation = adapter.interpret(probes, item)
        item["availability"] = availability_block(
            candidates=probes,
            source_kind="metadata_inference",
            interpretation=interpretation,
            generated_by=GENERATED_BY,
        )


def apply_availability(root: Path, catalog: dict[str, Any]) -> tuple[dict[str, int], dict[str, int], dict[str, int], list[str], dict[Path, list[dict[str, Any]]]]:
    adapter = TofAvailabilityAdapter()
    checked_at = str(catalog.get("last_checked_at") or catalog.get("generated_at") or "")
    before_reslist = {state: 0 for state in STATES}
    after_reslist = {state: 0 for state in STATES}
    object_totals = {state: 0 for state in STATES}
    errors: list[str] = []
    shards: dict[Path, list[dict[str, Any]]] = {}

    for row in catalog.get("versions") or []:
        if not isinstance(row, dict):
            continue
        version = str(row.get("version") or "")
        old_state = old_reslist_state(row)
        before_reslist[old_state] = before_reslist.get(old_state, 0) + 1

        probes = [reslist_probe(row, checked_at)]
        interpretation = adapter.interpret(probes, row)
        row["availability"] = availability_block(
            candidates=probes,
            source_kind="live_probe",
            interpretation=interpretation,
            generated_by=GENERATED_BY,
        )
        new_state = interpretation["state"]
        after_reslist[new_state] = after_reslist.get(new_state, 0) + 1
        if old_state != new_state:
            errors.append(f"{version}:old_state={old_state}:new_state={new_state}")

        section_counts: dict[str, dict[str, int]] = {}
        section_reasons: dict[str, dict[str, int]] = {}
        for section_name in ("full", "patches"):
            path, items = load_section_items(root, row.get(section_name))
            if path is None:
                continue
            apply_object_availability(items, checked_at, adapter)
            shards[path] = items
            counts = state_counts(items)
            section_counts[section_name] = counts
            section_reasons[section_name] = reason_counts(items)
            for state, count in counts.items():
                object_totals[state] = object_totals.get(state, 0) + count

        if section_counts:
            row["availability_counts"] = section_counts
            row["availability_reasons"] = section_reasons

    return (
        {key: value for key, value in before_reslist.items() if value},
        {key: value for key, value in after_reslist.items() if value},
        {key: value for key, value in object_totals.items() if value},
        errors,
        shards,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    catalog_path = args.root / "catalog.json"
    catalog = deepcopy(load_json(catalog_path))
    before_reslist, after_reslist, object_totals, errors, shards = apply_availability(args.root, catalog)

    print("Tower of Fantasy availability migration")
    print(f"versions={len(catalog.get('versions') or [])}")
    print("summary_source_kind=live_probe")
    print("object_source_kind=metadata_inference")
    print(f"before_reslist_states={before_reslist}")
    print(f"after_reslist_states={after_reslist}")
    print(f"object_states={object_totals}")
    print(f"url_list_shards={len(shards)}")
    print(f"semantic_match={'PASS' if not errors else 'FAIL'}")
    if errors:
        print("\n".join(f"semantic_error={error}" for error in errors[:100]))
        raise SystemExit(1)

    if not args.dry_run:
        write_json(catalog_path, catalog, indent=2)
        for path, items in sorted(shards.items()):
            write_json(path, items, indent=2)
        print(f"wrote={catalog_path}")
        print(f"wrote_shards={len(shards)}")


if __name__ == "__main__":
    main()
