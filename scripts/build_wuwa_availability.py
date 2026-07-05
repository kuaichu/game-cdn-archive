#!/usr/bin/env python3
"""Bake parallel availability records into WuWa multi-CDN metadata."""

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

from adapters.wuwa import WuwaAvailabilityAdapter  # noqa: E402
from scripts.availability_schema import ProbeResult, availability_block, probe_fact_defaults  # noqa: E402


DEFAULT_ROOT = ROOT / "docs" / "data" / "wuwa"
GENERATED_BY = "scripts/build_wuwa_availability.py"
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


def size_present(record: dict[str, Any]) -> bool:
    return "size" in record and record.get("size") not in {None, ""}


def unique_candidates(record: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    primary = str(record.get("url") or "").strip()
    if primary:
        urls.append(primary)
    for value in record.get("urls") or []:
        url = str(value or "").strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def old_state(record: dict[str, Any]) -> str:
    if int_value(record.get("size")) > 0 and unique_candidates(record):
        return "available"
    return "unavailable"


def metadata_error(record: dict[str, Any]) -> str:
    if not size_present(record):
        return "metadata_size_missing"
    if int_value(record.get("size")) <= 0:
        return "size_zero"
    return "not_probed"


def metadata_probe(url: str, record: dict[str, Any], checked_at: str) -> ProbeResult:
    size = int_value(record.get("size"))
    ok = bool(url) and size_present(record) and size > 0
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=0,
            method="WUWA_METADATA",
            checked_at=checked_at,
            final_url=url,
            content_type="",
            size=size,
            error="" if ok else metadata_error(record),
            stale=False,
            scheduler_confidence="medium" if ok else "low",
        ),
    }


def probes_from_record(record: dict[str, Any], checked_at: str) -> list[ProbeResult]:
    urls = unique_candidates(record)
    if not urls:
        label = str(record.get("dest") or record.get("name") or "unknown").replace("\\", "/").strip("/") or "unknown"
        urls = [f"wuwa-metadata://missing/{label}"]
    return [metadata_probe(url, record, checked_at) for url in urls]


def summary_probe(version: str, checked_at: str) -> ProbeResult:
    url = f"wuwa-metadata://{version}"
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=False,
            status=0,
            method="WUWA_METADATA_SUMMARY",
            checked_at=checked_at,
            final_url=url,
            content_type="",
            size=0,
            error="not_probed",
            stale=False,
            scheduler_confidence="medium",
        ),
    }


