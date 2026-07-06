#!/usr/bin/env python3
"""Probe WuWa CDN candidates into a persistent build-time facts cache."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_wuwa_availability import DEFAULT_CACHE, DEFAULT_ROOT, load_json, load_versions, selected_live_versions, unique_candidates  # noqa: E402
from probe_scheduler import PersistentProbeCache, ProbeScheduleConfig, schedule_probe_candidates  # noqa: E402


@dataclass
class ProbeRunStats:
    records: int = 0
    urls_seen: int = 0
    requested: int = 0
    cache_hits: int = 0
    failed_probe_results: int = 0
    remaining_records: int = 0
    started_at: float = field(default_factory=time.perf_counter)

    @property
    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.started_at


def iter_record_candidates(row: dict) -> list[list[str]]:
    records: list[list[str]] = []
    for item in row.get("files") or []:
        if isinstance(item, dict):
            records.append(unique_candidates(item))
    for route in row.get("patches") or []:
        if not isinstance(route, dict):
            continue
        for part in route.get("parts") or []:
            if isinstance(part, dict):
                records.append(unique_candidates(part))
    return records


def print_progress(label: str, stats: ProbeRunStats) -> None:
    print(
        f"progress={label} records={stats.records} probed={stats.requested} "
        f"cache_hit={stats.cache_hits} failed={stats.failed_probe_results} "
        f"remaining={stats.remaining_records} elapsed={stats.elapsed_seconds:.1f}s",
        flush=True,
    )


def probe_record(
    urls: list[str],
    cache: PersistentProbeCache,
    config: ProbeScheduleConfig,
    stats: ProbeRunStats,
    *,
    max_requests: int,
) -> bool:
    for url in urls:
        stats.urls_seen += 1
        cached = cache.fresh(url, config)
        if cached is not None:
            stats.cache_hits += 1
            if cached["probe"].get("ok"):
                return True
            continue

        if max_requests >= 0 and stats.requested >= max_requests:
            return False

        result = schedule_probe_candidates([url], previous={}, config=config)[0]
        cache.put(result)
        stats.requested += 1
        if not result["probe"].get("ok"):
            stats.failed_probe_results += 1
        if result["probe"].get("ok"):
            return True
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--canary-version", default="latest")
    parser.add_argument("--all-versions", action="store_true")
    parser.add_argument("--force-full", action="store_true")
    parser.add_argument("--request-interval", type=float, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--flush-every", type=int, default=25)
    parser.add_argument("--max-requests", type=int, default=-1, help="Stop after N new requests; useful for resume tests.")
    args = parser.parse_args()

    index = load_json(args.root / "index.json")
    versions = load_versions(args.root)
    selected_versions = selected_live_versions(
        index,
        live_probe=True,
        canary_version=args.canary_version,
        all_versions=args.all_versions,
    )

    config = ProbeScheduleConfig.wuwa_from_env()
    if args.force_full:
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

    cache = PersistentProbeCache(args.cache_path)
    records_by_version = {
        version: iter_record_candidates(row)
        for version, row in versions.items()
        if version in selected_versions
    }
    total_records = sum(len(records) for records in records_by_version.values())
    stats = ProbeRunStats(remaining_records=total_records)

    print("WuWa probe cache fill")
    print(f"selected_versions={','.join(sorted(selected_versions)) if selected_versions else 'NONE'}")
    print(f"cache_path={args.cache_path}")
    print(f"ttl_hours={config.ttl_hours}")
    print(f"timeout_seconds={config.timeout}")
    print(f"request_interval_seconds={config.request_interval_seconds}")
    print(f"force_full={'YES' if config.force_full else 'NO'}")
    print(f"total_records={total_records}")
    print(f"initial_cache_entries={len(cache.entries)}", flush=True)

    interrupted = False
    since_flush = 0
    try:
        for version in sorted(records_by_version.keys(), reverse=True):
            records = records_by_version[version]
            print(f"version_start={version} records={len(records)}", flush=True)
            for urls in records:
                if not urls:
                    stats.records += 1
                    stats.remaining_records = max(stats.remaining_records - 1, 0)
                    continue
                completed = probe_record(urls, cache, config, stats, max_requests=args.max_requests)
                since_flush += 1
                stats.records += 1
                stats.remaining_records = max(stats.remaining_records - 1, 0)
                if since_flush >= args.flush_every:
                    cache.flush()
                    since_flush = 0
                if args.progress_every > 0 and stats.records % args.progress_every == 0:
                    print_progress(version, stats)
                if not completed and args.max_requests >= 0 and stats.requested >= args.max_requests:
                    interrupted = True
                    print_progress("max_requests_reached", stats)
                    raise KeyboardInterrupt
            cache.flush()
            print_progress(f"version_done:{version}", stats)
    except KeyboardInterrupt:
        interrupted = True
        cache.flush()

    cache.flush()
    print("WuWa probe cache result")
    print(f"request_total={stats.requested}")
    print(f"cache_hits={stats.cache_hits}")
    print(f"failed_probe_results={stats.failed_probe_results}")
    print(f"remaining_records={stats.remaining_records}")
    print(f"elapsed_seconds={stats.elapsed_seconds:.3f}")
    print(f"final_cache_entries={len(cache.entries)}")
    print(f"interrupted={'YES' if interrupted else 'NO'}")
    if interrupted:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
