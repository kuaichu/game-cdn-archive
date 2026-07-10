#!/usr/bin/env python3
"""Bake parallel availability records into Android APK data."""

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

from adapters.android import APK_CONTENT_TYPES, APK_SIZE_THRESHOLD_BYTES, AndroidAvailabilityAdapter  # noqa: E402
from scripts.availability_schema import ProbeResult, availability_block, probe_fact_defaults  # noqa: E402
from scripts.probe_scheduler import ProbeScheduleConfig, previous_probe_by_url, schedule_probe_candidates  # noqa: E402


DEFAULT_ROOT = ROOT / "docs" / "data" / "android"
GENERATED_BY = "scripts/build_android_availability.py"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_records(index: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for game_id, game in (index.get("games") or {}).items():
        for entry in game.get("versions") or []:
            if not isinstance(entry, dict):
                continue
            entry["_availability_context"] = {"game_id": game_id, "version": entry.get("version") or ""}
            records.append(entry)
    return records


def strip_context(index: dict[str, Any]) -> None:
    for game in (index.get("games") or {}).values():
        for entry in game.get("versions") or []:
            if isinstance(entry, dict):
                entry.pop("_availability_context", None)


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def normalize_error(error: Any) -> str:
    text = str(error or "")
    lowered = text.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if "getaddrinfo" in lowered or "no address" in lowered or "could not resolve host" in lowered:
        return f"dns: {text}"
    if "certificate" in lowered or "tls" in lowered or "ssl" in lowered:
        return f"tls: {text}"
    return text


def legacy_probe_from_record(record: dict[str, Any], checked_at: str) -> ProbeResult:
    status = int_value(record.get("status"))
    content_type = str(record.get("content_type") or "")
    size = int_value(record.get("size"))
    error = normalize_error(record.get("error"))
    ok = 200 <= status < 400 and not error and "text/html" not in content_type.lower() and "application/xml" not in content_type.lower()
    return {
        "url": str(record["url"]),
        "probe": probe_fact_defaults(
            ok=ok,
            status=status,
            method="LEGACY_ANDROID_HEAD",
            checked_at=checked_at,
            final_url=str(record.get("url") or ""),
            content_type=content_type,
            size=size,
            last_modified=str(record.get("last_modified") or ""),
            etag=str(record.get("etag") or "").strip('"'),
            error=error,
            bot_challenge=record.get("probe_status") == "bot_challenge_assumed_available",
            stale=False,
            scheduler_confidence="high",
        ),
    }


def android_previous_by_url(index: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, ProbeResult]:
    previous = previous_probe_by_url(records)
    checked_at = str(index.get("last_checked_at") or index.get("generated_at") or "")
    for record in records:
        url = record.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in previous:
            previous[url] = legacy_probe_from_record(record, checked_at)
    return previous


def old_unavailable(record: dict[str, Any]) -> bool:
    status = int_value(record.get("status"))
    return bool(record.get("error")) or status < 200 or status >= 400


def known_good_apk_record(record: dict[str, Any]) -> bool:
    status = int_value(record.get("status"))
    size = int_value(record.get("size"))
    content_type = str(record.get("content_type") or "").split(";", 1)[0].strip().lower()
    return (
        200 <= status < 400
        and not record.get("error")
        and size > APK_SIZE_THRESHOLD_BYTES
        and content_type in APK_CONTENT_TYPES
    )


def protect_known_good_interpretation(
    record: dict[str, Any],
    probes: list[ProbeResult],
    interpretation: dict[str, Any],
) -> dict[str, Any]:
    if not known_good_apk_record(record):
        return interpretation
    if interpretation.get("state") != "unavailable":
        return interpretation
    if interpretation.get("reason") not in {"content_type_mismatch", "size_zero"}:
        return interpretation
    probe = probes[0].get("probe") if probes else None
    if not isinstance(probe, dict) or int_value(probe.get("status")) not in {200, 206}:
        return interpretation
    protected = dict(interpretation)
    protected.update({
        "state": "unknown",
        "preferred_url": "",
        "confidence": "low",
        "retained": False,
        "display_label": "状态未知",
    })
    return protected


def fake_200_tightened(record: dict[str, Any], interpretation: dict[str, Any]) -> bool:
    if old_unavailable(record):
        return False
    if known_good_apk_record(record):
        return False
    status = int_value(record.get("status"))
    if status != 200:
        return False
    if interpretation.get("state") != "unavailable":
        return False
    return interpretation.get("reason") in {"content_type_mismatch", "size_zero"}


def state_counts(index: dict[str, Any], *, old: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}
    for game in (index.get("games") or {}).values():
        for entry in game.get("versions") or []:
            if not isinstance(entry, dict):
                continue
            if old:
                state = "unavailable" if old_unavailable(entry) else "available"
            else:
                state = str(((entry.get("availability") or {}).get("interpretation") or {}).get("state") or "missing")
            counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items()))


