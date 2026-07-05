#!/usr/bin/env python3
"""Probe archived direct-download URLs and write a health index."""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docs" / "data"
STATUS_PATH = DATA_DIR / "url_status.json"
ANDROID_LISTS_DIR = DATA_DIR / "android" / "lists"

DEFAULT_HEADERS = {
    "User-Agent": "game-cdn-archive/1.0 (+https://github.com/kuaichu/game-cdn-archive)",
    "Accept": "*/*",
}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def is_http_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def data_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def source_kind(path: Path) -> str:
    parts = path.relative_to(DATA_DIR).parts
    if not parts:
        return "unknown"
    if parts[0] == "url_lists":
        return "nte"
    return parts[0]


def infer_file_context(path: Path) -> dict[str, Any]:
    kind = source_kind(path)
    context: dict[str, Any] = {"source": kind, "file": data_path(path)}
    if kind == "hoyo":
        match = re.fullmatch(r"(.+)_versions\.json", path.name)
        if match:
            context["game_id"] = match.group(1)
    elif kind == "url_lists":
        match = re.fullmatch(r"(.+?)-(full|patches)\.json", path.name)
        context["game_id"] = "nte"
        if match:
            context["version"] = match.group(1)
            context["role"] = match.group(2)
    elif kind in {"wuwa", "arknights", "endfield"}:
        context["game_id"] = kind
    return context


def expected_size_from(item: dict[str, Any]) -> int:
    for key in ("size", "filesize", "packed_size", "uncompressed_size"):
        value = item.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return 0


def source_ref(ctx: dict[str, Any], role: str, item: dict[str, Any]) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "source": ctx.get("source"),
        "file": ctx.get("file"),
        "role": role or ctx.get("role") or "",
    }
    for key in ("game_id", "version", "channel"):
        if ctx.get(key):
            ref[key] = ctx[key]
    name = item.get("filename") or item.get("name") or item.get("dest")
    if name:
        ref["name"] = name
    expected_size = expected_size_from(item)
    if expected_size:
        ref["expected_size"] = expected_size
    return {key: value for key, value in ref.items() if value not in (None, "")}


def add_url(records: dict[str, dict[str, Any]], url: str, ref: dict[str, Any]) -> None:
    record = records.setdefault(url, {"url": url, "sources": [], "reference_count": 0})
    record["reference_count"] += 1
    source_key = json.dumps(ref, ensure_ascii=False, sort_keys=True)
    existing_keys = record.setdefault("_source_keys", set())
    if source_key not in existing_keys and len(record["sources"]) < 8:
        existing_keys.add(source_key)
        record["sources"].append(ref)
    expected_size = ref.get("expected_size")
    if isinstance(expected_size, int) and expected_size > int(record.get("expected_size") or 0):
        record["expected_size"] = expected_size


def walk_urls(value: Any, records: dict[str, dict[str, Any]], ctx: dict[str, Any], role: str = "") -> None:
    if isinstance(value, dict):
        item_ctx = dict(ctx)
        for key in ("game_id", "version", "channel"):
            if isinstance(value.get(key), str):
                item_ctx[key] = value[key]
        if isinstance(value.get("url"), str):
            item_ctx["role"] = role or item_ctx.get("role", "")
        for key, child in value.items():
            next_role = role
            if key in {"game", "voice", "update", "packages", "patches", "files", "segments", "full"}:
                next_role = f"{role}.{key}".strip(".")
            if key in {"url", "archive_url"} and is_http_url(child):
                add_url(records, child, source_ref(item_ctx, next_role or key, value))
                continue
            if key == "urls":
                continue
            walk_urls(child, records, item_ctx, next_role)
    elif isinstance(value, list):
        for child in value:
            walk_urls(child, records, ctx, role)


def collect_from_hoyo_versions(path: Path, payload: dict[str, Any], records: dict[str, dict[str, Any]]) -> None:
    base_ctx = infer_file_context(path)
    for version, row in payload.items():
        if isinstance(row, dict):
            ctx = {**base_ctx, "version": str(version)}
            walk_urls(row, records, ctx)


def collect_from_version_map(path: Path, payload: dict[str, Any], records: dict[str, dict[str, Any]]) -> None:
    base_ctx = infer_file_context(path)
    for version, row in payload.items():
        if isinstance(row, dict):
            ctx = {**base_ctx, "version": str(row.get("version") or version)}
            walk_urls(row, records, ctx)


def collect_urls() -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(DATA_DIR.rglob("*.json")):
        if path == STATUS_PATH or ANDROID_LISTS_DIR in path.parents:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"::warning::Skipping unreadable JSON {data_path(path)}: {exc}")
            continue
        kind = source_kind(path)
        if kind == "hoyo" and isinstance(payload, dict) and path.name.endswith("_versions.json"):
            collect_from_hoyo_versions(path, payload, records)
        elif kind == "wuwa" and path.name == "versions.json" and isinstance(payload, dict):
            collect_from_version_map(path, payload, records)
        else:
            walk_urls(payload, records, infer_file_context(path))

    include = os.environ.get("URL_STATUS_MATCH")
    values = [record for record in records.values() if not include or include in record["url"]]
    limit = env_int("URL_STATUS_LIMIT", 0)
    if limit > 0:
        values = values[:limit]
    for record in values:
        record.pop("_source_keys", None)
    return sorted(values, key=lambda item: item["url"])


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


