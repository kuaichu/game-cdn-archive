"""HoYo package availability interpretation from source metadata."""

from __future__ import annotations

from scripts.availability_schema import Confidence, Interpretation, ProbeResult


def _confidence(value: object, fallback: Confidence = "low") -> Confidence:
    text = str(value or "").strip().lower()
    return text if text in {"medium", "low"} else fallback  # type: ignore[return-value]


def _size_present(record: dict) -> bool:
    return "size" in record and record.get("size") not in {None, ""}


def _int_size(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _int_count(mapping: object, key: str) -> int:
    if not isinstance(mapping, dict):
        return 0
    return _int_size(mapping.get(key))


def _is_summary(record: dict) -> bool:
    return any(key in record for key in ("unavailable_items", "package_items", "update_items", "has_chunk"))


def _item_reason(record: dict) -> str:
    if not _size_present(record):
        return "metadata_size_missing"
    return "size_zero"


class HoyoAvailabilityAdapter:
    game = "hoyo"

    def interpret(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        if not probes:
            raise ValueError("HoYo availability requires at least one metadata candidate")

        if _is_summary(record):
            return self._interpret_summary(probes, record)
        return self._interpret_download_item(probes, record)

    def _interpret_download_item(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        if len(probes) > 1:
            raise NotImplementedError("HoYo download item availability currently supports one metadata candidate per item")

        probe_result = probes[0]
        probe = probe_result["probe"]
        size = _int_size(record.get("size"))
        confidence = _confidence(probe.get("scheduler_confidence"), "low")

        if _size_present(record) and size > 0:
            return {
                "state": "available",
                "reason": "not_probed",
                "preferred_url": probe_result["url"],
                "confidence": confidence,
                "retained": False,
                "display_label": "可用",
            }

        return {
            "state": "unavailable",
            "reason": _item_reason(record),
            "preferred_url": "",
            "confidence": "low",
            "retained": False,
            "display_label": "链接失效",
        }

    def _interpret_summary(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        counts = record.get("availability_counts")
        reasons = record.get("availability_reasons")
        unavailable_count = _int_count(counts, "unavailable")
        unknown_count = _int_count(counts, "unknown")
        available_count = _int_count(counts, "available")

        if unavailable_count:
            reason = "metadata_size_missing" if _int_count(reasons, "metadata_size_missing") else "size_zero"
            return {
                "state": "unavailable",
                "reason": reason,
                "preferred_url": "",
                "confidence": "low",
                "retained": False,
                "display_label": "链接失效" if unavailable_count == 1 else f"含失效 {unavailable_count}",
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

        first_url = probes[0]["url"] if probes else ""
        return {
            "state": "available",
            "reason": "not_probed",
            "preferred_url": first_url,
            "confidence": "medium",
            "retained": False,
            "display_label": "可用",
        }
