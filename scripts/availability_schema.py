#!/usr/bin/env python3
"""Shared URL availability schema and vocabulary."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


SourceKind = Literal["live_probe", "upstream_archive", "metadata_inference", "manual_seed"]
Confidence = Literal["high", "medium", "low"]
AvailabilityState = Literal["available", "unavailable", "mirror_only", "unknown"]
AvailabilityReason = Literal[
    "http_2xx",
    "http_3xx",
    "http_403",
    "http_404",
    "http_5xx",
    "http_timeout",
    "dns_error",
    "tls_error",
    "range_probe_ok",
    "bot_challenge",
    "size_zero",
    "content_type_mismatch",
    "metadata_size_missing",
    "mirror_fallback",
    "multi_cdn_preferred",
    "upstream_marked_unavailable",
    "retained_historical",
    "not_probed",
]


SOURCE_KINDS = {"live_probe", "upstream_archive", "metadata_inference", "manual_seed"}
CONFIDENCES = {"high", "medium", "low"}
AVAILABILITY_STATES = {"available", "unavailable", "mirror_only", "unknown"}
AVAILABILITY_REASONS = {
    "http_2xx",
    "http_3xx",
    "http_403",
    "http_404",
    "http_5xx",
    "http_timeout",
    "dns_error",
    "tls_error",
    "range_probe_ok",
    "bot_challenge",
    "size_zero",
    "content_type_mismatch",
    "metadata_size_missing",
    "mirror_fallback",
    "multi_cdn_preferred",
    "upstream_marked_unavailable",
    "retained_historical",
    "not_probed",
}


class ProbeFacts(TypedDict):
    ok: bool
    status: int
    method: str
    checked_at: str
    final_url: str
    content_type: str
    size: int
    last_modified: str
    etag: str
    error: str
    bot_challenge: bool
    stale: bool
    age_hours: float | None
    scheduler_confidence: Confidence


class ProbeResult(TypedDict):
    url: str
    probe: ProbeFacts


class AvailabilitySource(TypedDict):
    kind: SourceKind
    confidence: Confidence


class Interpretation(TypedDict):
    state: AvailabilityState
    reason: AvailabilityReason
    preferred_url: str
    confidence: Confidence
    retained: bool
    display_label: str


class AvailabilityBlock(TypedDict):
    candidates: list[ProbeResult]
    source: AvailabilitySource
    interpretation: Interpretation
    generated_by: NotRequired[str]


def probe_fact_defaults(**overrides: Any) -> ProbeFacts:
    base: ProbeFacts = {
        "ok": False,
        "status": 0,
        "method": "",
        "checked_at": "",
        "final_url": "",
        "content_type": "",
        "size": 0,
        "last_modified": "",
        "etag": "",
        "error": "",
        "bot_challenge": False,
        "stale": False,
        "age_hours": None,
        "scheduler_confidence": "high",
    }
    base.update(overrides)
    return base


def availability_block(
    candidates: list[ProbeResult],
    source_kind: SourceKind,
    interpretation: Interpretation,
    generated_by: str,
) -> AvailabilityBlock:
    return {
        "candidates": candidates,
        "source": {
            "kind": source_kind,
            "confidence": interpretation["confidence"],
        },
        "interpretation": interpretation,
        "generated_by": generated_by,
    }
