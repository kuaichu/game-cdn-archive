"""Arknights PC availability interpretation."""

from __future__ import annotations

from scripts.availability_schema import Confidence, Interpretation, ProbeResult


class ArknightsAvailabilityAdapter:
    game = "arknights"

    def interpret(self, probes: list[ProbeResult], record: dict) -> Interpretation:
        if not probes:
            raise ValueError("Arknights availability requires at least one probe result")

        probe_result = probes[0]
        probe = probe_result["probe"]
        preferred_url = probe_result["url"] if probe.get("ok") else ""
        confidence: Confidence = probe.get("scheduler_confidence") or "low"
        status = int(probe.get("status") or 0)
        size = int(probe.get("size") or 0)
        error = str(probe.get("error") or "").lower()

        if probe.get("ok"):
            reason = "range_probe_ok" if probe.get("method") == "GET" and status == 206 else (
                "http_3xx" if 300 <= status < 400 else "http_2xx"
            )
            return {
                "state": "available",
                "reason": reason,
                "preferred_url": preferred_url,
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

        if status == 404:
            reason = "http_404"
            state = "unavailable"
            label = "链接失效"
        elif status == 403:
            reason = "http_403"
            state = "unknown"
            label = "状态未知"
        elif 500 <= status < 600:
            reason = "http_5xx"
            state = "unknown"
            label = "状态未知"
        elif size == 0 and status:
            reason = "size_zero"
            state = "unknown"
            label = "状态未知"
        elif "timeout" in error:
            reason = "http_timeout"
            state = "unknown"
            label = "状态未知"
        elif error.startswith("dns:"):
            reason = "dns_error"
            state = "unavailable"
            label = "链接失效"
        elif error.startswith("tls:"):
            reason = "tls_error"
            state = "unknown"
            label = "状态未知"
        else:
            reason = "not_probed" if status == 0 else "http_5xx"
            state = "unknown"
            label = "状态未知"

        return {
            "state": state,
            "reason": reason,
            "preferred_url": "",
            "confidence": "low" if confidence == "high" else confidence,
            "retained": False,
            "display_label": label,
        }
