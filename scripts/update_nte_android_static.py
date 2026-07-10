#!/usr/bin/env python3
"""Refresh NTE Android resource ResList indexes.

This is intentionally shaped like the legacy NTE PC catalog. Android APKs stay
in docs/data/android; this script tracks the post-install Android resources
described by PatcherSDK ResList manifests.
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from adapters.nte import NteAvailabilityAdapter  # noqa: E402
from build_urls_from_reslist import parse_patchlist, parse_reslist, write_aria2_objects, write_aria2_reslist, write_urls  # noqa: E402
from decode_patcherxml0 import decode_patcherxml0  # noqa: E402
from nte_downloader import version_range, version_sort_key  # noqa: E402
from scripts.availability_schema import ProbeResult, availability_block, probe_fact_defaults  # noqa: E402


DOCS_DATA = ROOT / "docs" / "data"
NTE_ANDROID_ROOT = DOCS_DATA / "nte" / "android"
CATALOG_PATH = NTE_ANDROID_ROOT / "catalog.json"
URL_LISTS = NTE_ANDROID_ROOT / "url_lists"

APP_ID = "1289"
KEY_SEED = f"{APP_ID}@Patcher"
IV_SEED = "PatcherSDK"
CDN_ROOT = "https://yhcdn1.wmupd.com/clientRes"
UPDATE_JSON_URL = "https://yhcdn1.wmupd.com/clientRes/publish_Updata/update.json"
GENERATED_BY = "scripts/update_nte_android_static.py"

BRANCHES: list[dict[str, Any]] = [
    {
        "branch": "publish_Android",
        "branch_kind": "legacy_android",
        "base_path": f"{CDN_ROOT}/publish_Android",
        "version_ranges": [("1.0.0", "1.0.30"), ("1.1.0", "1.1.20"), ("1.2.0", "1.2.22")],
        "note": "Original Android resource branch recovered from the 1.0 APK config.",
    },
    {
        "branch": "Android_120",
        "branch_kind": "versioncode_branch",
        "base_path": f"{CDN_ROOT}/Android_120",
        "version_ranges": [("1.2.0", "1.2.30"), ("1.3.0", "1.3.30")],
        "apk_version": "1.2.0",
        "versioncode": "120",
        "apk_url": "https://yhapk.wmupd.com/webops/yh/yh_gw_20260702.apk",
        "note": "Current Android resources branch tied to APK versioncode 120.",
    },
    {
        "branch": "Android_130",
        "branch_kind": "candidate_versioncode_branch",
        "base_path": f"{CDN_ROOT}/Android_130",
        "version_ranges": [("1.3.0", "1.3.30")],
        "versioncode": "130",
        "note": "Future sibling branch probe; kept in branch_scan even when empty.",
    },
]


def now_text() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch(url: str, timeout: int) -> tuple[int, bytes | None, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "game-cdn-archive-nte-android/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers.items())
    except urllib.error.HTTPError as exc:
        return exc.code, None, dict(exc.headers.items())
    except (TimeoutError, socket.timeout, urllib.error.URLError, OSError) as exc:
        return 0, None, {"X-Fetch-Error": str(exc)}


def branch_versions(branch: dict[str, Any]) -> list[str]:
    versions: list[str] = []
    seen: set[str] = set()
    for start, end in branch["version_ranges"]:
        for version in version_range(start, end):
            if version not in seen:
                versions.append(version)
                seen.add(version)
    return versions


def reslist_url(branch: dict[str, Any], version: str) -> str:
    return f"{branch['base_path']}/Version/Android/version/{version}/ResList.bin.zip"


def object_base_url(branch: dict[str, Any]) -> str:
    return f"{branch['base_path']}/Res"


def status_error(row: dict[str, Any]) -> str:
    status = int_value(row.get("status"))
    if row.get("error"):
        return str(row["error"])
    if status >= 400:
        return f"HTTP {status}"
    if status == 0:
        return "not_probed"
    return ""


def reslist_probe(row: dict[str, Any], checked_at: str) -> ProbeResult:
    status = int_value(row.get("status"))
    url = str(row.get("reslist_url") or "")
    ok = 200 <= status < 400
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=status,
            method="GET",
            checked_at=checked_at,
            final_url=url,
            content_type="application/zip" if ok else "",
            size=int_value(row.get("reslist_bytes") or row.get("content_length")),
            last_modified=str(row.get("last_modified") or ""),
            error=status_error(row),
            stale=False,
            scheduler_confidence="high" if status else "low",
        ),
    }


def object_probe(item: dict[str, Any], checked_at: str) -> ProbeResult:
    url = str(item.get("url") or "")
    size = int_value(item.get("filesize"))
    ok = bool(url) and size > 0
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=0,
            method="RESLIST_METADATA",
            checked_at=checked_at,
            final_url=url,
            content_type="",
            size=size,
            error="" if ok else ("metadata_size_missing" if "filesize" not in item else "size_zero"),
            stale=False,
            scheduler_confidence="medium" if ok else "low",
        ),
    }


def apply_object_availability(items: list[dict[str, Any]], checked_at: str, adapter: NteAvailabilityAdapter) -> None:
    for item in items:
        probes = [object_probe(item, checked_at)]
        item["availability"] = availability_block(
            candidates=probes,
            source_kind="metadata_inference",
            interpretation=adapter.interpret(probes, item),
            generated_by=GENERATED_BY,
        )


def state_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        state = str(((item.get("availability") or {}).get("interpretation") or {}).get("state") or "unknown")
        counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items()))


def reason_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = str(((item.get("availability") or {}).get("interpretation") or {}).get("reason") or "")
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def write_index(prefix: Path, name: str, items: list[dict[str, Any]], kind: str, download_prefix: str) -> dict[str, int | str]:
    json_path = prefix / f"{name}.json"
    urls_path = prefix / f"{name}.urls.txt"
    aria2_path = prefix / (f"{name}.files.aria2.txt" if kind == "reslist" else f"{name}.patches.aria2.txt")
    write_json(json_path, items)
    write_urls(items, urls_path)
    if kind == "reslist":
        write_aria2_reslist(items, aria2_path, f"{download_prefix}_{name.replace('-full', '')}_full")
    else:
        write_aria2_objects(items, aria2_path, f"{download_prefix}_{name.replace('-patches', '')}_patches")
    return {
        "items": len(items),
        "bytes": sum(int_value(item.get("filesize")) for item in items),
        "json": str(json_path),
        "urls": str(urls_path),
        "aria2": str(aria2_path),
    }


def normalize_paths(row: dict[str, Any]) -> dict[str, Any]:
    for section in ("full", "patches"):
        files = row.get(section)
        if not isinstance(files, dict):
            continue
        for key in ("json", "urls", "aria2"):
            if files.get(key):
                files[key] = f"data/nte/android/url_lists/{Path(str(files[key])).name}"
    row.pop("archive", None)
    return row


def process_version(branch: dict[str, Any], version: str, out_root: Path, checked_at: str, timeout: int) -> dict[str, Any]:
    adapter = NteAvailabilityAdapter()
    url = reslist_url(branch, version)
    status, body, headers = fetch(url, timeout)
    row: dict[str, Any] = {
        "version": version,
        "platform": "Android",
        "branch": branch["branch"],
        "branch_kind": branch["branch_kind"],
        "reslist_url": url,
        "object_base_url": object_base_url(branch),
        "status": status,
        "last_modified": headers.get("Last-Modified"),
        "content_length": int_value(headers.get("Content-Length")),
    }
    for key in ("apk_version", "versioncode", "apk_url"):
        if branch.get(key):
            row[key] = branch[key]
    if headers.get("X-Fetch-Error"):
        row["error"] = headers["X-Fetch-Error"]
    row["availability"] = availability_block(
        candidates=[reslist_probe(row, checked_at)],
        source_kind="live_probe",
        interpretation=adapter.interpret([reslist_probe(row, checked_at)], row),
        generated_by=GENERATED_BY,
    )
    if status != 200 or body is None:
        return row

    archive_dir = out_root / "archives"
    decoded_dir = out_root / "decoded" / branch["branch"] / version
    url_dir = out_root / "url_lists"
    for directory in (archive_dir, decoded_dir, url_dir):
        directory.mkdir(parents=True, exist_ok=True)

    archive_path = archive_dir / f"{branch['branch']}_{version}_ResList.bin.zip"
    archive_path.write_bytes(body)
    row["archive"] = str(archive_path)
    row["reslist_bytes"] = len(body)

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.namelist():
            raw = archive.read(member)
            (decoded_dir / f"{member}.decoded.xml").write_bytes(decode_patcherxml0(raw, KEY_SEED))

    res_xml = decoded_dir / "ResList.bin.decoded.xml"
    diff_xml = decoded_dir / "lastdiff.bin.decoded.xml"
    safe_name = f"{branch['branch']}-{version}"
    if res_xml.exists():
        full_items = parse_reslist(res_xml, object_base_url(branch))
        apply_object_availability(full_items, checked_at, adapter)
        row["full"] = write_index(url_dir, f"{safe_name}-full", full_items, "reslist", "NTE_Android")
    if diff_xml.exists():
        patch_items = parse_patchlist(diff_xml, object_base_url(branch))
        apply_object_availability(patch_items, checked_at, adapter)
        row["patches"] = write_index(url_dir, f"{safe_name}-patches", patch_items, "patchlist", "NTE_Android")
    row["availability"] = availability_block(
        candidates=[reslist_probe(row, checked_at)],
        source_kind="live_probe",
        interpretation=adapter.interpret([reslist_probe(row, checked_at)], row),
        generated_by=GENERATED_BY,
    )

    section_counts: dict[str, dict[str, int]] = {}
    section_reasons: dict[str, dict[str, int]] = {}
    for section in ("full", "patches"):
        link = row.get(section)
        if not isinstance(link, dict) or not link.get("json"):
            continue
        items = json.loads(Path(str(link["json"])).read_text(encoding="utf-8"))
        section_counts[section] = state_counts(items)
        section_reasons[section] = reason_counts(items)
    row["availability_counts"] = section_counts
    row["availability_reasons"] = section_reasons
    return normalize_paths(row)


def copy_url_lists(temp_root: Path) -> None:
    URL_LISTS.mkdir(parents=True, exist_ok=True)
    for path in (temp_root / "url_lists").glob("*"):
        if path.is_file():
            shutil.copy2(path, URL_LISTS / path.name)


def fetch_update_json(timeout: int) -> dict[str, Any] | None:
    status, body, _headers = fetch(f"{UPDATE_JSON_URL}?tValue={int(datetime.now().timestamp())}", timeout)
    if status != 200 or body is None:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    android_default = (((payload.get("Android") or {}).get("laohu_9") or {}).get("default") or {})
    return {
        "url": UPDATE_JSON_URL,
        "status": status,
        "android_default": android_default,
    }


def load_catalog() -> dict[str, Any]:
    if CATALOG_PATH.exists():
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {
        "game": {
            "id": "nte-android-resources",
            "name": "Neverness to Everness Android Resources",
            "zh_name": "异环 Android 资源",
            "platform": "Android",
            "app_id": APP_ID,
            "cdn_hosts": ["https://yhcdn1.wmupd.com/clientRes", "https://yhcdn2.wmupd.com/clientRes"],
        },
        "source": CDN_ROOT,
        "key_seed": KEY_SEED,
        "iv_seed": IV_SEED,
        "layout_note": "Intentional legacy NTE catalog/list shape; APK installers remain in docs/data/android.",
        "versions": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh NTE Android resource ResList archive data.")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--branches", nargs="*", help="Optional branch names to scan.")
    args = parser.parse_args()

    NTE_ANDROID_ROOT.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog()
    checked_at = now_text()
    selected = {name for name in (args.branches or [])}
    branches = [branch for branch in BRANCHES if not selected or branch["branch"] in selected]
    rows: list[dict[str, Any]] = []
    branch_scan: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="nte-android-static-") as temp:
        temp_root = Path(temp)
        for branch in branches:
            available = 0
            candidates = branch_versions(branch)
            for version in candidates:
                row = process_version(branch, version, temp_root, checked_at, args.timeout)
                if row.get("status") == 200 and row.get("full"):
                    rows.append(row)
                    available += 1
            branch_scan.append({
                "branch": branch["branch"],
                "branch_kind": branch["branch_kind"],
                "base_path": branch["base_path"],
                "candidate_versions": len(candidates),
                "available_versions": available,
                "version_ranges": branch["version_ranges"],
                "note": branch.get("note", ""),
            })
        copy_url_lists(temp_root)

    rows.sort(key=lambda row: (str(row.get("branch") or ""), version_sort_key(str(row["version"]))))
    catalog.update({
        "generated_at": checked_at,
        "last_checked_at": checked_at,
        "update_json": fetch_update_json(args.timeout),
        "branches": [{key: value for key, value in branch.items() if key != "version_ranges"} for branch in BRANCHES],
        "branch_scan": branch_scan,
        "versions": rows,
    })
    write_json(CATALOG_PATH, catalog)
    print(f"NTE Android resource versions={len(rows)}")
    for scan in branch_scan:
        print(f"{scan['branch']}={scan['available_versions']}/{scan['candidate_versions']}")


if __name__ == "__main__":
    main()
