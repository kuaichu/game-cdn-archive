#!/usr/bin/env python3
"""Bake parallel availability records into WuWa multi-CDN metadata."""

from __future__ import annotations

import argparse
import json
import sys
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from adapters.wuwa import WuwaAvailabilityAdapter  # noqa: E402
from probe_scheduler import PersistentProbeCache, ProbeScheduleConfig  # noqa: E402
from scripts.availability_schema import ProbeResult, availability_block, probe_fact_defaults  # noqa: E402


DEFAULT_ROOT = ROOT / "docs" / "data" / "wuwa"
DEFAULT_CACHE = ROOT / ".cache" / "wuwa_probe_facts.json"
GENERATED_BY = "scripts/build_wuwa_availability.py"
STATES = ("available", "mirror_only", "unavailable", "unknown")
METADATA_METHODS = {"WUWA_METADATA", "WUWA_METADATA_SUMMARY", "WUWA_UNPROBED_CANDIDATE"}


@dataclass
class ProbeStats:
    requested: int = 0
    cache_hits: int = 0
    failed_probe_results: int = 0
    unavailable_records: int = 0
    live_records: int = 0
    metadata_records: int = 0
    preserved_records: int = 0
    started_at: float = field(default_factory=time.perf_counter)

    @property
    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.started_at


@dataclass
class PreferredUrlChange:
    version: str
    path: str
    old_url: str
    new_url: str
    reason: str
    state: str
    first_failed: str


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


def old_preferred_url(record: dict[str, Any]) -> str:
    availability = record.get("availability") if isinstance(record.get("availability"), dict) else {}
    interpretation = availability.get("interpretation") if isinstance(availability, dict) else {}
    preferred = interpretation.get("preferred_url") if isinstance(interpretation, dict) else ""
    if preferred:
        return str(preferred)
    urls = unique_candidates(record)
    return urls[0] if urls else ""


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


def unprobed_candidate(url: str, record: dict[str, Any], checked_at: str) -> ProbeResult:
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=False,
            status=0,
            method="WUWA_UNPROBED_CANDIDATE",
            checked_at=checked_at,
            final_url=url,
            content_type="",
            size=int_value(record.get("size")),
            error="not_probed",
            stale=False,
            scheduler_confidence="low",
        ),
    }


def metadata_probes_from_record(record: dict[str, Any], checked_at: str) -> list[ProbeResult]:
    urls = unique_candidates(record)
    if not urls:
        label = str(record.get("dest") or record.get("name") or "unknown").replace("\\", "/").strip("/") or "unknown"
        urls = [f"wuwa-metadata://missing/{label}"]
    return [metadata_probe(url, record, checked_at) for url in urls]


def summary_probe(version: str, checked_at: str, *, live: bool) -> ProbeResult:
    url = f"wuwa-{'live' if live else 'metadata'}://{version}"
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=live,
            status=0,
            method="WUWA_LIVE_SUMMARY" if live else "WUWA_METADATA_SUMMARY",
            checked_at=checked_at,
            final_url=url,
            content_type="",
            size=0,
            error="" if live else "not_probed",
            stale=False,
            scheduler_confidence="high" if live else "medium",
        ),
    }


def is_live_probe(probe: ProbeResult) -> bool:
    method = str((probe.get("probe") or {}).get("method") or "")
    return bool(method and method not in METADATA_METHODS and not method.startswith("WUWA_"))


def live_previous_by_url(records: Iterable[dict[str, Any]]) -> dict[str, ProbeResult]:
    previous: dict[str, ProbeResult] = {}
    for record in records:
        availability = record.get("availability") if isinstance(record, dict) else None
        candidates = availability.get("candidates") if isinstance(availability, dict) else None
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict) or not candidate.get("url") or not isinstance(candidate.get("probe"), dict):
                continue
            probe = {"url": str(candidate["url"]), "probe": candidate["probe"]}
            if is_live_probe(probe):  # type: ignore[arg-type]
                previous[str(candidate["url"])] = probe  # type: ignore[assignment]
    return previous


