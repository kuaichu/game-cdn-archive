"""Endfield availability interpretation from upstream archive metadata."""

from __future__ import annotations

from scripts.availability_schema import Confidence, Interpretation, ProbeResult


def _bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _confidence(value: object, fallback: Confidence = "medium") -> Confidence:
    text = str(value or "").strip().lower()
    return text if text in {"medium", "low"} else fallback  # type: ignore[return-value]


def _int_count(mapping: object, key: str) -> int:
    if not isinstance(mapping, dict):
        return 0
    try:
        return int(mapping.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _is_summary(record: dict) -> bool:
    return "availability_counts" in record or "package_items" in record or "patch_routes" in record


class EndfieldAvailabilityAdapter:
    game = "endfield"

    def interpret(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        if not probes:
            raise ValueError("Endfield availability requires at least one upstream archive candidate")

        if _is_summary(record):
            return self._interpret_summary(probes, record)
        return self._interpret_file(record)

    def _interpret_file(self, record: dict) -> Interpretation:
        official_available = _bool_or_none(record.get("official_available"))
        official_url = str(record.get("official_url") or "")
        mirror_url = str(record.get("mirror_url") or "")
        confidence = "medium"

        if official_available is True:
            return {
                "state": "available",
                "reason": "not_probed",
                "preferred_url": official_url,
                "confidence": confidence,
                "retained": False,
                "display_label": "可用",
            }

        if official_available is False and mirror_url:
            return {
                "state": "mirror_only",
                "reason": "mirror_fallback",
                "preferred_url": mirror_url,
                "confidence": confidence,
                "retained": False,
                "display_label": "镜像可用",
            }

        if official_available is False:
            return {
                "state": "unavailable",
                "reason": "upstream_marked_unavailable",
                "preferred_url": "",
                "confidence": confidence,
                "retained": False,
                "display_label": "链接失效",
            }

        return {
            "state": "unknown",
            "reason": "not_probed",
            "preferred_url": str(record.get("preferred_url") or official_url or mirror_url),
            "confidence": "low",
            "retained": False,
            "display_label": "状态未知",
        }

    def _interpret_summary(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        counts = record.get("availability_counts")
        unavailable_count = _int_count(counts, "unavailable")
        mirror_count = _int_count(counts, "mirror_only")
        available_count = _int_count(counts, "available")
        unknown_count = _int_count(counts, "unknown")
        confidence = _confidence(probes[0]["probe"].get("scheduler_confidence"), "medium")

        if unavailable_count:
            return {
                "state": "unavailable",
                "reason": "upstream_marked_unavailable",
                "preferred_url": "",
                "confidence": confidence,
                "retained": False,
                "display_label": "链接失效" if unavailable_count == 1 else f"失效 {unavailable_count}",
            }

        if mirror_count:
            return {
                "state": "mirror_only",
                "reason": "mirror_fallback",
                "preferred_url": "",
                "confidence": confidence,
                "retained": False,
                "display_label": "官方过期" if available_count else "镜像可用",
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

        if unknown_count:
            return {
                "state": "unknown",
                "reason": "not_probed",
                "preferred_url": "",
                "confidence": "low",
                "retained": False,
                "display_label": "状态未知",
            }

        raise NotImplementedError("TODO(status: stubbed): Endfield summary records require availability_counts")
