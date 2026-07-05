#!/usr/bin/env python3
"""Validate WuWa per-version shards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WUWA_DIR = REPO_ROOT / "docs" / "data" / "wuwa"
EXPECTED_TOTAL_FILES = 24865
REQUIRED_VERSION_FIELDS = ("version", "channel", "region", "release_date", "files", "patches")
REQUIRED_FILE_FIELDS = ("dest", "md5", "size", "url")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(data) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def choose_samples(versions: list[str]) -> list[str]:
    if len(versions) <= 3:
        return versions
    return [versions[0], versions[len(versions) // 2], versions[-1]]


def is_present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return True


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_aggregate_report(args: argparse.Namespace) -> tuple[bool, str]:
    aggregate = load_json(args.source)
    index = load_json(args.index)
    summaries = index.get("versions") or []
    summary_versions = [str(item.get("version") or "") for item in summaries]
    aggregate_versions = [key for key in aggregate.keys() if isinstance(aggregate.get(key), dict)]

    lines: list[str] = []
    ok = True

    lines.append("WuWa split validation")
    lines.append("mode=aggregate")
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


def build_self_report(args: argparse.Namespace) -> tuple[bool, str]:
    index = load_json(args.index)
    summaries = index.get("versions") or []
    summary_versions = [str(item.get("version") or "") for item in summaries]
    summary_by_version = {str(item.get("version") or ""): item for item in summaries}
    shard_paths = sorted(args.shard_dir.glob("*.json"))
    shard_versions = [path.stem for path in shard_paths]

    lines: list[str] = []
    ok = True
    total_files = 0

    lines.append("WuWa split validation")
    lines.append("mode=self")
    lines.append(f"index={args.index}")
    lines.append(f"shard_dir={args.shard_dir}")
    lines.append(f"expected_total_files={args.expected_total_files}")
    lines.append(f"index_versions={len(summary_versions)}")
    lines.append(f"shard_versions={len(shard_versions)}")

    duplicate_versions = sorted(
        {version for version in summary_versions if summary_versions.count(version) > 1}
    )
    if duplicate_versions:
        ok = False
        lines.append("index_duplicate_versions=FAIL")
        lines.append("duplicate_versions=" + ",".join(duplicate_versions))
    else:
        lines.append("index_duplicate_versions=PASS")

    missing_shards = sorted(set(summary_versions) - set(shard_versions))
    extra_shards = sorted(set(shard_versions) - set(summary_versions))
    if missing_shards:
        ok = False
        lines.append("all_index_shards_present=FAIL")
        lines.append("missing_shards=" + ",".join(missing_shards))
    else:
        lines.append("all_index_shards_present=PASS")
    if extra_shards:
        ok = False
        lines.append("no_unindexed_shards=FAIL")
        lines.append("extra_shards=" + ",".join(extra_shards))
    else:
        lines.append("no_unindexed_shards=PASS")

    field_errors: list[str] = []
    file_errors: list[str] = []
    count_errors: list[str] = []
    patch_count_errors: list[str] = []

    for version in summary_versions:
        shard_path = args.shard_dir / f"{version}.json"
        if not shard_path.exists():
            continue
        shard = load_json(shard_path)
        summary = summary_by_version.get(version) or {}
        if not is_present(summary.get("release_date")):
            field_errors.append(f"{version}:summary.release_date")

        if shard.get("version") != version:
            field_errors.append(f"{version}:version_mismatch:{shard.get('version')}")

        for field in REQUIRED_VERSION_FIELDS:
            if field == "patches":
                if field not in shard or not isinstance(shard.get(field), list):
                    field_errors.append(f"{version}:{field}")
                continue
            if not is_present(shard.get(field)):
                field_errors.append(f"{version}:{field}")

        files = shard.get("files")
        if not isinstance(files, list) or not files:
            field_errors.append(f"{version}:files")
            continue

        total_files += len(files)
        expected_file_count = summary.get("file_count", shard.get("file_count"))
        expected_file_count = as_int(expected_file_count)
        if expected_file_count is not None and expected_file_count != len(files):
            count_errors.append(f"{version}:{expected_file_count}!={len(files)}")

        patches = shard.get("patches") if isinstance(shard.get("patches"), list) else []
        expected_patch_count = summary.get("patch_routes")
        expected_patch_count = as_int(expected_patch_count)
        if expected_patch_count is not None and expected_patch_count != len(patches):
            patch_count_errors.append(f"{version}:{expected_patch_count}!={len(patches)}")

        for index, entry in enumerate(files):
            if not isinstance(entry, dict):
                file_errors.append(f"{version}:{index}:not_object")
                continue
            missing_fields = [
                field for field in REQUIRED_FILE_FIELDS if not is_present(entry.get(field))
            ]
            if missing_fields:
                file_errors.append(f"{version}:{index}:{','.join(missing_fields)}")

    if field_errors:
        ok = False
        lines.append("version_fields=FAIL")
        lines.extend(f"version_field_error={item}" for item in field_errors)
    else:
        lines.append("version_fields=PASS")

    if count_errors:
        ok = False
        lines.append("file_counts=FAIL")
        lines.extend(f"file_count_mismatch={item}" for item in count_errors)
    else:
        lines.append("file_counts=PASS")

    if patch_count_errors:
        ok = False
        lines.append("patch_counts=FAIL")
        lines.extend(f"patch_count_mismatch={item}" for item in patch_count_errors)
    else:
        lines.append("patch_counts=PASS")

    if file_errors:
        ok = False
        lines.append("file_required_fields=FAIL")
        lines.extend(f"file_required_field_error={item}" for item in file_errors[:50])
        if len(file_errors) > 50:
            lines.append(f"file_required_field_error_omitted={len(file_errors) - 50}")
    else:
        lines.append("file_required_fields=PASS")

    lines.append(f"total_files={total_files}")
    if total_files == args.expected_total_files:
        lines.append("expected_total_files_match=PASS")
    else:
        ok = False
        lines.append("expected_total_files_match=FAIL")

    lines.append("result=" + ("PASS" if ok else "FAIL"))
    return ok, "\n".join(lines) + "\n"


def build_report(args: argparse.Namespace) -> tuple[bool, str]:
    if args.mode == "aggregate":
        return build_aggregate_report(args)
    if args.mode == "self":
        return build_self_report(args)
    if args.source.exists():
        return build_aggregate_report(args)
    return build_self_report(args)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=WUWA_DIR / "versions.json")
    parser.add_argument("--index", type=Path, default=WUWA_DIR / "index.json")
    parser.add_argument("--shard-dir", type=Path, default=WUWA_DIR / "versions")
    parser.add_argument("--mode", choices=("auto", "aggregate", "self"), default="auto")
    parser.add_argument("--expected-total-files", type=int, default=EXPECTED_TOTAL_FILES)
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