def cached_live_probes_from_record(
    record: dict[str, Any],
    cache: PersistentProbeCache,
    config: ProbeScheduleConfig,
    stats: ProbeStats,
) -> list[ProbeResult] | None:
    urls = unique_candidates(record)
    if not urls:
        return None

    probes: list[ProbeResult] = []
    for url in urls:
        result = cache.fresh(url, config)
        if result is None:
            return None
        stats.cache_hits += 1
        probes.append(result)
        if result["probe"].get("ok"):
            break

    stats.live_records += 1
    return probes


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


def all_items_live(items: Iterable[dict[str, Any]]) -> bool:
    seen = False
    for item in items:
        seen = True
        source = (item.get("availability") or {}).get("source") or {}
        if source.get("kind") != "live_probe":
            return False
    return seen


def all_items_have_availability(items: Iterable[dict[str, Any]]) -> bool:
    return all(isinstance(item.get("availability"), dict) for item in items)


def first_failed_probe(probes: list[ProbeResult]) -> str:
    for probe in probes:
        facts = probe.get("probe") or {}
        if not facts.get("ok") and str(facts.get("method") or "") != "WUWA_UNPROBED_CANDIDATE":
            status = facts.get("status")
            error = facts.get("error") or "probe failed"
            return f"{probe.get('url')} status={status} error={error}"
    return ""


def apply_item_availability(
    item: dict[str, Any],
    version: str,
    checked_at: str,
    adapter: WuwaAvailabilityAdapter,
    source_kind: str,
    cache: PersistentProbeCache,
    config: ProbeScheduleConfig,
    stats: ProbeStats,
    changes: list[PreferredUrlChange],
) -> None:
    old_url = old_preferred_url(item)
    if source_kind == "live_probe":
        probes = cached_live_probes_from_record(item, cache, config, stats)
        if probes is None:
            source_kind = "metadata_inference"
            probes = metadata_probes_from_record(item, checked_at)
            stats.metadata_records += 1
    else:
        probes = metadata_probes_from_record(item, checked_at)
        stats.metadata_records += 1
    interpretation = adapter.interpret(probes, item)
    if interpretation["state"] == "unavailable":
        stats.unavailable_records += 1
    item["availability"] = availability_block(
        candidates=probes,
        source_kind=source_kind,  # type: ignore[arg-type]
        interpretation=interpretation,
        generated_by=GENERATED_BY,
    )
    new_url = interpretation.get("preferred_url") or ""
    if old_url != new_url:
        changes.append(
            PreferredUrlChange(
                version=version,
                path=str(item.get("dest") or item.get("name") or ""),
                old_url=old_url,
                new_url=new_url,
                reason=str(interpretation.get("reason") or ""),
                state=str(interpretation.get("state") or ""),
                first_failed=first_failed_probe(probes),
            )
        )


def apply_items_availability(
    items: list[dict[str, Any]],
    version: str,
    checked_at: str,
    adapter: WuwaAvailabilityAdapter,
    source_kind: str,
    cache: PersistentProbeCache,
    config: ProbeScheduleConfig,
    stats: ProbeStats,
    changes: list[PreferredUrlChange],
) -> None:
    for item in items:
        apply_item_availability(item, version, checked_at, adapter, source_kind, cache, config, stats, changes)


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


def linked_lists_have_availability(root: Path, row: dict[str, Any]) -> bool:
    _path, file_items = load_list_items(root, (row.get("links") or {}).get("files"))
    if file_items and not all_items_have_availability(file_items):
        return False
    for route in row.get("patches") or []:
        if not isinstance(route, dict):
            continue
        _path, patch_items = load_list_items(root, route.get("links"))
        if patch_items and not all_items_have_availability(patch_items):
            return False
    return True


def apply_summary_availability(
    summary: dict[str, Any],
    version_row: dict[str, Any],
    counts: dict[str, int],
    reasons: dict[str, int],
    checked_at: str,
    adapter: WuwaAvailabilityAdapter,
    source_kind: str,
) -> None:
    version = str(summary.get("version") or version_row.get("version") or "unknown")
    summary["availability_counts"] = counts
    summary["availability_reasons"] = reasons
    version_row["availability_counts"] = counts
    version_row["availability_reasons"] = reasons
    summary_live = source_kind == "live_probe" and all_items_live(iter_file_items(version_row))
    probe = summary_probe(version, checked_at, live=summary_live)
    interpretation = adapter.interpret([probe], summary)
    summary["availability"] = availability_block(
        candidates=[probe],
        source_kind=("live_probe" if summary_live else "metadata_inference"),
        interpretation=interpretation,
        generated_by=GENERATED_BY,
    )


