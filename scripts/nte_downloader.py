#!/usr/bin/env python3
"""NTE official CDN downloader.

Flow:
  1. Fetch/probe official versioned ResList.bin.zip archives.
  2. Decode PatcherXML0 protected ResList.bin.
  3. Download CDN objects to their original file paths.
  4. Optionally pack a downloaded version directory into a ZIP archive.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from build_urls_from_reslist import DEFAULT_BASE_URL, object_url, parse_reslist
from decode_patcherxml0 import decode_patcherxml0


CONFIG_URLS = [
    "https://yhcdn1.wmupd.com/clientRes/publish_PC/Version/Windows/config.xml",
    "https://yhcdn2.wmupd.com/clientRes/publish_PC/Version/Windows/config.xml",
]
RESLIST_URL_TEMPLATE = (
    "https://yhcdn1.wmupd.com/clientRes/publish_PC/"
    "Version/Windows/version/{version}/ResList.bin.zip"
)
USER_AGENT = "nte-downloader/0.1"


def request(url: str, timeout: int = 30) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})


def fetch_bytes(url: str, timeout: int = 30, retries: int = 2) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request(url, timeout), timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}") from last_error


def probe_url(url: str, timeout: int = 10) -> dict[str, int | str | None]:
    req = request(url, timeout)
    req.add_header("Range", "bytes=0-0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            headers = dict(resp.headers.items())
            size = None
            content_range = headers.get("Content-Range", "")
            match = re.search(r"/(\d+)$", content_range)
            if match:
                size = int(match.group(1))
            return {
                "status": resp.status,
                "size": size,
                "last_modified": headers.get("Last-Modified"),
            }
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "size": None, "last_modified": exc.headers.get("Last-Modified")}
    except Exception:
        return {"status": None, "size": None, "last_modified": None}


def fetch_config(timeout: int = 30) -> tuple[str, ET.Element]:
    errors = []
    for url in CONFIG_URLS:
        try:
            data = fetch_bytes(f"{url}?tValue={int(time.time() * 1000)}", timeout=timeout)
            return url, ET.fromstring(data)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("failed to fetch config.xml\n" + "\n".join(errors))


def current_version_from_config(root: ET.Element) -> str | None:
    node = root.find(".//ResVersion")
    return node.text.strip() if node is not None and node.text else None


def version_sort_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def version_range(start: str, end: str) -> list[str]:
    start_parts = version_sort_key(start)
    end_parts = version_sort_key(end)
    if len(start_parts) != 3 or len(end_parts) != 3:
        raise ValueError("versions must look like 1.0.0")

    versions = []
    major = start_parts[0]
    if major != end_parts[0]:
        raise ValueError("cross-major ranges are not supported")
    for minor in range(start_parts[1], end_parts[1] + 1):
        patch_start = start_parts[2] if minor == start_parts[1] else 0
        patch_end = end_parts[2] if minor == end_parts[1] else 30
        for patch in range(patch_start, patch_end + 1):
            versions.append(f"{major}.{minor}.{patch}")
    return versions


def discover_versions(start: str, end: str, timeout: int) -> list[dict]:
    rows = []
    for version in version_range(start, end):
        url = RESLIST_URL_TEMPLATE.format(version=version)
        info = probe_url(url, timeout=timeout)
        row = {"version": version, "url": url, **info}
        rows.append(row)
        print(version, row["status"], row["size"])
    return rows


def load_or_fetch_reslist(version: str, cache_dir: Path, timeout: int) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive_path = cache_dir / f"{version}_ResList.bin.zip"
    if archive_path.exists() and archive_path.stat().st_size > 0:
        return archive_path

    url = RESLIST_URL_TEMPLATE.format(version=version)
    data = fetch_bytes(url, timeout=timeout, retries=2)
    archive_path.write_bytes(data)
    return archive_path


def decode_reslist_archive(version: str, archive_path: Path, work_dir: Path) -> Path:
    decoded_dir = work_dir / "decoded" / version
    decoded_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        raw = archive.read("ResList.bin")
    decoded_path = decoded_dir / "ResList.bin.decoded.xml"
    decoded_path.write_bytes(decode_patcherxml0(raw, "1289@Patcher"))
    return decoded_path


def prepare_version(version: str, work_dir: Path, timeout: int) -> dict:
    archive_path = load_or_fetch_reslist(version, work_dir / "archives", timeout)
    decoded_xml = decode_reslist_archive(version, archive_path, work_dir)
    items = parse_reslist(decoded_xml, DEFAULT_BASE_URL)

    list_dir = work_dir / "url_lists"
    list_dir.mkdir(parents=True, exist_ok=True)
    json_path = list_dir / f"{version}-full.json"
    urls_path = list_dir / f"{version}-full.urls.txt"
    json_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    urls_path.write_text("\n".join(str(item["url"]) for item in items) + "\n", encoding="utf-8")

    return {
        "version": version,
        "archive": str(archive_path),
        "decoded_xml": str(decoded_xml),
        "json": str(json_path),
        "urls": str(urls_path),
        "files": len(items),
        "bytes": sum(int(item["filesize"]) for item in items),
    }


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_one(item: dict, root_dir: Path, timeout: int, retries: int, verify: bool) -> dict:
    rel = Path(str(item["filename"]).replace("\\", "/"))
    target = root_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    expected_size = int(item["filesize"])
    expected_md5 = str(item["md5"])

    if target.exists() and target.stat().st_size == expected_size:
        if not verify or md5_file(target) == expected_md5:
            return {"filename": str(rel), "status": "exists", "bytes": expected_size}

    tmp = target.with_suffix(target.suffix + ".part")
    url = str(item["url"])
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request(url, timeout), timeout=timeout) as resp, tmp.open("wb") as out:
                shutil.copyfileobj(resp, out, length=1024 * 1024)
            if tmp.stat().st_size != expected_size:
                raise RuntimeError(f"size mismatch: {tmp.stat().st_size} != {expected_size}")
            if verify and md5_file(tmp) != expected_md5:
                raise RuntimeError("md5 mismatch")
            os.replace(tmp, target)
            return {"filename": str(rel), "status": "downloaded", "bytes": expected_size}
        except Exception as exc:
            last_error = exc
            if tmp.exists():
                tmp.unlink()
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))

    return {"filename": str(rel), "status": "failed", "error": str(last_error)}


def download_version(
    version: str,
    work_dir: Path,
    download_root: Path,
    workers: int,
    timeout: int,
    retries: int,
    verify: bool,
) -> dict:
    meta = prepare_version(version, work_dir, timeout)
    items = json.loads(Path(meta["json"]).read_text(encoding="utf-8"))
    root_dir = download_root / f"NTE_{version}_full"
    root_dir.mkdir(parents=True, exist_ok=True)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(download_one, item, root_dir, timeout, retries, verify)
            for item in items
        ]
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            result = future.result()
            results.append(result)
            print(f"[{index}/{len(items)}] {result['status']} {result['filename']}")

    summary = {
        **meta,
        "download_dir": str(root_dir),
        "downloaded": sum(1 for item in results if item["status"] in {"downloaded", "exists"}),
        "failed": [item for item in results if item["status"] == "failed"],
    }
    summary_path = work_dir / f"{version}-download-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def pack_version(version: str, download_root: Path, output: Path) -> Path:
    src_dir = download_root / f"NTE_{version}_full"
    if not src_dir.exists():
        raise FileNotFoundError(src_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path in src_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(src_dir))
    return output


def cmd_list(args: argparse.Namespace) -> None:
    url, root = fetch_config(args.timeout)
    current = current_version_from_config(root)
    print(f"config: {url}")
    print(f"current: {current}")
    end = args.end or current or "1.1.5"
    rows = discover_versions(args.start, end, args.timeout)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_prepare(args: argparse.Namespace) -> None:
    for version in args.versions:
        meta = prepare_version(version, args.work_dir, args.timeout)
        print(f"{version}: {meta['files']} files, {meta['bytes']} bytes")


def cmd_download(args: argparse.Namespace) -> None:
    for version in args.versions:
        summary = download_version(
            version,
            args.work_dir,
            args.download_root,
            args.workers,
            args.timeout,
            args.retries,
            not args.no_verify,
        )
        if summary["failed"]:
            print(f"{version}: {len(summary['failed'])} failed")
        else:
            print(f"{version}: completed")
        if args.pack and not summary["failed"]:
            output = args.pack_dir / f"NTE_{version}_full.zip"
            print(f"packing {output}")
            pack_version(version, args.download_root, output)


def cmd_pack(args: argparse.Namespace) -> None:
    for version in args.versions:
        output = args.output_dir / f"NTE_{version}_full.zip"
        print(pack_version(version, args.download_root, output))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NTE official CDN downloader")
    sub = parser.add_subparsers(required=True)

    list_parser = sub.add_parser("list", help="Fetch official config and probe versioned ResLists")
    list_parser.add_argument("--start", default="1.0.0")
    list_parser.add_argument("--end")
    list_parser.add_argument("--out", default="outputs/nte_downloader_versions.json")
    list_parser.add_argument("--timeout", type=int, default=10)
    list_parser.set_defaults(func=cmd_list)

    prepare_parser = sub.add_parser("prepare", help="Fetch/decode ResLists and generate URL indexes")
    prepare_parser.add_argument("versions", nargs="+")
    prepare_parser.add_argument("--work-dir", type=Path, default=Path("outputs/nte_downloader"))
    prepare_parser.add_argument("--timeout", type=int, default=30)
    prepare_parser.set_defaults(func=cmd_prepare)

    download_parser = sub.add_parser("download", help="Download complete files for versions")
    download_parser.add_argument("versions", nargs="+")
    download_parser.add_argument("--work-dir", type=Path, default=Path("outputs/nte_downloader"))
    download_parser.add_argument("--download-root", type=Path, default=Path("downloads"))
    download_parser.add_argument("--workers", type=int, default=4)
    download_parser.add_argument("--timeout", type=int, default=60)
    download_parser.add_argument("--retries", type=int, default=2)
    download_parser.add_argument("--no-verify", action="store_true")
    download_parser.add_argument("--pack", action="store_true")
    download_parser.add_argument("--pack-dir", type=Path, default=Path("packages"))
    download_parser.set_defaults(func=cmd_download)

    pack_parser = sub.add_parser("pack", help="Pack an already downloaded version directory")
    pack_parser.add_argument("versions", nargs="+")
    pack_parser.add_argument("--download-root", type=Path, default=Path("downloads"))
    pack_parser.add_argument("--output-dir", type=Path, default=Path("packages"))
    pack_parser.set_defaults(func=cmd_pack)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
