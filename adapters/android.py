"""Android APK availability interpretation."""

from __future__ import annotations

from scripts.availability_schema import Confidence, Interpretation, ProbeResult


APK_SIZE_THRESHOLD_BYTES = 1024 * 1024
TEXT_PLACEHOLDER_MAX_BYTES = 1024
APK_CONTENT_TYPES = {
    "application/vnd.android.package-archive",
    "application/octet-stream",
    "binary/octet-stream",
}
INVALID_APK_CONTENT_TYPES = {
    "text/plain",
    "text/html",
    "application/xml",
    "text/xml",
}


def _lower(value: object) -> str:
    return str(value or "").strip().lower()


def _confidence(probe: dict) -> Confidence:
    value = probe.get("scheduler_confidence") or "low"
    return value if value in {"high", "medium", "low"} else "low"  # type: ignore[return-value]


def _looks_like_apk_url(record: dict, probe_result: ProbeResult) -> bool:
    for value in (record.get("filename"), record.get("url"), probe_result.get("url"), probe_result["probe"].get("final_url")):
        if _lower(value).split("?", 1)[0].endswith(".apk"):
            return True
    return False


def _looks_like_apk_content(content_type: str) -> bool:
    lowered = content_type.split(";", 1)[0].strip().lower()
    return lowered in APK_CONTENT_TYPES


def _content_type_base(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def _is_historical_record(record: dict) -> bool:
    source = _lower(record.get("source"))
    if any(record.get(key) for key in ("archive", "archive_url", "archive_note", "preserve_same_hash")):
        return True
    if any(token in source for token in ("historical", "wayback", "archive", "recovered", "previous", "user-provided")):
        return True
    return bool(record.get("captured_at"))


def _error_reason(status: int, error: str) -> tuple[str, str]:
    if status == 404:
        return "http_404", "链接失效"
    if status == 403:
        return "http_403", "状态未知"
    if 500 <= status < 600:
        return "http_5xx", "状态未知"
    if "timeout" in error:
        return "http_timeout", "状态未知"
    if error.startswith("dns:") or "getaddrinfo" in error or "no address" in error or "could not resolve host" in error:
        return "dns_error", "状态未知"
    if error.startswith("tls:") or "certificate" in error or "ssl" in error:
        return "tls_error", "状态未知"
    if status == 0:
        return "not_probed", "状态未知"
    return "http_5xx", "状态未知"


class AndroidAvailabilityAdapter:
    game = "android"

    def interpret(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        if not probes:
            raise ValueError("Android availability requires at least one probe result")
        if len(probes) > 1:
            raise NotImplementedError("Android availability currently supports one APK URL candidate per record")

        probe_result = probes[0]
        probe = probe_result["probe"]
        status = int(probe.get("status") or 0)
        size = int(probe.get("size") or 0)
        content_type = _lower(probe.get("content_type"))
        error = _lower(probe.get("error"))
        confidence = _confidence(probe)
        apk_url = _looks_like_apk_url(record, probe_result)
        content_type_base = _content_type_base(content_type)
        apk_like = apk_url and _looks_like_apk_content(content_type)
        usable = bool(probe.get("ok")) and 200 <= status < 400 and apk_like and size > APK_SIZE_THRESHOLD_BYTES

        if usable:
            reason = "range_probe_ok" if str(probe.get("method") or "").endswith("GET") and status == 206 else (
                "http_3xx" if 300 <= status < 400 else "http_2xx"
            )
            return {
                "state": "available",
                "reason": reason,
                "preferred_url": probe_result["url"],
                "confidence": confidence,
                "retained": False,
                "display_label": "可用",
            }

        if probe.get("bot_challenge"):
            return {
                "state": "unknown",
                "reason": "bot_challenge",
                "preferred_url": "",
                "confidence": "low",
                "retained": False,
                "display_label": "状态未知",
            }

        if status == 404 and _is_historical_record(record):
            return {
                "state": "unavailable",
                "reason": "retained_historical",
                "preferred_url": "",
                "confidence": "low",
                "retained": True,
                "display_label": "链接失效",
            }

        if apk_url and status in {200, 206} and content_type_base in INVALID_APK_CONTENT_TYPES:
            state = "unavailable" if size <= TEXT_PLACEHOLDER_MAX_BYTES else "unknown"
            return {
                "state": state,
                "reason": "content_type_mismatch",
                "preferred_url": "",
                "confidence": "low" if confidence == "high" else confidence,
                "retained": False,
                "display_label": "链接失效" if state == "unavailable" else "状态未知",
            }

        if apk_url and status in {200, 206} and _looks_like_apk_content(content_type) and size <= APK_SIZE_THRESHOLD_BYTES:
            return {
                "state": "unavailable",
                "reason": "size_zero",
                "preferred_url": "",
                "confidence": "low" if confidence == "high" else confidence,
                "retained": False,
                "display_label": "链接失效",
            }

        if 200 <= status < 400:
            reason = "size_zero" if size <= APK_SIZE_THRESHOLD_BYTES else "content_type_mismatch"
            return {
                "state": "unknown",
                "reason": reason,
                "preferred_url": "",
                "confidence": "low" if confidence == "high" else confidence,
                "retained": False,
                "display_label": "状态未知",
            }

        reason, label = _error_reason(status, error)
        state = "unavailable" if reason == "http_404" else "unknown"
        return {
            "state": state,
            "reason": reason,
            "preferred_url": "",
            "confidence": "low" if confidence == "high" else confidence,
            "retained": False,
            "display_label": label,
        }
