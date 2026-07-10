#!/usr/bin/env python3
"""Stateless URL probe primitives.

This module owns network I/O for the availability rewrite. It intentionally has
no game-specific rules and no TTL/cache scheduling.
"""

from __future__ import annotations

import argparse
import json
import os
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
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36",
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


def request_meta(
    url: str,
    method: str,
    timeout: int,
    checked_at: str,
    headers: dict[str, str] | None = None,
    method_label: str | None = None,
) -> ProbeFacts:
    request_headers = dict(DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)
    if method == "GET":
        request_headers["Range"] = "bytes=0-0"
    request = urllib.request.Request(url_for_request(url), headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response_meta(response, method_label or method, checked_at)
    except urllib.error.HTTPError as exc:
        return http_error_meta(exc, method_label or method, checked_at)
    except Exception as exc:
        return exception_meta(exc, method_label or method, checked_at)


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


def curl_request_meta(
    url: str,
    method: str,
    timeout: int,
    checked_at: str,
    headers: dict[str, str] | None = None,
    method_label: str | None = None,
) -> ProbeFacts:
    request_headers = dict(DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)
    command = [
        "curl",
        "-L",
        "-sS",
        "--max-time",
        str(timeout),
        "-A",
        request_headers["User-Agent"],
    ]
    for key, value in request_headers.items():
        if key.lower() != "user-agent":
            command.extend(["-H", f"{key}: {value}"])
    if method == "HEAD":
        command.append("-I")
    else:
        command.extend(["--range", "0-0", "--output", os.devnull, "--dump-header", "-"])
    command.append(url_for_request(url))
    result_method = method_label or f"CURL_{method}"
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout + 5, check=False)
    except FileNotFoundError as exc:
        return exception_meta(exc, result_method, checked_at)
    except Exception as exc:
        return exception_meta(exc, result_method, checked_at)
    output = f"{completed.stdout}\n{completed.stderr}"
    status, headers, headers_text = parse_curl_headers(completed.stdout)
    content_type = headers.get("Content-Type", "")
    error = "" if 200 <= status < 400 else (completed.stderr.strip() or f"HTTP {status}" if status else "curl probe failed")
    return probe_fact_defaults(
        status=status,
        method=result_method,
        checked_at=checked_at,
        final_url=headers.get("Location", "") or url,
        content_type=content_type,
        size=size_from_content_range(headers) or header_size(headers),
        last_modified=headers.get("Last-Modified", ""),
        etag=(headers.get("ETag") or "").strip('"'),
        error=error,
        bot_challenge=is_bot_challenge(status, content_type, output),
    )


def curl_head_meta(url: str, timeout: int, checked_at: str) -> ProbeFacts:
    return curl_request_meta(url, "HEAD", timeout, checked_at)


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


def content_type_base(meta: ProbeFacts) -> str:
    return str(meta.get("content_type") or "").split(";", 1)[0].strip().lower()


def is_apk_candidate(url: str, meta: ProbeFacts) -> bool:
    for value in (url, str(meta.get("final_url") or "")):
        path = urllib.parse.unquote(urllib.parse.urlsplit(value).path).lower()
        if path.endswith(".apk"):
            return True
    return False


def needs_browser_fallback(meta: ProbeFacts) -> bool:
    status = int(meta.get("status") or 0)
    if meta.get("bot_challenge") or status in {403, 429, 503}:
        return True
    return 200 <= status < 400 and content_type_base(meta) in {"text/html", "application/xml", "text/xml"}


def evidence_score(meta: ProbeFacts) -> int:
    status = int(meta.get("status") or 0)
    size = int(meta.get("size") or 0)
    content_type = content_type_base(meta)
    if meta.get("bot_challenge"):
        return 0
    if status in {200, 206} and content_type in {
        "application/vnd.android.package-archive",
        "application/octet-stream",
        "binary/octet-stream",
    } and size > 1024 * 1024:
        return 100
    if status in {200, 206} and content_type not in {"text/html", "application/xml", "text/xml"} and size > 0:
        return 60
    if status in {404, 410}:
        return 50
    if status in {403, 429, 503}:
        return 20
    if 200 <= status < 400:
        return 10
    return 0


def probe_profile(
    url: str,
    timeout: int,
    checked_at: str,
    headers: dict[str, str] | None = None,
    method_prefix: str = "",
) -> ProbeFacts:
    head = request_meta(
        url,
        "HEAD",
        timeout,
        checked_at,
        headers=headers,
        method_label=f"{method_prefix}HEAD" if method_prefix else "HEAD",
    )
    apk_candidate = is_apk_candidate(url, head)
    meta = head
    if apk_candidate or needs_range_fallback(head):
        ranged = request_meta(
            url,
            "GET",
            timeout,
            checked_at,
            headers=headers,
            method_label=f"{method_prefix}GET" if method_prefix else "GET",
        )
        if apk_candidate or int(ranged.get("status") or 0) in {200, 206}:
            meta = ranged
    if should_try_curl(meta) or needs_browser_fallback(meta):
        method = "GET" if apk_candidate else "HEAD"
        curled = curl_request_meta(
            url,
            method,
            timeout,
            checked_at,
            headers=headers,
            method_label=f"CURL_{method_prefix}{method}",
        )
        if evidence_score(curled) > evidence_score(meta):
            meta = curled
    return meta


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
    meta = probe_profile(url, timeout, checked_at)
    if needs_browser_fallback(meta):
        browser_meta = probe_profile(
            url,
            timeout,
            checked_at,
            headers=BROWSER_HEADERS,
            method_prefix="BROWSER_",
        )
        if evidence_score(browser_meta) > evidence_score(meta):
            meta = browser_meta
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