def iter_patch_parts(row: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for route in row.get("patches") or []:
        if not isinstance(route, dict):
            continue
        for part in route.get("parts") or []:
            if isinstance(part, dict):
                yield part


def iter_file_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    files = [item for item in row.get("files") or [] if isinstance(item, dict)]
    return [*files, *iter_patch_parts(row)]


def count_states(items: Iterable[dict[str, Any]], *, legacy: bool) -> dict[str, int]:
    counts = {state: 0 for state in STATES}
    for item in items:
        state = old_state(item) if legacy else str(((item.get("availability") or {}).get("interpretation") or {}).get("state") or "unknown")
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


def apply_item_availability(item: dict[str, Any], checked_at: str, adapter: WuwaAvailabilityAdapter) -> None:
    probes = probes_from_record(item, checked_at)
    interpretation = adapter.interpret(probes, item)
    item["availability"] = availability_block(
        candidates=probes,
        source_kind="metadata_inference",
        interpretation=interpretation,
        generated_by=GENERATED_BY,
    )


def apply_items_availability(items: list[dict[str, Any]], checked_at: str, adapter: WuwaAvailabilityAdapter) -> None:
    for item in items:
        apply_item_availability(item, checked_at, adapter)


def docs_path(root: Path, link: str) -> Path:
    rel = Path(str(link))
    if not str(link).startswith("data/wuwa/"):
        raise ValueError(f"Unexpected WuWa data link: {link}")
    return root.parents[1] / rel


def load_list_items(root: Path, section: Any) -> tuple[Path | None, list[dict[str, Any]]]:
    if not isinstance(section, dict) or not section.get("json"):
        return None, []
    path = docs_path(root, str(section["json"]))
    if not path.exists():
        raise FileNotFoundError(path)
    payload = load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return path, [item for item in payload if isinstance(item, dict)]


def apply_summary_availability(
    summary: dict[str, Any],
    version_row: dict[str, Any],
    counts: dict[str, int],
    reasons: dict[str, int],
    checked_at: str,
    adapter: WuwaAvailabilityAdapter,
) -> None:
    version = str(summary.get("version") or version_row.get("version") or "unknown")
    summary["availability_counts"] = counts
    summary["availability_reasons"] = reasons
    version_row["availability_counts"] = counts
    version_row["availability_reasons"] = reasons
    probe = summary_probe(version, checked_at)
    interpretation = adapter.interpret([probe], summary)
    summary["availability"] = availability_block(
        candidates=[probe],
        source_kind="metadata_inference",
        interpretation=interpretation,
        generated_by=GENERATED_BY,
    )


def apply_availability(
    root: Path,
    index: dict[str, Any],
    versions: dict[str, dict[str, Any]],
) -> tuple[dict[str, int], dict[str, int], dict[str, int], list[str], dict[Path, list[dict[str, Any]]]]:
    adapter = WuwaAvailabilityAdapter()
    checked_at = str(index.get("last_checked_at") or index.get("generated_at") or "")
    summaries = index.get("versions") or []
    before_totals = {state: 0 for state in STATES}
    after_totals = {state: 0 for state in STATES}
    summary_totals = {state: 0 for state in STATES}
    errors: list[str] = []
    list_shards: dict[Path, list[dict[str, Any]]] = {}

    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        version = str(summary.get("version") or "")
        row = versions.get(version)
        if not isinstance(row, dict):
            errors.append(f"{version}:missing_version_shard")
            continue

        items = iter_file_items(row)
        legacy_counts = count_states(items, legacy=True)
        apply_items_availability(items, checked_at, adapter)
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

        path, file_items = load_list_items(root, (row.get("links") or {}).get("files"))
        if path is not None:
            apply_items_availability(file_items, checked_at, adapter)
            list_shards[path] = file_items
        for route in row.get("patches") or []:
            if not isinstance(route, dict):
                continue
            path, patch_items = load_list_items(root, route.get("links"))
            if path is not None:
                apply_items_availability(patch_items, checked_at, adapter)
                list_shards[path] = patch_items

    return (
        {key: value for key, value in before_totals.items() if value},
        {key: value for key, value in after_totals.items() if value},
        {key: value for key, value in summary_totals.items() if value},
        errors,
        list_shards,
    )


def load_versions(root: Path) -> dict[str, dict[str, Any]]:
    versions: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "versions").glob("*.json")):
        payload = load_json(path)
        if isinstance(payload, dict):
            version = str(payload.get("version") or path.stem)
            versions[version] = payload
    return versions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    index_path = args.root / "index.json"
    index = deepcopy(load_json(index_path))
    versions = deepcopy(load_versions(args.root))

    before_totals, after_totals, summary_totals, errors, list_shards = apply_availability(args.root, index, versions)

    print("WuWa availability migration")
    print("source_kind=metadata_inference")
    print("live_probe_performed=NO")
    print("baseline=current frontend has no per-file live availability; URL presence + positive size remains available")
    print(f"versions={len(index.get('versions') or [])}")
    print(f"version_shards={len(versions)}")
    print(f"list_shards={len(list_shards)}")
    print(f"before_file_states={before_totals}")
    print(f"after_file_states={after_totals}")
    print(f"summary_contract_states={summary_totals}")
    print(f"semantic_match={'PASS' if not errors else 'FAIL'}")
    if errors:
        print("\n".join(f"semantic_error={error}" for error in errors[:100]))
        raise SystemExit(1)

    if not args.dry_run:
        write_json(index_path, index, indent=2)
        for version, payload in sorted(versions.items()):
            write_json(args.root / "versions" / f"{version}.json", payload, indent=2)
        for path, items in sorted(list_shards.items()):
            write_json(path, items, indent=2)
        print(f"wrote={index_path}")
        print(f"wrote_version_shards={len(versions)}")
        print(f"wrote_list_shards={len(list_shards)}")


if __name__ == "__main__":
    main()
