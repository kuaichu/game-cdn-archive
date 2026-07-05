#!/usr/bin/env python3
"""Validate WuWa per-version shards against the aggregate archive."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WUWA_DIR = REPO_ROOT / "docs" / "data" / "wuwa"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(data) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def choose_samples(versions: list[str]) -> list[str]:
    if len(versions) <= 3:
        return versions
    return [versions[0], versions[len(versions) // 2], versions[-1]]


def build_report(args: argparse.Namespace) -> tuple[bool, str]:
    aggregate = load_json(args.source)
    index = load_json(args.index)
    summaries = index.get("versions") or []
    summary_versions = [str(item.get("version") or "") for item in summaries]
    aggregate_versions = [key for key in aggregate.keys() if isinstance(aggregate.get(key), dict)]

    lines: list[str] = []
    ok = True

    lines.append("WuWa split validation")
    lines.append(f"source={args.source}")
    lines.append(f"index={args.index}")
    lines.append(f"shard_dir={args.shard_dir}")
    lines.append(f"aggregate_versions={len(aggregate_versions)}")
    lines.append(f"index_versions={len(summary_versions)}")

    if set(aggregate_versions) != set(summary_versions):
        ok = False
        lines.append("version_set_match=FAIL")
        lines.append(
            "missing_from_index="
            + ",".join(sorted(set(aggregate_versions) - set(summary_versions)))
        )
        lines.append(
            "missing_from_aggregate="
            + ",".join(sorted(set(summary_versions) - set(aggregate_versions)))
        )
    else:
        lines.append("version_set_match=PASS")

    reconstructed = {}
    missing_shards = []
    for version in aggregate_versions:
        shard_path = args.shard_dir / f"{version}.json"
        if not shard_path.exists():
            missing_shards.append(str(shard_path))
            continue
        reconstructed[version] = load_json(shard_path)

    if missing_shards:
        ok = False
        lines.append("all_shards_present=FAIL")
        lines.extend(f"missing_shard={path}" for path in missing_shards)
    else:
        lines.append("all_shards_present=PASS")

    if canonical(reconstructed) == canonical(aggregate):
        lines.append("canonical_reconstruction=PASS")
    else:
        ok = False
        lines.append("canonical_reconstruction=FAIL")

    file_count_mismatches = []
    patch_count_mismatches = []
    for version in aggregate_versions:
        original = aggregate.get(version) or {}
        shard = reconstructed.get(version) or {}
        original_files = len(original.get("files") or [])
        shard_files = len(shard.get("files") or [])
        if original_files != shard_files:
            file_count_mismatches.append(f"{version}:{original_files}!={shard_files}")
        original_patches = len(original.get("patches") or [])
        shard_patches = len(shard.get("patches") or [])
        if original_patches != shard_patches:
            patch_count_mismatches.append(f"{version}:{original_patches}!={shard_patches}")

    if file_count_mismatches:
        ok = False
        lines.append("file_counts=FAIL")
        lines.extend(f"file_count_mismatch={item}" for item in file_count_mismatches)
    else:
        lines.append("file_counts=PASS")

    if patch_count_mismatches:
        ok = False
        lines.append("patch_counts=FAIL")
        lines.extend(f"patch_count_mismatch={item}" for item in patch_count_mismatches)
    else:
        lines.append("patch_counts=PASS")

    sample_versions = choose_samples(summary_versions)
    lines.append("sample_versions=" + ",".join(sample_versions))
    for version in sample_versions:
        original = aggregate.get(version) or {}
        shard = reconstructed.get(version) or {}
        fields = ["version", "channel", "region", "resource_index", "base_url", "cdn_urls", "links"]
        mismatched_fields = [
            field for field in fields if canonical(original.get(field)) != canonical(shard.get(field))
        ]
        if mismatched_fields:
            ok = False
            lines.append(f"sample_field_diff[{version}]=FAIL:{','.join(mismatched_fields)}")
        else:
            lines.append(f"sample_field_diff[{version}]=PASS")

    total_files = sum(len((aggregate.get(version) or {}).get("files") or []) for version in aggregate_versions)
    total_shard_files = sum(
        len((reconstructed.get(version) or {}).get("files") or []) for version in aggregate_versions
    )
    lines.append(f"aggregate_total_files={total_files}")
    lines.append(f"shard_total_files={total_shard_files}")
    lines.append("result=" + ("PASS" if ok else "FAIL"))
    return ok, "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=WUWA_DIR / "versions.json")
    parser.add_argument("--index", type=Path, default=WUWA_DIR / "index.json")
    parser.add_argument("--shard-dir", type=Path, default=WUWA_DIR / "versions")
    parser.add_argument("--log", type=Path, default=None)
    args = parser.parse_args()

    ok, report = build_report(args)
    print(report, end="")
    if args.log:
        args.log.write_text(report, encoding="utf-8")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
