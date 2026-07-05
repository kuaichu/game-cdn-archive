"""NTE ResList and object availability interpretation."""

from __future__ import annotations

from scripts.availability_schema import Confidence, Interpretation, ProbeResult


def _confidence(probe: dict, fallback: Confidence) -> Confidence:
    value = str(probe.get("scheduler_confidence") or fallback).strip().lower()
    return value if value in {"high", "medium", "low"} else fallback  # type: ignore[return-value]


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_object_record(record: dict) -> bool:
    return any(key in record for key in ("filename", "object", "patch", "oldfile", "newfile"))


def _error_reason(status: int, error: str) -> tuple[str, str, str]:
    lowered = error.lower()
    if status == 404:
        return "unavailable", "http_404", "链接失效"
    if status == 403:
        return "unknown", "http_403", "状态未知"
    if 500 <= status < 600:
        return "unknown", "http_5xx", "状态未知"
    if "timeout" in lowered or "timed out" in lowered:
        return "unknown", "http_timeout", "状态未知"
    if "dns" in lowered or "name resolution" in lowered or "getaddrinfo" in lowered:
        return "unavailable", "dns_error", "链接失效"
    if "tls" in lowered or "ssl" in lowered or "certificate" in lowered:
        return "unknown", "tls_error", "状态未知"
    if status == 0:
        return "unknown", "not_probed", "状态未知"
    return "unknown", "http_5xx", "状态未知"


class NteAvailabilityAdapter:
    game = "nte"

    def interpret(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        if not probes:
            raise ValueError("NTE availability requires at least one candidate")
        if len(probes) > 1:
            raise NotImplementedError("NTE availability currently supports one URL candidate per record")

        if _is_object_record(record):
            return self._interpret_object(probes[0], record)
        return self._interpret_reslist(probes[0])

    def _interpret_reslist(self, probe_result: ProbeResult) -> Interpretation:
        probe = probe_result["probe"]
        status = _int(probe.get("status"))
        error = str(probe.get("error") or "")
        confidence = _confidence(probe, "high")

        if bool(probe.get("ok")) and 200 <= status < 300:
            return {
                "state": "available",
                "reason": "http_2xx",
                "preferred_url": probe_result["url"],
                "confidence": confidence,
                "retained": False,
                "display_label": "可用",
            }
        if bool(probe.get("ok")) and 300 <= status < 400:
            return {
                "state": "available",
                "reason": "http_3xx",
                "preferred_url": probe_result["url"],
                "confidence": confidence,
                "retained": False,
                "display_label": "可用",
            }

        state, reason, label = _error_reason(status, error)
        return {
            "state": state,  # type: ignore[typeddict-item]
            "reason": reason,  # type: ignore[typeddict-item]
            "preferred_url": "",
            "confidence": "low" if confidence == "high" and state == "unknown" else confidence,
            "retained": False,
            "display_label": label,
        }

    def _interpret_object(self, probe_result: ProbeResult, record: dict) -> Interpretation:
        probe = probe_result["probe"]
        size = _int(record.get("filesize") if "filesize" in record else probe.get("size"))
        confidence = _confidence(probe, "medium")

        if size > 0:
            return {
                "state": "available",
                "reason": "not_probed",
                "preferred_url": probe_result["url"],
                "confidence": "medium" if confidence == "high" else confidence,
                "retained": False,
                "display_label": "可用",
            }

        reason = "metadata_size_missing" if "filesize" not in record else "size_zero"
        return {
            "state": "unavailable",
            "reason": reason,
            "preferred_url": "",
            "confidence": "low",
            "retained": False,
            "display_label": "链接失效",
        }
