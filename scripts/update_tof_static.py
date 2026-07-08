#!/usr/bin/env python3
"""Refresh Tower of Fantasy static ResList indexes."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_urls_from_reslist import parse_patchlist, parse_reslist, write_aria2_objects, write_aria2_reslist, write_urls
from decode_patcherxml0 import decode_patcherxml0


ROOT = Path(__file__).resolve().parents[1]
DOCS_DATA = ROOT / "docs" / "data"
TOF_ROOT = DOCS_DATA / "tof"
CATALOG_PATH = TOF_ROOT / "catalog.json"
URL_LISTS = TOF_ROOT / "url_lists"

APP_ID = "1256"
KEY_SEED = f"{APP_ID}@Patcher"
BASE_PATH = "https://htcdn1.wmupd.com/clientRes/Windows55"
BASE_URL = f"{BASE_PATH}/Res"
CONFIG_URLS = [
    f"{BASE_PATH}/Version/Windows/config.xml",
    "https://htcdn2.wmupd.com/clientRes/Windows55/Version/Windows/config.xml",
]
URL_TEMPLATES = [
    f"{BASE_PATH}/Version/Windows/version/{{version}}/ResList.bin.zip",
    "https://htcdn2.wmupd.com/clientRes/Windows55/Version/Windows/version/{version}/ResList.bin.zip",
]


def fetch(url: str, timeout: int) -> tuple[int, bytes | None, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "game-cdn-archive-tof/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers.items())
    except urllib.error.HTTPError as exc:
        return exc.code, None, dict(exc.headers.items())
    except (TimeoutError, socket.timeout, urllib.error.URLError, OSError) as exc:
        return 0, None, {"X-Fetch-Error": str(exc)}


def fetch_first(urls: list[str], timeout: int) -> tuple[str, int, bytes | None, dict[str, str]]:
    fallback: tuple[str, int, bytes | None, dict[str, str]] | None = None
    errors: list[str] = []
    for url in urls:
        status, body, headers = fetch(url, timeout)
        if status == 200 and body is not None:
            return url, status, body, headers
        if status == 0:
            errors.append(f"{url}: {headers.get('X-Fetch-Error', 'unknown network error')}")
            continue
        if fallback is None:
            fallback = (url, status, body, headers)
    if fallback:
        return fallback
    return urls[0], 0, None, {"X-Fetch-Error": "; ".join(errors) or "all Tower of Fantasy endpoints failed"}


def current_version_from_config(timeout: int) -> tuple[str, dict[str, Any]]:
    url, status, body, headers = fetch_first(CONFIG_URLS, timeout)
    if status != 200 or body is None:
        raise RuntimeError(f"could not fetch Tower of Fantasy config.xml from {url}: {status}")
    root = ET.fromstring(body)
    version = (root.findtext(".//ResVersion") or "").strip()
    if not version:
        raise RuntimeError("Tower of Fantasy config.xml did not contain ResVersion")
    return version, {
        "url": url,
        "status": status,
        "last_modified": headers.get("Last-Modified"),
        "content_length": int(headers.get("Content-Length", "0") or "0"),
        "res_version": version,
        "section": (root.findtext(".//Section") or "").strip(),
        "res_size": int((root.findtext(".//ResSize") or "0").strip() or "0"),
        "hash": (root.findtext(".//Hash") or "").strip(),
        "diff_hash": (root.findtext(".//diffHash") or "").strip(),
        "list_hash": (root.findtext(".//listHash") or "").strip(),
        "compressed": (root.findtext(".//Compressed") or "").strip(),
        "encrypt": (root.findtext(".//Encrypt") or "").strip(),
    }


def write_index(prefix: Path, name: str, items: list[dict[str, str | int]], kind: str) -> dict[str, int | str]:
    json_path = prefix / f"{name}.json"
    urls_path = prefix / f"{name}.urls.txt"
    aria2_path = prefix / (
        f"{name}.files.aria2.txt" if kind == "reslist" else f"{name}.patches.aria2.txt"
    )

    json_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    write_urls(items, urls_path)
    if kind == "reslist":
        write_aria2_reslist(items, aria2_path, f"TOF_{name.replace('-full', '')}_full")
    else:
        write_aria2_objects(items, aria2_path, f"TOF_{name.replace('-patches', '')}_patches")

    return {
        "items": len(items),
        "bytes": sum(int(item["filesize"]) for item in items),
        "json": str(json_path),
        "urls": str(urls_path),
        "aria2": str(aria2_path),
    }


def fetch_reslist(version: str, timeout: int) -> tuple[str, int, bytes | None, dict[str, str]]:
    return fetch_first([template.format(version=version) for template in URL_TEMPLATES], timeout)


def process_version(version: str, out_root: Path, timeout: int) -> dict[str, Any]:
    url, status, body, headers = fetch_reslist(version, timeout)
    row: dict[str, Any] = {"version": version, "url": url, "status": status}
    row["last_modified"] = headers.get("Last-Modified")
    row["content_length"] = int(headers.get("Content-Length", "0") or "0")
    if headers.get("X-Fetch-Error"):
        row["error"] = headers["X-Fetch-Error"]
    if status != 200 or body is None:
        return row

    archive_dir = out_root / "archives"
    extracted_dir = out_root / "extracted" / version
    decoded_dir = out_root / "decoded" / version
    url_dir = out_root / "url_lists"
    for directory in (archive_dir, extracted_dir, decoded_dir, url_dir):
        directory.mkdir(parents=True, exist_ok=True)

    archive_path = archive_dir / f"{version}_ResList.bin.zip"
    archive_path.write_bytes(body)
    row["archive"] = str(archive_path)
    row["archive_bytes"] = len(body)

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.namelist():
            raw = archive.read(member)
            (extracted_dir / member).write_bytes(raw)
            (decoded_dir / f"{member}.decoded.xml").write_bytes(decode_patcherxml0(raw, KEY_SEED))

    res_xml = decoded_dir / "ResList.bin.decoded.xml"
    diff_xml = decoded_dir / "lastdiff.bin.decoded.xml"
    if res_xml.exists():
        row["full"] = write_index(url_dir, f"{version}-full", parse_reslist(res_xml, BASE_URL), "reslist")
    if diff_xml.exists():
        row["patches"] = write_index(url_dir, f"{version}-patches", parse_patchlist(diff_xml, BASE_URL), "patchlist")
    return row


def normalize_paths(row: dict[str, Any]) -> dict[str, Any]:
    for section in ("full", "patches"):
        files = row.get(section)
        if not isinstance(files, dict):
            continue
        for key in ("json", "urls", "aria2"):
            if files.get(key):
                files[key] = f"data/tof/url_lists/{Path(str(files[key])).name}"
    if row.get("url"):
        row["reslist_url"] = row.pop("url")
    if row.get("archive_bytes") is not None:
        row["reslist_bytes"] = row.pop("archive_bytes")
    row.pop("archive", None)
    return row


def load_catalog() -> dict[str, Any]:
    if CATALOG_PATH.exists():
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {
        "game": {
            "id": "tof",
            "name": "幻塔",
            "subName": "Tower of Fantasy",
            "shortName": "TOF",
            "icon": "assets/icons/tof.svg",
            "kind": "tof",
        },
        "source": "https://htcdn1.wmupd.com/clientRes/Windows55/",
        "config_urls": CONFIG_URLS,
        "reslist_url_template": URL_TEMPLATES[0],
        "object_base_url": BASE_URL,
        "key_seed": KEY_SEED,
        "iv_seed": "PatcherSDK",
        "versions": [],
    }


def copy_url_lists(temp_root: Path) -> None:
    URL_LISTS.mkdir(parents=True, exist_ok=True)
    for path in (temp_root / "url_lists").glob("*"):
        if path.is_file():
            shutil.copy2(path, URL_LISTS / path.name)


def existing_files_present(row: dict[str, Any]) -> bool:
    for section in ("full", "patches"):
        files = row.get(section)
        if not isinstance(files, dict):
            continue
        for key in ("json", "urls", "aria2"):
            value = files.get(key)
            if value and not (DOCS_DATA / Path(str(value)).relative_to("data")).exists():
                return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh Tower of Fantasy ResList archive data.")
    parser.add_argument("--versions", nargs="*", help="Specific versions to refresh. Defaults to current config ResVersion.")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    TOF_ROOT.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog()
    checked_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    current, config = current_version_from_config(args.timeout)
    versions = args.versions or [current]
    existing = {row["version"]: row for row in catalog.get("versions", []) if isinstance(row, dict) and row.get("version")}
    rows = [row for row in catalog.get("versions", []) if isinstance(row, dict) and row.get("version") not in set(versions)]

    with tempfile.TemporaryDirectory(prefix="tof-static-") as temp:
        temp_root = Path(temp)
        for version in versions:
            old = existing.get(version)
            if old and old.get("status") == 200 and existing_files_present(old):
                rows.append(old)
                continue
            row = normalize_paths(process_version(version, temp_root, args.timeout))
            if row.get("status") == 0 and old:
                print(
                    f"::warning::Reusing cached Tower of Fantasy {version} metadata after transient "
                    f"ResList fetch failure: {row.get('error') or 'unknown network error'}"
                )
                rows.append(old)
                continue
            if row.get("status") == 0:
                raise RuntimeError(
                    f"could not fetch uncached Tower of Fantasy ResList for {version}: "
                    f"{row.get('error') or 'unknown network error'}"
                )
            rows.append(row)
        copy_url_lists(temp_root)

    rows.sort(key=lambda row: tuple(int(part) for part in str(row["version"]).split(".") if part.isdigit()))
    catalog.update({
        "last_checked_at": checked_at,
        "generated_at": checked_at,
        "current_version": current,
        "config": config,
        "versions": rows,
    })
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok_count = sum(1 for row in rows if row.get("status") == 200)
    print(f"Tower of Fantasy current={current}, versions={len(rows)}, available={ok_count}")


if __name__ == "__main__":
    main()
