#!/usr/bin/env python3
"""Regression tests for shared URL probe evidence selection."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import url_probe  # noqa: E402
from availability_schema import probe_fact_defaults  # noqa: E402


APK_URL = "https://cdn.example.test/game.apk"


def facts(
    *,
    status: int,
    method: str,
    content_type: str,
    size: int,
    error: str = "",
    bot_challenge: bool = False,
) -> dict:
    return probe_fact_defaults(
        ok=200 <= status < 400 and not error and not bot_challenge,
        status=status,
        method=method,
        checked_at="2026-07-10T00:00:00.000Z",
        final_url=APK_URL,
        content_type=content_type,
        size=size,
        error=error,
        bot_challenge=bot_challenge,
    )


def assert_browser_fallback_recovers_apk() -> None:
    calls: list[tuple[str, str]] = []

    def fake_request_meta(
        url: str,
        method: str,
        timeout: int,
        checked_at: str,
        headers: dict | None = None,
        method_label: str | None = None,
    ) -> dict:
        del url, timeout, checked_at
        user_agent = str((headers or {}).get("User-Agent") or "")
        calls.append((method, user_agent))
        return facts(
            status=200,
            method=method_label or method,
            content_type="text/html",
            size=29_190,
        )

    def fake_curl_request_meta(
        url: str,
        method: str,
        timeout: int,
        checked_at: str,
        headers: dict | None = None,
        method_label: str | None = None,
    ) -> dict:
        del url, timeout, checked_at
        user_agent = str((headers or {}).get("User-Agent") or "")
        calls.append((f"CURL_{method}", user_agent))
        if user_agent.startswith("Mozilla/"):
            return facts(
                status=206,
                method=method_label or f"CURL_{method}",
                content_type="application/vnd.android.package-archive",
                size=2_024_284_550,
            )
        return facts(
            status=200,
            method=method_label or f"CURL_{method}",
            content_type="text/html",
            size=29_190,
        )

    with patch.object(url_probe, "request_meta", side_effect=fake_request_meta), patch.object(
        url_probe,
        "curl_request_meta",
        side_effect=fake_curl_request_meta,
    ):
        result = url_probe.probe_one(APK_URL)

    probe = result["probe"]
    if probe["status"] != 206 or probe["content_type"] != "application/vnd.android.package-archive":
        raise AssertionError(f"browser fallback did not recover APK evidence: {result!r}")
    if not probe["ok"]:
        raise AssertionError(f"recovered APK evidence must be usable: {result!r}")
    if not any(user_agent.startswith("Mozilla/") for _, user_agent in calls):
        raise AssertionError(f"browser fallback was not attempted: {calls!r}")


def assert_apk_range_failure_overrides_head() -> None:
    def fake_request_meta(
        url: str,
        method: str,
        timeout: int,
        checked_at: str,
        headers: dict | None = None,
        method_label: str | None = None,
    ) -> dict:
        del url, timeout, checked_at, headers
        if method == "HEAD":
            return facts(
                status=200,
                method=method_label or method,
                content_type="application/vnd.android.package-archive",
                size=1_545_322_676,
            )
        return facts(
            status=403,
            method=method_label or method,
            content_type="application/xml",
            size=334,
            error="HTTP 403",
        )

    with patch.object(url_probe, "request_meta", side_effect=fake_request_meta):
        result = url_probe.probe_one(APK_URL)

    probe = result["probe"]
    if probe["status"] != 403 or probe["ok"]:
        raise AssertionError(f"APK HEAD result incorrectly overrode failed range GET: {result!r}")


def main() -> None:
    assert_browser_fallback_recovers_apk()
    assert_apk_range_failure_overrides_head()
    print("url_probe_browser_fallback=PASS")
    print("url_probe_apk_range_validation=PASS")


if __name__ == "__main__":
    main()
