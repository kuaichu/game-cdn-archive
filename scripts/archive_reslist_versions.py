#!/usr/bin/env python3
"""Fetch, decode, and index versioned NTE ResList archives."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from build_urls_from_reslist import DEFAULT_BASE_URL, parse_patchlist, parse_reslist, write_aria2_objects, write_aria2_reslist, write_urls
from decode_patcherxml0 import decode_patcherxml0


URL_TEMPLATE = (
    "https://yhcdn1.wmupd.com/clientRes/publish_PC/"
    "Version/Windows/version/{version}/ResList.bin.zip"
)


def fetch(url: str, timeout: int) -> tuple[int, bytes | None, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "nte-url-archive/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers.items())
    except urllib.error.HTTPError as exc:
        return exc.code, None, dict(exc.headers.items())


def write_index(prefix: Path, name: str, items: list[dict[str, str | int]], kind: str) -> dict[str, int | str]:
    json_path = prefix / f"{name}.json"
    urls_path = prefix / f"{name}.urls.txt"
    aria2_path = prefix / (
        f"{name}.files.aria2.txt" if kind == "reslist" else f"{name}.patches.aria2.txt"
    )

    json_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    write_urls(items, urls_path)
    if kind == "reslist":
        write_aria2_reslist(items, aria2_path, f"NTE_{name.replace('-full', '')}_full")
    else:
        write_aria2_objects(items, aria2_path, f"NTE_{name.replace('-patches', '')}_patches")

    return {
        "items": len(items),
        "bytes": sum(int(item["filesize"]) for item in items),
        "json": str(json_path),
        "urls": str(urls_path),
        "aria2": str(aria2_path),
    }


def process_version(version: str, out_root: Path, timeout: int) -> dict:
    url = URL_TEMPLATE.format(version=version)
    row: dict = {"version": version, "url": url}

    status, body, headers = fetch(url, timeout)
    row["status"] = status
    row["last_modified"] = headers.get("Last-Modified")
    row["content_length"] = int(headers.get("Content-Length", "0") or "0")
    if status != 200 or body is None:
        return row

    archive_dir = out_root / "archives"
    extracted_dir = out_root / "extracted" / version
    decoded_dir = out_root / "decoded" / version
    url_dir = out_root / "url_lists"
    for directory in [archive_dir, extracted_dir, decoded_dir, url_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    archive_path = archive_dir / f"{version}_ResList.bin.zip"
    archive_path.write_bytes(body)
    row["archive"] = str(archive_path)
    row["archive_bytes"] = len(body)

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.namelist():
            raw = archive.read(member)
            extracted = extracted_dir / member
            extracted.write_bytes(raw)
            decoded = decoded_dir / f"{member}.decoded.xml"
            decoded.write_bytes(decode_patcherxml0(raw, "1289@Patcher"))

    res_xml = decoded_dir / "ResList.bin.decoded.xml"
    diff_xml = decoded_dir / "lastdiff.bin.decoded.xml"
    if res_xml.exists():
        row["full"] = write_index(url_dir, f"{version}-full", parse_reslist(res_xml, DEFAULT_BASE_URL), "reslist")
    if diff_xml.exists():
        row["patches"] = write_index(url_dir, f"{version}-patches", parse_patchlist(diff_xml, DEFAULT_BASE_URL), "patchlist")

    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive NTE versioned ResList archives.")
    parser.add_argument("versions", nargs="+")
    parser.add_argument("--out-root", type=Path, default=Path("outputs/nte_reslists_all"))
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    args.out_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for version in args.versions:
        row = process_version(version, args.out_root, args.timeout)
        rows.append(row)
        full = row.get("full") or {}
        patches = row.get("patches") or {}
        print(
            version,
            row["status"],
            f"full={full.get('items', '-')}/{full.get('bytes', '-')}",
            f"patches={patches.get('items', '-')}/{patches.get('bytes', '-')}",
        )

    summary = args.out_root / "summary.json"
    summary.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
