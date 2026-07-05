#!/usr/bin/env python3
"""Split the Wuthering Waves aggregate version archive into per-version files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WUWA_DIR = REPO_ROOT / "docs" / "data" / "wuwa"
VERSION_NAME_RE = re.compile(r"^[0-9][0-9A-Za-z_.+-]*$")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def version_filename(version: str) -> str:
    if not VERSION_NAME_RE.match(version):
        raise ValueError(f"Unsafe WuWa version name: {version!r}")
    return f"{version}.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=WUWA_DIR / "versions.json",
        help="Existing aggregate WuWa versions JSON",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=WUWA_DIR / "index.json",
        help="Existing WuWa summary index JSON; read for version order validation",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=WUWA_DIR / "versions",
        help="Directory for per-version JSON files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing shard files when content differs",
    )
    args = parser.parse_args()

    aggregate = load_json(args.source)
    index = load_json(args.index)
    summaries = index.get("versions") or []
    summary_versions = [str(item.get("version") or "") for item in summaries]
    aggregate_versions = [key for key in aggregate.keys() if isinstance(aggregate.get(key), dict)]

    missing_from_aggregate = [version for version in summary_versions if version not in aggregate]
    if missing_from_aggregate:
        raise SystemExit(
            "Refusing to split: index versions missing from aggregate: "
            + ", ".join(missing_from_aggregate)
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    unchanged = 0
    for version in aggregate_versions:
        payload = aggregate[version]
        target = args.output_dir / version_filename(version)
        content = dump_json(payload)
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if existing == content:
                unchanged += 1
                continue
            if not args.force:
                raise SystemExit(
                    f"Refusing to overwrite changed shard without --force: {target}"
                )
        target.write_text(content, encoding="utf-8")
        written += 1

    print(f"source={args.source}")
    print(f"index={args.index}")
    print(f"output_dir={args.output_dir}")
    print(f"aggregate_versions={len(aggregate_versions)}")
    print(f"index_versions={len(summary_versions)}")
    print(f"written={written}")
    print(f"unchanged={unchanged}")


if __name__ == "__main__":
    main()
