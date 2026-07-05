#!/usr/bin/env python3
"""Availability probe scheduler and cache policy.

This layer owns TTL, rotation, force-full, and previous-probe reuse. It delegates
all network I/O to scripts/url_probe.py.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from availability_schema import Confidence, ProbeFacts, ProbeResult
from url_probe import probe_candidates


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_hours(value: Any, now: datetime) -> float | None:
    parsed = parse_iso_datetime(value)
    if not parsed:
        return None
    return max((now - parsed).total_seconds() / 3600, 0)


def confidence_for_age(age: float | None, ttl_hours: int, grace_hours: int) -> Confidence:
    if age is None:
        return "low"
    if age <= ttl_hours:
        return "high"
    if age <= grace_hours:
        return "medium"
    return "low"


def annotate_probe(probe: ProbeResult, now: datetime, ttl_hours: int, grace_hours: int) -> ProbeResult:
    facts = dict(probe["probe"])
    age = age_hours(facts.get("checked_at"), now)
    confidence = confidence_for_age(age, ttl_hours, grace_hours)
    facts["age_hours"] = None if age is None else round(age, 3)
    facts["scheduler_confidence"] = confidence
    facts["stale"] = confidence != "high"
    return {"url": probe["url"], "probe": facts}  # type: ignore[typeddict-item]


@dataclass(frozen=True)
class ProbeScheduleConfig:
    ttl_hours: int = 72
    failed_ttl_hours: int = 24
    grace_hours: int = 168
    rotation_limit: int = 300
    force_full: bool = False
    timeout: int = 20
    request_interval_seconds: float = 0.0

    @classmethod
    def from_env(cls) -> "ProbeScheduleConfig":
        return cls(
            ttl_hours=env_int("URL_STATUS_TTL_HOURS", 72),
            failed_ttl_hours=env_int("URL_STATUS_FAILED_TTL_HOURS", 24),
            grace_hours=env_int("URL_STATUS_GRACE_HOURS", 168),
            rotation_limit=env_int("URL_STATUS_ROTATION_LIMIT", 300),
            force_full=env_flag("URL_STATUS_FORCE_FULL", False),
            timeout=env_int("URL_STATUS_TIMEOUT", 20),
            request_interval_seconds=float(os.environ.get("URL_STATUS_REQUEST_INTERVAL_SECONDS") or 0),
        )

    @classmethod
    def android_apks_from_env(cls) -> "ProbeScheduleConfig":
        ttl_hours = env_int("ANDROID_APK_REPROBE_TTL_HOURS", 20)
        return cls(
            ttl_hours=ttl_hours,
            failed_ttl_hours=env_int("ANDROID_APK_FAILED_REPROBE_TTL_HOURS", min(ttl_hours, 24) if ttl_hours > 0 else 0),
            grace_hours=env_int("ANDROID_APK_GRACE_HOURS", max(ttl_hours * 4, 168) if ttl_hours > 0 else 168),
            rotation_limit=env_int("ANDROID_APK_ROTATION_LIMIT", 300),
            force_full=env_flag("URL_STATUS_FORCE_FULL", False),
            timeout=env_int("ANDROID_APK_PROBE_TIMEOUT", env_int("URL_STATUS_TIMEOUT", 20)),
            request_interval_seconds=float(os.environ.get("ANDROID_APK_REQUEST_INTERVAL_SECONDS") or 0),
        )

    @classmethod
    def wuwa_from_env(cls) -> "ProbeScheduleConfig":
        ttl_hours = env_int("WUWA_CDN_PROBE_TTL_HOURS", 24)
        return cls(
            ttl_hours=ttl_hours,
            failed_ttl_hours=env_int("WUWA_CDN_FAILED_REPROBE_TTL_HOURS", min(ttl_hours, 12) if ttl_hours > 0 else 0),
            grace_hours=env_int("WUWA_CDN_GRACE_HOURS", max(ttl_hours * 7, 168) if ttl_hours > 0 else 168),
            rotation_limit=env_int("WUWA_CDN_ROTATION_LIMIT", 1000),
            force_full=env_flag("WUWA_CDN_FORCE_FULL", env_flag("URL_STATUS_FORCE_FULL", False)),
            timeout=env_int("WUWA_CDN_PROBE_TIMEOUT", env_int("URL_STATUS_TIMEOUT", 12)),
            request_interval_seconds=float(os.environ.get("WUWA_CDN_REQUEST_INTERVAL_SECONDS") or 0.05),
        )


def previous_probe_by_url(records: list[dict[str, Any]]) -> dict[str, ProbeResult]:
    previous: dict[str, ProbeResult] = {}
    for record in records:
        availability = record.get("availability") if isinstance(record, dict) else None
        candidates = availability.get("candidates") if isinstance(availability, dict) else None
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict) or not candidate.get("url") or not isinstance(candidate.get("probe"), dict):
                continue
            previous[str(candidate["url"])] = {
                "url": str(candidate["url"]),
                "probe": candidate["probe"],
            }
    return previous


def should_probe_previous(previous: ProbeResult | None, now: datetime, config: ProbeScheduleConfig) -> bool:
    if config.force_full or previous is None:
        return True
    facts: ProbeFacts = previous["probe"]
    age = age_hours(facts.get("checked_at"), now)
    if age is None:
        return True
    if not facts.get("ok") and age >= config.failed_ttl_hours:
        return True
    return age >= config.ttl_hours


def rotation_score(url: str) -> int:
    return sum((index + 1) * ord(ch) for index, ch in enumerate(url))


def schedule_probe_candidates(
    urls: list[str],
    previous: dict[str, ProbeResult] | None = None,
    config: ProbeScheduleConfig | None = None,
) -> list[ProbeResult]:
    if not urls:
        raise ValueError("schedule_probe_candidates requires at least one URL candidate")
    config = config or ProbeScheduleConfig.from_env()
    previous = previous or {}
    now = datetime.now(timezone.utc)

    new_urls: set[str] = set()
    stale_candidates: list[tuple[float, int, str]] = []
    for url in urls:
        prior = previous.get(url)
        if prior is None:
            new_urls.add(url)
        if should_probe_previous(prior, now, config):
            age = age_hours(prior["probe"].get("checked_at"), now) if prior else None
            stale_candidates.append((age if age is not None else float("inf"), rotation_score(url), url))

    if config.force_full or config.rotation_limit <= 0:
        selected = {url for _, _, url in stale_candidates}
    else:
        stale_existing = [(age, score, url) for age, score, url in stale_candidates if url not in new_urls]
        remaining_slots = max(config.rotation_limit - len(new_urls), 0)
        selected = set(new_urls)
        selected.update(url for _, _, url in sorted(stale_existing, reverse=True)[:remaining_slots])

    probed_by_url: dict[str, ProbeResult] = {}
    if selected:
        for index, url in enumerate(sorted(selected)):
            if index and config.request_interval_seconds > 0:
                time.sleep(config.request_interval_seconds)
            result = probe_candidates([url], timeout=config.timeout)[0]
            probed_by_url[result["url"]] = annotate_probe(result, now, config.ttl_hours, config.grace_hours)

    results: list[ProbeResult] = []
    for url in urls:
        if url in probed_by_url:
            results.append(probed_by_url[url])
            continue
        prior = previous.get(url)
        if not prior:
            raise RuntimeError(f"no probe result produced for new URL candidate: {url}")
        results.append(annotate_probe(prior, now, config.ttl_hours, config.grace_hours))
    return results
