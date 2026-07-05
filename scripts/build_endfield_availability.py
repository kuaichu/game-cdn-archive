#!/usr/bin/env python3
"""Bake parallel availability records into Endfield archive data."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from adapters.endfield import EndfieldAvailabilityAdapter  # noqa: E402
from scripts.availability_schema import ProbeResult, availability_block, probe_fact_defaults  # noqa: E402


DEFAULT_ROOT = ROOT / "docs" / "data" / "endfield"
GENERATED_BY = "scripts/build_endfield_availability.py"
STATES = ("available", "mirror_only", "unavailable", "unknown")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def old_state(record: dict[str, Any]) -> str:
    if record.get("official_available") is True:
        return "available"
    if record.get("official_available") is False and record.get("mirror_url"):
        return "mirror_only"
    if record.get("official_available") is False:
        return "unavailable"
    return "unknown"


def count_states(items: Iterable[dict[str, Any]], *, legacy: bool) -> dict[str, int]:
    counts = {state: 0 for state in STATES}
    for item in items:
        if legacy:
            state = old_state(item)
        else:
            state = str(((item.get("availability") or {}).get("interpretation") or {}).get("state") or "unknown")
        if state not in counts:
            counts[state] = 0
        counts[state] += 1
    return {key: value for key, value in counts.items() if value}


def reason_counts(items: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = str(((item.get("availability") or {}).get("interpretation") or {}).get("reason") or "")
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def iter_patch_parts(row: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for route in row.get("patches") or []:
        if not isinstance(route, dict):
            continue
        for part in route.get("parts") or []:
            if isinstance(part, dict):
                yield part


def iter_file_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    packages = [item for item in row.get("packages") or [] if isinstance(item, dict)]
    return [*packages, *iter_patch_parts(row)]


def upstream_probe(url: str, *, ok: bool, size: int, checked_at: str, error: str = "") -> ProbeResult:
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=0,
            method="UPSTREAM_ARCHIVE",
            checked_at=checked_at,
            final_url=url,
            content_type="",
            size=size,
            error=error,
            stale=False,
            scheduler_confidence="medium",
        ),
    }


def probes_from_item(item: dict[str, Any], checked_at: str) -> list[ProbeResult]:
    official_url = str(item.get("official_url") or "")
    mirror_url = str(item.get("mirror_url") or "")
    official_available = item.get("official_available") is True
    size = int(item.get("size") or 0)
    probes = [
        upstream_probe(
            official_url or f"endfield-upstream://missing-official/{item.get('name') or 'unknown'}",
            ok=official_available,
            size=size,
            checked_at=checked_at,
            error="" if official_available else "upstream_marked_unavailable",
        )
    ]
    if mirror_url:
        probes.append(upstream_probe(mirror_url, ok=True, size=size, checked_at=checked_at, error="mirror_fallback"))
    return probes


def summary_probe(version: str, checked_at: str) -> ProbeResult:
    url = f"endfield-upstream://{version}"
    return upstream_probe(url, ok=False, size=0, checked_at=checked_at, error="not_probed")


def apply_file_availability(item: dict[str, Any], checked_at: str, adapter: EndfieldAvailabilityAdapter) -> None:
    probes = probes_from_item(item, checked_at)
    interpretation = adapter.interpret(probes, item)
    item["availability"] = availability_block(
        candidates=probes,
        source_kind="upstream_archive",
        interpretation=interpretation,
        generated_by=GENERATED_BY,
    )


def apply_summary_availability(
    summary: dict[str, Any],
    version_row: dict[str, Any],
    counts: dict[str, int],
    reasons: dict[str, int],
    checked_at: str,
    adapter: EndfieldAvailabilityAdapter,
) -> None:
    version = str(summary.get("version") or version_row.get("version") or "unknown")
    summary["availability_counts"] = counts
    summary["availability_reasons"] = reasons
    version_row["availability_counts"] = counts
    version_row["availability_reasons"] = reasons
    record = dict(summary)
    probes = [summary_probe(version, checked_at)]
    interpretation = adapter.interpret(probes, record)
    summary["availability"] = availability_block(
        candidates=probes,
        source_kind="upstream_archive",
        interpretation=interpretation,
        generated_by=GENERATED_BY,
    )


def apply_availability(index: dict[str, Any], versions: dict[str, Any]) -> tuple[dict[str, int], dict[str, int], dict[str, int], list[str]]:
    adapter = EndfieldAvailabilityAdapter()
    checked_at = str(index.get("last_checked_at") or index.get("generated_from_observation") or "")
    before_totals = {state: 0 for state in STATES}
    after_totals = {state: 0 for state in STATES}
    summary_totals = {state: 0 for state in STATES}
    errors: list[str] = []

    for summary in index.get("versions") or []:
        if not isinstance(summary, dict):
            continue
        version = str(summary.get("version") or "")
        row = versions.get(version)
        if not isinstance(row, dict):
            errors.append(f"{version}:missing_version_row")
            continue

        items = iter_file_items(row)
        legacy_counts = count_states(items, legacy=True)
        for item in items:
            apply_file_availability(item, checked_at, adapter)
        new_counts = count_states(items, legacy=False)
        reasons = reason_counts(items)
        apply_summary_availability(summary, row, new_counts, reasons, checked_at, adapter)

        for state, count in legacy_counts.items():
            before_totals[state] = before_totals.get(state, 0) + count
        for state, count in new_counts.items():
            after_totals[state] = after_totals.get(state, 0) + count
        summary_state = str(((summary.get("availability") or {}).get("interpretation") or {}).get("state") or "unknown")
        summary_totals[summary_state] = summary_totals.get(summary_state, 0) + 1

        if legacy_counts != new_counts:
            errors.append(f"{version}:legacy_counts={legacy_counts}:new_counts={new_counts}")

    return (
        {key: value for key, value in before_totals.items() if value},
        {key: value for key, value in after_totals.items() if value},
        {key: value for key, value in summary_totals.items() if value},
        errors,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    index_path = args.root / "index.json"
    versions_path = args.root / "versions.json"
    index = deepcopy(load_json(index_path))
    versions = deepcopy(load_json(versions_path))

    before_totals, after_totals, summary_totals, errors = apply_availability(index, versions)

    print("Endfield availability migration")
    print(f"versions={len(index.get('versions') or [])}")
    print(f"before_file_states={before_totals}")
    print(f"after_file_states={after_totals}")
    print(f"summary_contract_states={summary_totals}")
    print(f"semantic_match={'PASS' if not errors else 'FAIL'}")
    if errors:
        print("\n".join(f"semantic_error={error}" for error in errors[:100]))
        raise SystemExit(1)

    if not args.dry_run:
        write_json(index_path, index, indent=2)
        write_json(versions_path, versions, indent=2)
        print(f"wrote={index_path}")
        print(f"wrote={versions_path}")


if __name__ == "__main__":
    main()
