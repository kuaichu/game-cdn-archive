"""WuWa multi-CDN availability interpretation from existing metadata."""

from __future__ import annotations

from scripts.availability_schema import Confidence, Interpretation, ProbeResult


def _confidence(value: object, fallback: Confidence = "medium") -> Confidence:
    text = str(value or "").strip().lower()
    return text if text in {"medium", "low"} else fallback  # type: ignore[return-value]


def _int_size(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _size_present(record: dict) -> bool:
    return "size" in record and record.get("size") not in {None, ""}


def _probe_ok(probe_result: ProbeResult) -> bool:
    return bool((probe_result.get("probe") or {}).get("ok"))


def _first_valid_candidate(probes: list[ProbeResult], *, excluding: str = "") -> ProbeResult | None:
    for probe_result in probes:
        url = str(probe_result.get("url") or "")
        if url and url != excluding and _probe_ok(probe_result):
            return probe_result
    return None


def _int_count(mapping: object, key: str) -> int:
    if not isinstance(mapping, dict):
        return 0
    return _int_size(mapping.get(key))


def _is_summary(record: dict) -> bool:
    return "availability_counts" in record or "file_count" in record or "patch_routes" in record


class WuwaAvailabilityAdapter:
    game = "wuwa"

    def interpret(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        if not probes:
            raise ValueError("WuWa availability requires at least one metadata candidate")

        if _is_summary(record):
            return self._interpret_summary(probes, record)
        return self._interpret_file(probes, record)

    def _interpret_file(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        primary_url = str(record.get("url") or "")
        confidence = _confidence(probes[0]["probe"].get("scheduler_confidence"), "medium")
        primary_probe = next((probe for probe in probes if probe.get("url") == primary_url), None)

        if primary_url and primary_probe and _probe_ok(primary_probe):
            confidence = _confidence(primary_probe["probe"].get("scheduler_confidence"), confidence)
            return {
                "state": "available",
                "reason": "not_probed",
                "preferred_url": primary_url,
                "confidence": confidence,
                "retained": False,
                "display_label": "可用",
            }

        fallback_probe = _first_valid_candidate(probes, excluding=primary_url)
        if fallback_probe:
            fallback_url = str(fallback_probe.get("url") or "")
            confidence = _confidence(fallback_probe["probe"].get("scheduler_confidence"), confidence)
            return {
                "state": "available",
                "reason": "multi_cdn_preferred",
                "preferred_url": fallback_url,
                "confidence": confidence,
                "retained": False,
                "display_label": "可用",
            }

        if not _size_present(record):
            reason = "metadata_size_missing"
        elif _int_size(record.get("size")) <= 0:
            reason = "size_zero"
        else:
            reason = "not_probed"

        return {
            "state": "unavailable",
            "reason": reason,  # type: ignore[typeddict-item]
            "preferred_url": "",
            "confidence": "low",
            "retained": False,
            "display_label": "链接失效",
        }

    def _interpret_summary(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        counts = record.get("availability_counts")
        unavailable_count = _int_count(counts, "unavailable")
        unknown_count = _int_count(counts, "unknown")
        available_count = _int_count(counts, "available")
        confidence = _confidence(probes[0]["probe"].get("scheduler_confidence"), "medium")

        if unavailable_count:
            return {
                "state": "unavailable",
                "reason": "size_zero",
                "preferred_url": "",
                "confidence": "low",
                "retained": False,
                "display_label": "链接失效" if unavailable_count == 1 else f"失效 {unavailable_count}",
            }

        if unknown_count and not available_count:
            return {
                "state": "unknown",
                "reason": "not_probed",
                "preferred_url": "",
                "confidence": "low",
                "retained": False,
                "display_label": "状态未知",
            }

        if available_count:
            return {
                "state": "available",
                "reason": "not_probed",
                "preferred_url": "",
                "confidence": confidence,
                "retained": False,
                "display_label": "可用",
            }

        raise NotImplementedError("TODO(status: stubbed): WuWa summary records require availability_counts")
