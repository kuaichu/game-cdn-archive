#!/usr/bin/env python3
"""Fail when published docs files exceed the Cloudflare Pages size budget."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCS_DIR = ROOT / "docs"
DEFAULT_LIMIT_BYTES = 20 * 1024 * 1024


def human_bytes(value: int) -> str:
    mib = value / 1024 / 1024
    return f"{mib:.2f} MiB"


def iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in root.rglob("*") if path.is_file()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_DOCS_DIR, help="Published directory to scan.")
    parser.add_argument(
        "--limit-mib",
        type=float,
        default=20,
        help="Maximum allowed size per file, in MiB.",
    )
    args = parser.parse_args()

    scan_root = args.root if args.root.is_absolute() else ROOT / args.root
    limit_bytes = int(args.limit_mib * 1024 * 1024)
    files = iter_files(scan_root)
    if not files:
        print(f"PASS: no files found under {scan_root.relative_to(ROOT)}")
        return 0

    oversized = []
    largest = max(files, key=lambda path: path.stat().st_size)
    for path in files:
        size = path.stat().st_size
        if size > limit_bytes:
            oversized.append((path, size))

    if oversized:
        print(f"FAIL: files over {args.limit_mib:g} MiB in {scan_root.relative_to(ROOT)}:")
        for path, size in sorted(oversized, key=lambda item: item[1], reverse=True):
            print(f"  {path.relative_to(ROOT).as_posix()} {human_bytes(size)}")
        print(f"Largest file: {largest.relative_to(ROOT).as_posix()} {human_bytes(largest.stat().st_size)}")
        return 1

    print(
        f"PASS: {len(files)} files under {scan_root.relative_to(ROOT)} are <= {args.limit_mib:g} MiB; "
        f"largest {largest.relative_to(ROOT).as_posix()} {human_bytes(largest.stat().st_size)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