def response_meta(response: Any, method: str) -> dict[str, Any]:
    headers = response.headers
    size = size_from_content_range(headers) or header_size(headers)
    return {
        "status": int(response.status),
        "method": method,
        "final_url": response.geturl(),
        "content_type": headers.get("Content-Type", ""),
        "size": size,
        "last_modified": headers.get("Last-Modified", ""),
        "etag": (headers.get("ETag") or "").strip('"'),
        "error": "",
    }


def http_error_meta(exc: urllib.error.HTTPError, method: str) -> dict[str, Any]:
    headers = exc.headers
    return {
        "status": int(exc.code),
        "method": method,
        "final_url": exc.geturl(),
        "content_type": headers.get("Content-Type", "") if headers else "",
        "size": size_from_content_range(headers) or header_size(headers),
        "last_modified": headers.get("Last-Modified", "") if headers else "",
        "etag": ((headers.get("ETag") if headers else "") or "").strip('"'),
        "error": f"HTTP {exc.code}",
    }


def request_meta(url: str, method: str, timeout: int) -> dict[str, Any]:
    headers = dict(DEFAULT_HEADERS)
    if method == "GET":
        headers["Range"] = "bytes=0-0"
    request = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response_meta(response, method)
    except urllib.error.HTTPError as exc:
        return http_error_meta(exc, method)
    except Exception as exc:
        return {
            "status": 0,
            "method": method,
            "final_url": "",
            "content_type": "",
            "size": 0,
            "last_modified": "",
            "etag": "",
            "error": str(exc),
        }


def needs_range_fallback(meta: dict[str, Any]) -> bool:
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


def mark_ok(meta: dict[str, Any]) -> dict[str, Any]:
    status = int(meta.get("status") or 0)
    size = int(meta.get("size") or 0)
    content_type = str(meta.get("content_type") or "").lower()
    ok = 200 <= status < 400 and (size > 0 or "text/html" not in content_type)
    if ok:
        meta["error"] = ""
    elif not meta.get("error"):
        meta["error"] = f"HTTP {status}" if status else "probe failed"
    meta["ok"] = ok
    return meta


def probe_url(url: str, timeout: int) -> dict[str, Any]:
    meta = request_meta(url, "HEAD", timeout)
    if needs_range_fallback(meta):
        ranged = request_meta(url, "GET", timeout)
        if int(ranged.get("status") or 0) in {200, 206}:
            meta = ranged
    return mark_ok(meta)


def stable_index(index: dict[str, Any]) -> dict[str, Any]:
    stable = deepcopy(index)
    stable.pop("generated_at", None)
    stable.pop("last_checked_at", None)
    return stable


def main() -> None:
    timeout = env_int("URL_STATUS_TIMEOUT", 20)
    workers = env_int("URL_STATUS_WORKERS", 16)
    records = collect_urls()
    total = len(records)
    print(f"Probing {total} archived URLs with {workers} workers")

    probed: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(workers, 1)) as executor:
        future_by_url = {
            executor.submit(probe_url, record["url"], timeout): record
            for record in records
        }
        for future in concurrent.futures.as_completed(future_by_url):
            record = future_by_url[future]
            try:
                meta = future.result()
            except Exception as exc:
                meta = {
                    "status": 0,
                    "method": "",
                    "final_url": "",
                    "content_type": "",
                    "size": 0,
                    "last_modified": "",
                    "etag": "",
                    "error": str(exc),
                    "ok": False,
                }
            probed.append({**record, **meta})

    probed.sort(key=lambda item: item["url"])
    by_status: dict[str, int] = {}
    for record in probed:
        key = str(record.get("status") or 0)
        by_status[key] = by_status.get(key, 0) + 1

    now = iso_now()
    index = {
        "source": "generated by scripts/probe_url_status.py from archived direct-download URLs",
        "last_checked_at": now,
        "generated_at": now,
        "total_urls": total,
        "available_urls": sum(1 for record in probed if record.get("ok")),
        "unavailable_urls": sum(1 for record in probed if not record.get("ok")),
        "by_status": dict(sorted(by_status.items(), key=lambda item: int(item[0]))),
        "records": probed,
    }
    previous = None
    if STATUS_PATH.exists():
        try:
            previous = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = None
    if isinstance(previous, dict) and stable_index(previous) == stable_index(index):
        index["generated_at"] = previous.get("generated_at", now)

    STATUS_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote URL status for {total} URLs: "
        f"{index['available_urls']} available, {index['unavailable_urls']} unavailable"
    )


if __name__ == "__main__":
    main()
