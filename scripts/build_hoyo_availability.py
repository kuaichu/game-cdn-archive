#!/usr/bin/env python3
"""Bake parallel availability records into HoYo split metadata."""

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

from adapters.hoyo import HoyoAvailabilityAdapter  # noqa: E402
from scripts.availability_schema import ProbeResult, availability_block, probe_fact_defaults  # noqa: E402


DEFAULT_ROOT = ROOT / "docs" / "data" / "hoyo"
GENERATED_BY = "scripts/build_hoyo_availability.py"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def as_list(value: Any) -> list[Any]:
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def metadata_probe_from_item(item: dict[str, Any], checked_at: str) -> ProbeResult:
    url = str(item.get("url") or "")
    size_present = "size" in item and item.get("size") not in {None, ""}
    size = int_value(item.get("size"))
    ok = bool(url) and size_present and size > 0
    error = "" if ok else ("metadata_size_missing" if not size_present else "size_zero")
    confidence = "medium" if ok else "low"
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=0,
            method="METADATA_SIZE",
            checked_at=checked_at,
            final_url=url,
            content_type="",
            size=size,
            error=error,
            stale=False,
            scheduler_confidence=confidence,
        ),
    }


def metadata_probe_from_summary(game_id: str, summary: dict[str, Any], checked_at: str) -> ProbeResult:
    url = str(summary.get("last_modified_url") or f"hoyo-metadata://{game_id}/{summary.get('version') or 'unknown'}")
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=False,
            status=0,
            method="METADATA_SUMMARY",
            checked_at=checked_at,
            final_url=url,
            content_type="",
            size=0,
            error="not_probed",
            stale=False,
            scheduler_confidence="low",
        ),
    }


def iter_download_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    game = row.get("game") or {}
    for key in ("full", "segments"):
        items.extend(item for item in as_list(game.get(key)) if isinstance(item, dict) and item.get("url"))
    for voice in (row.get("voice") or {}).values():
        items.extend(item for item in as_list(voice) if isinstance(item, dict) and item.get("url"))
    for patch in (row.get("update") or {}).values():
        items.extend(item for item in as_list((patch or {}).get("game")) if isinstance(item, dict) and item.get("url"))
        for voice in ((patch or {}).get("voice") or {}).values():
            items.extend(item for item in as_list(voice) if isinstance(item, dict) and item.get("url"))
    return items


def state_counts_from_items(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"available": 0, "unavailable": 0, "unknown": 0}
    for item in items:
        state = str(((item.get("availability") or {}).get("interpretation") or {}).get("state") or "unknown")
        if state not in counts:
            counts[state] = 0
        counts[state] += 1
    return {key: value for key, value in counts.items() if value}


