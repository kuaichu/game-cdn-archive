#!/usr/bin/env python3
"""Probe versioned NTE ResList.bin.zip entry points.

The script performs a one-byte range request and records whether the object is
available. It does not download full archives.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


URL_TEMPLATE = (
    "https://yhcdn1.wmupd.com/clientRes/publish_PC/"
    "Version/Windows/version/{version}/ResList.bin.zip"
)


def curl_headers(url: str, timeout: int) -> str:
    completed = subprocess.run(
        [
            "curl.exe" if Path("C:/Windows/System32/curl.exe").exists() else "curl",
            "-L",
            "--range",
            "0-0",
            "--max-time",
            str(timeout),
            "-o",
            "NUL" if Path("C:/Windows").exists() else "/dev/null",
            "-s",
            "-D",
            "-",
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    return completed.stdout + completed.stderr


def parse_headers(headers: str) -> dict:
    statuses = re.findall(r"HTTP/\S+\s+(\d+)", headers)
    content_range = re.search(r"Content-Range:\s*bytes\s+0-0/(\d+)", headers, re.I)
    content_length = re.search(r"Content-Length:\s*(\d+)", headers, re.I)
    last_modified = re.search(r"Last-Modified:\s*(.+)", headers, re.I)
    return {
        "status": statuses[-1] if statuses else None,
        "size": int(content_range.group(1))
        if content_range
        else (int(content_length.group(1)) if content_length else None),
        "last_modified": last_modified.group(1).strip() if last_modified else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("versions", nargs="+", help="Versions to probe, such as 1.0.0")
    parser.add_argument("--out", default="data/reslist-probe.json")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    rows = []
    for version in args.versions:
        url = URL_TEMPLATE.format(version=version)
        info = parse_headers(curl_headers(url, args.timeout))
        rows.append({"version": version, "url": url, **info})
        print(version, info["status"], info["size"], info["last_modified"])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
