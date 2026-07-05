#!/usr/bin/env python3
"""Stateless URL probe primitives.

This module owns network I/O for the availability rewrite. It intentionally has
no game-specific rules and no TTL/cache scheduling.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.parser import Parser
from typing import Any

from availability_schema import ProbeFacts, ProbeResult, probe_fact_defaults


DEFAULT_HEADERS = {
    "User-Agent": "game-cdn-archive/1.0 (+https://github.com/kuaichu/game-cdn-archive)",
    "Accept": "*/*",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def url_for_request(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            urllib.parse.quote(parts.path, safe="/%"),
            urllib.parse.quote(parts.query, safe="=&%:/?+"),
            parts.fragment,
        )
    )


def header_size(headers: Any) -> int:
    value = headers.get("Content-Length") if headers else None
    try:
        return int(value or 0)
    except ValueError:
        return 0


def size_from_content_range(headers: Any) -> int:
    content_range = headers.get("Content-Range") if headers else ""
    match = re.search(r"/(\d+)$", content_range or "")
    return int(match.group(1)) if match else 0


def is_bot_challenge(status: int, content_type: str, headers_text: str = "", error: str = "") -> bool:
    text = f"{content_type}\n{headers_text}\n{error}".lower()
    if status in {403, 429, 503} and any(token in text for token in ("cloudflare", "challenge", "captcha")):
        return True
    if any(header in text for header in ("error-info", "byte-error-code", "x-exception-info")) and "challenge" in text:
        return True
    return "cf-mitigated" in text or "x-sucuri" in text


def response_meta(response: Any, method: str, checked_at: str) -> ProbeFacts:
    headers = response.headers
    status = int(response.status)
    content_type = headers.get("Content-Type", "")
    return probe_fact_defaults(
        status=status,
        method=method,
        checked_at=checked_at,
        final_url=response.geturl(),
        content_type=content_type,
        size=size_from_content_range(headers) or header_size(headers),
        last_modified=headers.get("Last-Modified", ""),
        etag=(headers.get("ETag") or "").strip('"'),
        error="",
        bot_challenge=is_bot_challenge(status, content_type, str(headers)),
    )


def http_error_meta(exc: urllib.error.HTTPError, method: str, checked_at: str) -> ProbeFacts:
    headers = exc.headers
    status = int(exc.code)
    content_type = headers.get("Content-Type", "") if headers else ""
    return probe_fact_defaults(
        status=status,
        method=method,
        checked_at=checked_at,
        final_url=exc.geturl(),
        content_type=content_type,
        size=size_from_content_range(headers) or header_size(headers),
        last_modified=headers.get("Last-Modified", "") if headers else "",
        etag=((headers.get("ETag") if headers else "") or "").strip('"'),
        error=f"HTTP {status}",
        bot_challenge=is_bot_challenge(status, content_type, str(headers) if headers else "", f"HTTP {status}"),
    )


def exception_meta(exc: Exception, method: str, checked_at: str) -> ProbeFacts:
    error = str(exc)
    lowered = error.lower()
    if "timed out" in lowered or "timeout" in lowered:
        normalized = "timeout"
    elif "certificate" in lowered or "tls" in lowered or "ssl" in lowered:
        normalized = f"tls: {error}"
    elif "name or service" in lowered or "no address" in lowered or "getaddrinfo" in lowered:
        normalized = f"dns: {error}"
    else:
        normalized = error
    return probe_fact_defaults(
        method=method,
        checked_at=checked_at,
        error=normalized,
    )


def request_meta(url: str, method: str, timeout: int, checked_at: str) -> ProbeFacts:
    headers = dict(DEFAULT_HEADERS)
    if method == "GET":
        headers["Range"] = "bytes=0-0"
    request = urllib.request.Request(url_for_request(url), headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response_meta(response, method, checked_at)
    except urllib.error.HTTPError as exc:
        return http_error_meta(exc, method, checked_at)
    except Exception as exc:
        return exception_meta(exc, method, checked_at)


def parse_curl_headers(output: str) -> tuple[int, Any, str]:
    blocks = [block for block in re.split(r"\r?\n\r?\n", output.strip()) if block.strip()]
    block = blocks[-1] if blocks else ""
    lines = block.splitlines()
    status = 0
    if lines:
        match = re.match(r"HTTP/\S+\s+(\d+)", lines[0])
        if match:
            status = int(match.group(1))
    headers = Parser().parsestr("\n".join(lines[1:]) if len(lines) > 1 else "")
    return status, headers, block


def curl_head_meta(url: str, timeout: int, checked_at: str) -> ProbeFacts:
    command = [
        "curl",
        "-I",
        "-L",
        "--max-time",
        str(timeout),
        "-A",
        DEFAULT_HEADERS["User-Agent"],
        url_for_request(url),
    ]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout + 5, check=False)
    except FileNotFoundError as exc:
        return exception_meta(exc, "CURL_HEAD", checked_at)
    except Exception as exc:
        return exception_meta(exc, "CURL_HEAD", checked_at)
    output = f"{completed.stdout}\n{completed.stderr}"
    status, headers, headers_text = parse_curl_headers(completed.stdout)
    content_type = headers.get("Content-Type", "")
    error = "" if 200 <= status < 400 else (completed.stderr.strip() or f"HTTP {status}" if status else "curl probe failed")
    return probe_fact_defaults(
        status=status,
        method="CURL_HEAD",
        checked_at=checked_at,
        final_url=headers.get("Location", "") or url,
        content_type=content_type,
        size=size_from_content_range(headers) or header_size(headers),
        last_modified=headers.get("Last-Modified", ""),
        etag=(headers.get("ETag") or "").strip('"'),
        error=error,
        bot_challenge=is_bot_challenge(status, content_type, output),
    )


def needs_range_fallback(meta: ProbeFacts) -> bool:
    status = int(meta.get("status") or 0)
    if status in {403, 405, 501}:
        return True
    if not (200 <= status < 400):
        return False
    content_type = str(meta.get("content_type") or "").lower()
    size = int(meta.get("size") or 0)
    if size <= 0:
        return True
    return "text/html" in content_type or "application/xml" in content_type


def should_try_curl(meta: ProbeFacts) -> bool:
    status = int(meta.get("status") or 0)
    if status == 0:
        return True
    if meta.get("bot_challenge"):
        return False
    if status in {403, 405, 501}:
        return True
    return False


def mark_ok(meta: ProbeFacts) -> ProbeFacts:
    status = int(meta.get("status") or 0)
    size = int(meta.get("size") or 0)
    content_type = str(meta.get("content_type") or "").lower()
    ok = not meta.get("bot_challenge") and 200 <= status < 400 and (size > 0 or "text/html" not in content_type)
    meta["ok"] = ok
    if ok:
        meta["error"] = ""
    elif not meta.get("error"):
        meta["error"] = f"HTTP {status}" if status else "probe failed"
    return meta


def probe_one(url: str, timeout: int = 20) -> ProbeResult:
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError(f"probe candidate must be an HTTP URL: {url!r}")
    checked_at = iso_now()
    meta = request_meta(url, "HEAD", timeout, checked_at)
    if needs_range_fallback(meta):
        ranged = request_meta(url, "GET", timeout, checked_at)
        if int(ranged.get("status") or 0) in {200, 206}:
            meta = ranged
    if should_try_curl(meta):
        curled = curl_head_meta(url, timeout, checked_at)
        if int(curled.get("status") or 0) >= int(meta.get("status") or 0) or not meta.get("ok"):
            meta = curled
    return {"url": url, "probe": mark_ok(meta)}


def probe_candidates(urls: list[str], timeout: int = 20) -> list[ProbeResult]:
    if not urls:
        raise ValueError("probe_candidates requires at least one URL candidate")
    return [probe_one(url, timeout=timeout) for url in urls]


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe one or more URL candidates.")
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(probe_candidates(args.urls, timeout=args.timeout), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
