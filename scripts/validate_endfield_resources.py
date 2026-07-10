#!/usr/bin/env python3
"""Validate the generated Endfield Windows resource archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "docs" / "data" / "endfield" / "resources"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path) -> tuple[bool, str]:
    index_path = root / "index.json"
    lines = ["Endfield resource validation", f"root={root}"]
    if not index_path.exists():
        return False, "\n".join([*lines, "index_exists=FAIL", "result=FAIL"]) + "\n"

    index = load_json(index_path)
    summaries = index.get("versions") if isinstance(index, dict) else None
    errors: list[str] = []
    if not isinstance(summaries, list) or not summaries:
        errors.append("versions_missing")
        summaries = []
    if (index.get("game") or {}).get("id") != "endfield":
        errors.append("game_identity")
    if index.get("platform") != "Windows":
        errors.append("platform")

    seen_versions: set[str] = set()
    total_files = 0
    total_size = 0
    for summary in summaries:
        version = str(summary.get("version") or "")
        if not version or version in seen_versions:
            errors.append(f"duplicate_or_missing_version:{version}")
            continue
        seen_versions.add(version)
        links = summary.get("links") or {}
        expected_count = int(summary.get("file_count") or 0)
        expected_size = int(summary.get("size") or 0)
        for kind in ("json", "urls", "aria2"):
            value = str(links.get(kind) or "")
            path = ROOT / "docs" / value
            if not value or not path.exists():
                errors.append(f"{version}:missing_{kind}")
        json_path = ROOT / "docs" / str(links.get("json") or "")
        if not json_path.exists():
            continue
        row = load_json(json_path)
        records = row.get("records") if isinstance(row, dict) else None
        if row.get("version") != version or row.get("platform") != "Windows":
            errors.append(f"{version}:identity")
        if not isinstance(records, list) or not records:
            errors.append(f"{version}:records")
            continue
        actual_size = sum(int(record.get("size") or 0) for record in records)
        if len(records) != expected_count or actual_size != expected_size:
            errors.append(f"{version}:summary_count_or_size")
        if len(records) != int(row.get("file_count") or 0) or actual_size != int(row.get("size") or 0):
            errors.append(f"{version}:row_count_or_size")
        if any(not str(record.get("url") or "").startswith("https://beyond.hycdn.cn/") for record in records):
            errors.append(f"{version}:url_shape")
        urls_path = ROOT / "docs" / str(links.get("urls") or "")
        if urls_path.exists():
            url_count = len([line for line in urls_path.read_text(encoding="utf-8").splitlines() if line.strip()])
            if url_count != len(records):
                errors.append(f"{version}:urls_count")
        total_files += len(records)
        total_size += actual_size

    lines.extend([
        f"versions={len(summaries)}",
        f"total_files={total_files}",
        f"total_size={total_size}",
        "errors=" + (",".join(errors) if errors else "0"),
        "result=" + ("PASS" if not errors else "FAIL"),
    ])
    return not errors, "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    ok, text = validate(args.root)
    print(text, end="")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
