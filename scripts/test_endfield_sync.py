#!/usr/bin/env python3
"""Regression checks for the Endfield upstream archive sync contract."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import import_endfield_archive as importer  # noqa: E402


def assert_workflow_clones_archive_branch() -> None:
    workflow = (ROOT / ".github" / "workflows" / "sync-archive.yml").read_text(encoding="utf-8")
    clone_line = next(
        line for line in workflow.splitlines() if "checkout_endfield_archive.sh" in line
    )
    if "/tmp/ak-endfield-api-archive" not in clone_line:
        raise AssertionError(f"Endfield checkout destination changed unexpectedly: {clone_line}")

    checkout_script = (SCRIPTS / "checkout_endfield_archive.sh").read_text(encoding="utf-8")
    for required in (
        "--branch archive",
        "--single-branch",
        "--depth 1",
        "--filter=blob:none",
        "--no-checkout",
        "sparse-checkout set --no-cone --stdin",
        "/output/akEndfield/launcher/game/1/all.json",
        "/output/akEndfield/launcher/game/1/all_patch.json",
        "/output/mirror_file_list.json",
    ):
        if required not in checkout_script:
            raise AssertionError(f"Endfield sparse checkout omitted {required!r}")


def assert_missing_main_layout_fails_clearly() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            importer.load_archive_inputs(Path(temp_dir))
        except FileNotFoundError as exc:
            message = str(exc)
            for required in ("archive branch", "all.json", "all_patch.json", "mirror_file_list.json"):
                if required not in message:
                    raise AssertionError(f"missing-input error omitted {required!r}: {message}") from exc
        else:
            raise AssertionError("a main-branch-style checkout without output/ was accepted")


def assert_archive_layout_loads() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        game_dir = root / "output" / "akEndfield" / "launcher" / "game" / "1"
        game_dir.mkdir(parents=True)
        paths = (
            game_dir / "all.json",
            game_dir / "all_patch.json",
            root / "output" / "mirror_file_list.json",
        )
        payloads = ([{"kind": "full"}], [{"kind": "patch"}], [{"kind": "mirror"}])
        for path, payload in zip(paths, payloads, strict=True):
            path.write_text(json.dumps(payload), encoding="utf-8")
        if importer.load_archive_inputs(root) != payloads:
            raise AssertionError("archive-branch input layout was not loaded correctly")


def main() -> None:
    assert_workflow_clones_archive_branch()
    assert_missing_main_layout_fails_clearly()
    assert_archive_layout_loads()
    print("endfield_archive_branch_contract=PASS")
    print("endfield_missing_inputs_fail_fast=PASS")
    print("endfield_archive_layout=PASS")


if __name__ == "__main__":
    main()