def apply_availability(index: dict[str, Any], config: ProbeScheduleConfig) -> tuple[dict[str, int], dict[str, int]]:
    before_counts = state_counts(index, old=True)
    records = iter_records(index)
    previous = android_previous_by_url(index, records)
    adapter = AndroidAvailabilityAdapter()

    for record in records:
        url = record.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError(f"Android APK record has invalid URL: {record.get('game_id')} {record.get('version')}")
        probes = schedule_probe_candidates([url], previous=previous, config=config)
        interpretation = adapter.interpret(probes, record)
        interpretation = protect_known_good_interpretation(record, probes, interpretation)
        record["availability"] = availability_block(
            candidates=probes,
            source_kind="live_probe",
            interpretation=interpretation,
            generated_by=GENERATED_BY,
        )

    strip_context(index)
    return before_counts, state_counts(index)


def tightened_fake_200_rows(original: dict[str, Any], updated: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    original_records = [
        entry
        for game in (original.get("games") or {}).values()
        for entry in game.get("versions", [])
        if isinstance(entry, dict)
    ]
    updated_records = [
        entry
        for game in (updated.get("games") or {}).values()
        for entry in game.get("versions", [])
        if isinstance(entry, dict)
    ]
    for original, updated_record in zip(original_records, updated_records):
        interpretation = ((updated_record.get("availability") or {}).get("interpretation") or {})
        if fake_200_tightened(original, interpretation):
            rows.append({
                "game_id": original.get("game_id"),
                "version": original.get("version"),
                "channel": original.get("channel"),
                "filename": original.get("filename"),
                "content_type": original.get("content_type"),
                "size": original.get("size"),
                "previous_state": "unknown",
                "reason": interpretation.get("reason"),
            })
    return rows


def compare_semantics(original: dict[str, Any], updated: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    allowed: list[str] = []
    original_records = [
        entry
        for game in (original.get("games") or {}).values()
        for entry in game.get("versions", [])
        if isinstance(entry, dict)
    ]
    updated_records = [
        entry
        for game in (updated.get("games") or {}).values()
        for entry in game.get("versions", [])
        if isinstance(entry, dict)
    ]
    if [entry.get("url") for entry in original_records] != [entry.get("url") for entry in updated_records]:
        errors.append("APK URL order changed")
    if len(original_records) != len(updated_records):
        errors.append(f"APK count changed: {len(original_records)} != {len(updated_records)}")

    for original, updated_record in zip(original_records, updated_records):
        old_bad = old_unavailable(original)
        interpretation = ((updated_record.get("availability") or {}).get("interpretation") or {})
        new_bad = interpretation.get("state") == "unavailable"
        if old_bad != new_bad:
            if fake_200_tightened(original, interpretation):
                allowed.append(
                    f"{original.get('game_id')}:{original.get('version')}:"
                    f"{original.get('filename')}:unknown->unavailable:{interpretation.get('reason')}"
                )
                continue
            errors.append(
                f"{original.get('game_id')}:{original.get('version')}:"
                f"old_unavailable={old_bad}:new_state={interpretation.get('state')}:"
                f"reason={interpretation.get('reason')}"
            )
    return not errors, errors, allowed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-full", action="store_true")
    parser.add_argument(
        "--allow-semantic-changes",
        action="store_true",
        help="Allow ongoing live availability changes after printing the drift list.",
    )
    args = parser.parse_args()

    index_path = args.root / "index.json"
    index = load_json(index_path)
    original = deepcopy(index)
    previous_contract_counts = state_counts(index)
    config = ProbeScheduleConfig.android_apks_from_env()
    if args.force_full:
        config = ProbeScheduleConfig(
            ttl_hours=config.ttl_hours,
            failed_ttl_hours=config.failed_ttl_hours,
            grace_hours=config.grace_hours,
            rotation_limit=config.rotation_limit,
            force_full=True,
            timeout=config.timeout,
        )

    before_counts, after_counts = apply_availability(index, config)
    ok, errors, allowed_tightens = compare_semantics(original, index)
    tightened_rows = tightened_fake_200_rows(original, index)
    total = sum(len((game.get("versions") or [])) for game in (index.get("games") or {}).values())

    print("Android availability migration")
    print(f"games={len(index.get('games') or {})}")
    print(f"apks={total}")
    print(f"previous_contract_states={previous_contract_counts}")
    print(f"before_states={before_counts}")
    print(f"after_states={after_counts}")
    print(f"intentional_tighten_count={len(allowed_tightens)}")
    if allowed_tightens:
        print("intentional_tighten_note=fake HTTP 200 APK placeholders are intentionally tightened from unknown to unavailable")
    for row in tightened_rows:
        print(
            "intentional_tighten="
            f"{row['game_id']} {row['version']} {row['channel']} "
            f"{row['filename']} content_type={row['content_type']} size={row['size']} "
            f"{row['previous_state']}->unavailable reason={row['reason']}"
        )
    print(f"semantic_match={'PASS' if ok else 'FAIL'}")
    if errors:
        print("\n".join(f"semantic_error={error}" for error in errors[:100]))
        if not args.allow_semantic_changes:
            raise SystemExit(1)
        print("semantic_change_policy=ALLOW_EXPLICIT")

    if not args.dry_run:
        write_json(index_path, index)
        print(f"wrote={index_path}")


if __name__ == "__main__":
    main()