def selected_live_versions(index: dict[str, Any], *, live_probe: bool, canary_version: str, all_versions: bool) -> set[str]:
    if not live_probe:
        return set()
    summaries = [item for item in index.get("versions") or [] if isinstance(item, dict)]
    if all_versions:
        return {str(item.get("version") or "") for item in summaries if item.get("version")}
    if canary_version and canary_version != "latest":
        return {canary_version}
    latest = str((summaries[0] or {}).get("version") or "") if summaries else ""
    return {latest} if latest else set()


def apply_availability(
    root: Path,
    index: dict[str, Any],
    versions: dict[str, dict[str, Any]],
    *,
    live_versions: set[str],
    config: ProbeScheduleConfig,
    cache: PersistentProbeCache,
) -> tuple[dict[str, int], dict[str, int], dict[str, int], list[str], dict[Path, list[dict[str, Any]]], ProbeStats, list[PreferredUrlChange]]:
    adapter = WuwaAvailabilityAdapter()
    checked_at = str(index.get("last_checked_at") or index.get("generated_at") or "")
    summaries = index.get("versions") or []
    before_totals = {state: 0 for state in STATES}
    after_totals = {state: 0 for state in STATES}
    summary_totals = {state: 0 for state in STATES}
    errors: list[str] = []
    list_shards: dict[Path, list[dict[str, Any]]] = {}
    changes: list[PreferredUrlChange] = []
    stats = ProbeStats()
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
        source_kind = "live_probe" if version in live_versions else "metadata_inference"
        preserve_existing = (
            source_kind != "live_probe"
            and all_items_have_availability(items)
            and linked_lists_have_availability(root, row)
        )

        if preserve_existing:
            new_counts = count_states(items, legacy=False)
            reasons = reason_counts(items)
            summary_source_kind = "live_probe" if all_items_live(items) else "metadata_inference"
            apply_summary_availability(summary, row, new_counts, reasons, checked_at, adapter, summary_source_kind)
            stats.preserved_records += len(items)
        else:
            apply_items_availability(items, version, checked_at, adapter, source_kind, cache, config, stats, changes)
            new_counts = count_states(items, legacy=False)
            reasons = reason_counts(items)
            apply_summary_availability(summary, row, new_counts, reasons, checked_at, adapter, source_kind)
            if source_kind != "live_probe" and items:
                print(
                    f"metadata_fallback_version={version} reason=missing_existing_availability",
                    flush=True,
                )

        for state, count in legacy_counts.items():
            before_totals[state] = before_totals.get(state, 0) + count
        for state, count in new_counts.items():
            after_totals[state] = after_totals.get(state, 0) + count
        summary_state = str(((summary.get("availability") or {}).get("interpretation") or {}).get("state") or "unknown")
        summary_totals[summary_state] = summary_totals.get(summary_state, 0) + 1

        if source_kind == "metadata_inference" and legacy_counts != new_counts:
            errors.append(f"{version}:legacy_counts={legacy_counts}:new_counts={new_counts}")

        if not preserve_existing:
            path, file_items = load_list_items(root, (row.get("links") or {}).get("files"))
            if path is not None:
                apply_items_availability(file_items, version, checked_at, adapter, source_kind, cache, config, stats, changes)
                list_shards[path] = file_items
            for route in row.get("patches") or []:
                if not isinstance(route, dict):
                    continue
                path, patch_items = load_list_items(root, route.get("links"))
                if path is not None:
                    apply_items_availability(patch_items, version, checked_at, adapter, source_kind, cache, config, stats, changes)
                    list_shards[path] = patch_items

    return (
        {key: value for key, value in before_totals.items() if value},
        {key: value for key, value in after_totals.items() if value},
        {key: value for key, value in summary_totals.items() if value},
        errors,
        list_shards,
        stats,
        changes,
    )