def reason_counts_from_items(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = str(((item.get("availability") or {}).get("interpretation") or {}).get("reason") or "")
        if not reason:
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def old_unavailable_count(row: dict[str, Any]) -> int:
    return sum(1 for item in iter_download_items(row) if int_value(item.get("size")) <= 0)


def apply_version_availability(
    game_id: str,
    summary: dict[str, Any],
    row: dict[str, Any],
    checked_at: str,
    adapter: HoyoAvailabilityAdapter,
) -> tuple[int, int, dict[str, int]]:
    items = iter_download_items(row)
    old_count = old_unavailable_count(row)

    for item in items:
        probes = [metadata_probe_from_item(item, checked_at)]
        interpretation = adapter.interpret(probes, item)
        item["availability"] = availability_block(
            candidates=probes,
            source_kind="metadata_inference",
            interpretation=interpretation,
            generated_by=GENERATED_BY,
        )

    counts = state_counts_from_items(items) if items else {"unknown": 1}
    summary_record = dict(summary)
    summary_record["game_id"] = game_id
    summary_record["availability_counts"] = counts
    summary_record["availability_reasons"] = reason_counts_from_items(items)
    summary_probes = [metadata_probe_from_summary(game_id, summary, checked_at)]
    summary_interpretation = adapter.interpret(summary_probes, summary_record)
    summary["availability"] = availability_block(
        candidates=summary_probes,
        source_kind="metadata_inference",
        interpretation=summary_interpretation,
        generated_by=GENERATED_BY,
    )
    summary["availability_counts"] = counts
    summary["availability_reasons"] = reason_counts_from_items(items)

    new_count = int(summary["availability_counts"].get("unavailable", 0))
    return old_count, new_count, summary["availability_counts"]


def apply_availability(
    root: Path,
    index: dict[str, Any],
) -> tuple[dict[str, int], dict[str, int], dict[str, int], list[str], dict[Path, dict[str, Any]]]:
    adapter = HoyoAvailabilityAdapter()
    checked_at = str(index.get("last_checked_at") or index.get("generated_at") or "")
    before_totals = {"available": 0, "unavailable": 0, "unknown": 0}
    after_totals = {"available": 0, "unavailable": 0, "unknown": 0}
    summary_totals = {"available": 0, "unavailable": 0, "unknown": 0}
    errors: list[str] = []
    shards: dict[Path, dict[str, Any]] = {}

    for game in index.get("games") or []:
        if not isinstance(game, dict):
            continue
        game_id = str(game.get("id") or "")
        for summary in game.get("versions") or []:
            if not isinstance(summary, dict):
                continue
            version = str(summary.get("version") or "")
            shard_path = root / "versions" / game_id / f"{version}.json"
            if not shard_path.exists():
                errors.append(f"{game_id}:{version}:missing_shard:{shard_path}")
                continue
            row = load_json(shard_path)
            old_count, new_count, counts = apply_version_availability(game_id, summary, row, checked_at, adapter)
            shards[shard_path] = row

            item_count = len(iter_download_items(row))
            before_totals["unavailable"] += old_count
            before_totals["available"] += max(item_count - old_count, 0)
            after_totals["unavailable"] += new_count
            after_totals["available"] += int(counts.get("available", 0))
            after_totals["unknown"] += int(counts.get("unknown", 0)) if item_count else 0
            summary_state = str(((summary.get("availability") or {}).get("interpretation") or {}).get("state") or "unknown")
            summary_totals[summary_state] = summary_totals.get(summary_state, 0) + 1

            legacy_summary_count = int_value(summary.get("unavailable_items"))
            if legacy_summary_count != new_count:
                errors.append(
                    f"{game_id}:{version}:unavailable_items={legacy_summary_count}:new_unavailable={new_count}"
                )
            if old_count != new_count:
                errors.append(f"{game_id}:{version}:old_unavailable={old_count}:new_unavailable={new_count}")

    return before_totals, after_totals, summary_totals, errors, shards


def nonzero_unavailable_versions(index: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for game in index.get("games") or []:
        game_id = game.get("id")
        for summary in game.get("versions") or []:
            count = int_value(summary.get("unavailable_items"))
            if count:
                rows.append(f"{game_id}:{summary.get('version')}={count}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    index_path = args.root / "games.json"
    index = load_json(index_path)
    updated = deepcopy(index)
    before_totals, after_totals, summary_totals, errors, shards = apply_availability(args.root, updated)
    versions = sum(len(game.get("versions") or []) for game in updated.get("games") or [] if isinstance(game, dict))
    shard_count = len(shards)

    print("HoYo availability migration")
    print(f"games={len(updated.get('games') or [])}")
    print(f"versions={versions}")
    print(f"version_shards={shard_count}")
    print(f"before_download_item_states={before_totals}")
    print(f"after_download_item_states={after_totals}")
    print(f"summary_contract_states={summary_totals}")
    nonzero = nonzero_unavailable_versions(updated)
    print(f"unavailable_version_count={len(nonzero)}")
    for row in nonzero:
        print(f"unavailable_version={row}")
    print(f"semantic_match={'PASS' if not errors else 'FAIL'}")
    if errors:
        print("\n".join(f"semantic_error={error}" for error in errors[:100]))
        raise SystemExit(1)

    if not args.dry_run:
        write_json(index_path, updated, indent=2)
        for path, row in sorted(shards.items()):
            write_json(path, row, indent=2)
        print(f"wrote={index_path}")
        print(f"wrote_shards={len(shards)}")


if __name__ == "__main__":
    main()
