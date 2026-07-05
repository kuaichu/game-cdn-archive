#!/usr/bin/env python3
"""Promote staged Arknights PC data into the formal static data set."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "data" / "arknights"
DEFAULT_STAGING = DEFAULT_OUTPUT / "staging"
VALIDATOR = REPO_ROOT / "scripts" / "validate_arknights_pc.py"
DOCS_ROOT = REPO_ROOT / "docs"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_validator(root: Path) -> None:
    subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(root)],
        cwd=REPO_ROOT,
        check=True,
    )


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def copy_tree(source: Path, target: Path) -> None:
    if source.exists():
        shutil.copytree(source, target)


def rewrite_staging_links(value, staging_prefix: str, output_prefix: str):
    if isinstance(value, str):
        return value.replace(staging_prefix, output_prefix, 1) if value.startswith(staging_prefix) else value
    if isinstance(value, dict):
        return {
            key: rewrite_staging_links(item, staging_prefix, output_prefix)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [rewrite_staging_links(item, staging_prefix, output_prefix) for item in value]
    return value


def data_prefix(path: Path) -> str:
    path = path.resolve()
    try:
        relative = path.relative_to(DOCS_ROOT)
    except ValueError as exc:
        raise ValueError(f"{path} must be inside {DOCS_ROOT}") from exc
    return relative.as_posix().rstrip("/") + "/"


def promote(staging: Path, output: Path) -> None:
    staging = staging.resolve()
    output = output.resolve()
    if not staging.exists():
        raise FileNotFoundError(staging)
    if staging == output:
        raise ValueError("staging and output must be different directories")
    if output not in staging.parents:
        raise ValueError("staging must be inside the output directory")

    run_validator(staging)

    staged_index = load_json(staging / "index.json")
    staged_versions = load_json(staging / "versions.json")
    staged_version_set = {
        str(item.get("version") or "")
        for item in staged_index.get("versions") or []
        if isinstance(item, dict)
    }
    if staged_version_set != set(staged_versions.keys()):
        raise RuntimeError("staged index and versions.json have different version sets")

    remove_tree(output / "lists")
    copy_tree(staging / "lists", output / "lists")

    staging_prefix = data_prefix(staging / "lists")
    output_prefix = data_prefix(output / "lists")
    promoted_versions = rewrite_staging_links(staged_versions, staging_prefix, output_prefix)
    write_json(output / "index.json", staged_index)
    write_json(output / "versions.json", promoted_versions)

    run_validator(output)
    print("promoted_versions=" + ",".join(sorted(staged_version_set)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    promote(args.staging, args.output)


if __name__ == "__main__":
    main()