def load_versions(root: Path) -> dict[str, dict[str, Any]]:
    versions: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "versions").glob("*.json")):
        payload = load_json(path)
        if isinstance(payload, dict):
            version = str(payload.get("version") or path.stem)
            versions[version] = payload
    return versions


def print_changes(changes: list[PreferredUrlChange]) -> None:
    print(f"preferred_url_changes={len(changes)}")
    if not changes:
        print("preferred_url_change_list=NONE")
        return
    for change in changes:
        print(
            "preferred_url_change="
            + json.dumps(
                {
                    "version": change.version,
                    "file": change.path,
                    "old_url": change.old_url,
                    "new_url": change.new_url,
                    "state": change.state,
                    "reason": change.reason,
                    "first_failed": change.first_failed,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live-probe", action="store_true", help="Probe WuWa CDN candidates for the canary version only by default.")
    parser.add_argument("--canary-version", default="latest")
    parser.add_argument("--all-versions", action="store_true", help="Probe every WuWa version. Use only after canary review.")
    parser.add_argument("--force-full-live", action="store_true", help="Ignore cached live WuWa probes for selected versions.")
    parser.add_argument("--request-interval", type=float, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args()

    index_path = args.root / "index.json"
    index = deepcopy(load_json(index_path))
    versions = deepcopy(load_versions(args.root))
    live_versions = selected_live_versions(
        index,
        live_probe=args.live_probe,
        canary_version=args.canary_version,
        all_versions=args.all_versions,
    )
    config = ProbeScheduleConfig.wuwa_from_env()
    if args.force_full_live:
        config = ProbeScheduleConfig(
            ttl_hours=config.ttl_hours,
            failed_ttl_hours=config.failed_ttl_hours,
            grace_hours=config.grace_hours,
            rotation_limit=config.rotation_limit,
            force_full=True,
            timeout=config.timeout,
            request_interval_seconds=config.request_interval_seconds,
        )
    if args.timeout is not None or args.request_interval is not None:
        config = ProbeScheduleConfig(
            ttl_hours=config.ttl_hours,
            failed_ttl_hours=config.failed_ttl_hours,
            grace_hours=config.grace_hours,
            rotation_limit=config.rotation_limit,
            force_full=config.force_full,
            timeout=args.timeout if args.timeout is not None else config.timeout,
            request_interval_seconds=args.request_interval if args.request_interval is not None else config.request_interval_seconds,
        )

    before_totals, after_totals, summary_totals, errors, list_shards, stats, changes = apply_availability(
        args.root,
        index,
        versions,
        live_versions=live_versions,
        config=config,
        cache=PersistentProbeCache(args.cache_path),
    )

    print("WuWa availability migration")
    print(f"live_probe_performed={'YES' if args.live_probe else 'NO'}")
    print(f"live_versions={','.join(sorted(live_versions)) if live_versions else 'NONE'}")
    print(f"probe_cache={args.cache_path}")
    print("build_network_io=NO")
    print(f"all_versions={'YES' if args.all_versions else 'NO'}")
    print("fallback_strategy=bounded_primary_then_ordered_backups")
    print(f"timeout_seconds={config.timeout}")
    print(f"request_interval_seconds={config.request_interval_seconds}")
    print(f"force_full_live={'YES' if config.force_full else 'NO'}")
    print("baseline=current frontend has no per-file live availability; old preferred_url is metadata primary candidate")
    print(f"versions={len(index.get('versions') or [])}")
    print(f"version_shards={len(versions)}")
    print(f"list_shards={len(list_shards)}")
    print(f"before_file_states={before_totals}")
    print(f"after_file_states={after_totals}")
    print(f"summary_contract_states={summary_totals}")
    print(f"live_records={stats.live_records}")
    print(f"metadata_records={stats.metadata_records}")
    print(f"preserved_records={stats.preserved_records}")
    print(f"request_total={stats.requested}")
    print(f"cache_hits={stats.cache_hits}")
    print(f"failed_probe_results={stats.failed_probe_results}")
    print(f"unavailable_records={stats.unavailable_records}")
    print(f"elapsed_seconds={stats.elapsed_seconds:.3f}")
    print(f"semantic_match={'PASS' if not errors else 'FAIL'}")
    print_changes(changes)
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
