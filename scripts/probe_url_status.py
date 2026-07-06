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
OUTPUT_DIR = ROOT / "outputs"
STATUS_PATH = OUTPUT_DIR / "url_status.json"
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


def env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_hours(value: Any, now: datetime) -> float | None:
    parsed = parse_iso_datetime(value)
    if not parsed:
        return None
    return max((now - parsed).total_seconds() / 3600, 0)


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
        parts = path.relative_to(DATA_DIR).parts
        if len(parts) == 4 and parts[1] == "versions":
            context["game_id"] = parts[2]
            context["version"] = path.stem
            return context
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


PROBE_META_KEYS = {
    "status",
    "method",
    "final_url",
    "content_type",
    "size",
    "last_modified",
    "etag",
    "error",
    "ok",
    "checked_at",
}


def previous_checked_at(previous: dict[str, Any] | None, previous_index: dict[str, Any] | None) -> str:
    if not previous:
        return ""
    return str(previous.get("checked_at") or (previous_index or {}).get("last_checked_at") or "")


def record_with_previous_probe(
    current: dict[str, Any],
    previous: dict[str, Any],
    previous_index: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(current)
    for key in PROBE_META_KEYS:
        if key in previous:
            merged[key] = previous[key]
    if not merged.get("checked_at"):
        merged["checked_at"] = previous_checked_at(previous, previous_index)
    return merged


def due_for_probe(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    previous_index: dict[str, Any] | None,
    now: datetime,
    ttl_hours: int,
    failed_ttl_hours: int,
) -> tuple[bool, str]:
    if previous is None:
        return True, "new"
    checked_at = previous_checked_at(previous, previous_index)
    checked_age = age_hours(checked_at, now)
    if checked_age is None:
        return True, "unknown-age"
    if not previous.get("ok") and checked_age >= failed_ttl_hours:
        return True, "previously-unavailable"
    if checked_age >= ttl_hours:
        return True, "stale"
    if current.get("expected_size") and previous.get("expected_size") and current.get("expected_size") != previous.get("expected_size"):
        return True, "metadata-changed"
    return False, "fresh-cache"


def rotation_score(url: str) -> int:
    return sum((index + 1) * ord(ch) for index, ch in enumerate(url))


def select_records_to_probe(
    records: list[dict[str, Any]],
    previous_index: dict[str, Any] | None,
    now: datetime,
) -> tuple[set[str], dict[str, int]]:
    previous_by_url = {
        record.get("url"): record
        for record in (previous_index or {}).get("records", [])
        if isinstance(record, dict) and record.get("url")
    }
    ttl_hours = env_int("URL_STATUS_TTL_HOURS", 72)
    failed_ttl_hours = env_int("URL_STATUS_FAILED_TTL_HOURS", 24)
    full_interval_hours = env_int("URL_STATUS_FULL_INTERVAL_HOURS", 168)
    rotation_limit = env_int("URL_STATUS_ROTATION_LIMIT", 300)
    force_full = env_flag("URL_STATUS_FORCE_FULL", False)
    full_age = age_hours((previous_index or {}).get("last_full_probe_at") or (previous_index or {}).get("last_checked_at"), now)

    if force_full or not previous_index or full_age is None or full_age >= full_interval_hours:
        return {record["url"] for record in records}, {"full": len(records)}

    selected: set[str] = set()
    reasons: dict[str, int] = {}
    rotation_candidates: list[tuple[float, int, str]] = []
    for record in records:
        previous = previous_by_url.get(record["url"])
        should_probe, reason = due_for_probe(record, previous, previous_index, now, ttl_hours, failed_ttl_hours)
        if should_probe:
            selected.add(record["url"])
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        checked_age = age_hours(previous_checked_at(previous, previous_index), now) or 0
        rotation_candidates.append((checked_age, rotation_score(record["url"]), record["url"]))

    for _, _, url in sorted(rotation_candidates, reverse=True)[:max(rotation_limit, 0)]:
        selected.add(url)
    if rotation_limit > 0:
        reasons["rotation"] = min(rotation_limit, len(rotation_candidates))
    return selected, reasons


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
    previous = None
    if STATUS_PATH.exists():
        try:
            previous = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = None
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    selected_urls, probe_reasons = select_records_to_probe(records, previous, now_dt)
    previous_by_url = {
        record.get("url"): record
        for record in (previous or {}).get("records", [])
        if isinstance(record, dict) and record.get("url")
    }
    print(
        f"Probing {len(selected_urls)} of {total} archived URLs with {workers} workers "
        f"(reasons: {probe_reasons})"
    )

    probed_by_url: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(workers, 1)) as executor:
        future_by_url = {
            executor.submit(probe_url, record["url"], timeout): record
            for record in records
            if record["url"] in selected_urls
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
            probed_by_url[record["url"]] = {**record, **meta, "checked_at": now}

    probed: list[dict[str, Any]] = []
    for record in records:
        if record["url"] in probed_by_url:
            probed.append(probed_by_url[record["url"]])
            continue
        previous_record = previous_by_url.get(record["url"])
        if previous_record:
            probed.append(record_with_previous_probe(record, previous_record, previous or {}))
        else:
            probed.append({**record, **mark_ok({"status": 0, "error": "not probed"}), "checked_at": now})
    probed.sort(key=lambda item: item["url"])
    by_status: dict[str, int] = {}
    for record in probed:
        key = str(record.get("status") or 0)
        by_status[key] = by_status.get(key, 0) + 1

    index = {
        "source": "generated by scripts/probe_url_status.py from archived direct-download URLs",
        "last_checked_at": now,
        "last_full_probe_at": (
            now
            if len(selected_urls) == total
            else (previous or {}).get("last_full_probe_at") or (previous or {}).get("last_checked_at") or now
        ),
        "last_probe_count": len(selected_urls),
        "last_probe_reasons": probe_reasons,
        "generated_at": now,
        "total_urls": total,
        "available_urls": sum(1 for record in probed if record.get("ok")),
        "unavailable_urls": sum(1 for record in probed if not record.get("ok")),
        "by_status": dict(sorted(by_status.items(), key=lambda item: int(item[0]))),
        "records": probed,
    }
    if isinstance(previous, dict) and stable_index(previous) == stable_index(index):
        index["generated_at"] = previous.get("generated_at", now)

    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote URL status for {total} URLs: "
        f"{index['available_urls']} available, {index['unavailable_urls']} unavailable"
    )


if __name__ == "__main__":
    main()
