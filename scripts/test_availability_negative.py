#!/usr/bin/env python3
"""Negative-path checks for the availability migration."""

from __future__ import annotations

import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from adapters.arknights import ArknightsAvailabilityAdapter  # noqa: E402
from adapters.android import AndroidAvailabilityAdapter  # noqa: E402
from scripts.availability_schema import ProbeResult, availability_block, probe_fact_defaults  # noqa: E402
from scripts.validate_availability import validate_android, validate_arknights  # noqa: E402


ARKNIGHTS_ROOT = ROOT / "docs" / "data" / "arknights"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def failed_probe(url: str) -> ProbeResult:
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=False,
            status=404,
            method="HEAD",
            checked_at="2026-07-06T00:00:00.000Z",
            final_url=url,
            content_type="",
            size=0,
            error="HTTP 404",
            stale=False,
            scheduler_confidence="high",
        ),
    }


def android_probe(
    url: str,
    *,
    ok: bool,
    status: int,
    content_type: str,
    size: int,
    error: str = "",
) -> ProbeResult:
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=status,
            method="HEAD",
            checked_at="2026-07-06T00:00:00.000Z",
            final_url=url,
            content_type=content_type,
            size=size,
            error=error,
            stale=False,
            scheduler_confidence="high",
        ),
    }


def first_package(versions: dict[str, Any]) -> dict[str, Any]:
    for row in versions.values():
        packages = row.get("packages") if isinstance(row, dict) else None
        if isinstance(packages, list) and packages:
            package = packages[0]
            if isinstance(package, dict):
                return package
    raise AssertionError("no Arknights package record found")


def assert_arknights_failed_probe_maps_to_unavailable() -> None:
    url = "https://example.invalid/missing.zip"
    adapter = ArknightsAvailabilityAdapter()
    result = adapter.interpret([failed_probe(url)], {"name": "missing.zip", "url": url})
    expected = {
        "state": "unavailable",
        "reason": "http_404",
        "preferred_url": "",
        "confidence": "low",
        "retained": False,
        "display_label": "链接失效",
    }
    if result != expected:
        raise AssertionError(f"unexpected Arknights failure interpretation: {result!r}")


def assert_android_negative_paths() -> None:
    adapter = AndroidAvailabilityAdapter()
    url = "https://example.invalid/game.apk"

    result_404 = adapter.interpret([
        android_probe(url, ok=False, status=404, content_type="text/html", size=0, error="HTTP 404")
    ], {"game_id": "android-test", "version": "1.0.0", "url": url, "filename": "game.apk"})
    expected_404 = {
        "state": "unavailable",
        "reason": "http_404",
        "preferred_url": "",
        "confidence": "low",
        "retained": False,
        "display_label": "链接失效",
    }
    if result_404 != expected_404:
        raise AssertionError(f"unexpected Android 404 interpretation: {result_404!r}")

    result_non_apk = adapter.interpret([
        android_probe(url, ok=True, status=200, content_type="text/html", size=20 * 1024 * 1024)
    ], {"game_id": "android-test", "version": "1.0.0", "url": url, "filename": "game.apk"})
    if result_non_apk["state"] != "unavailable" or result_non_apk["reason"] != "content_type_mismatch":
        raise AssertionError(f"unexpected Android non-APK interpretation: {result_non_apk!r}")

    result_fake_200 = adapter.interpret([
        android_probe(url, ok=True, status=200, content_type="text/plain", size=3)
    ], {"game_id": "android-test", "version": "1.0.0", "url": url, "filename": "game.apk"})
    expected_fake_200 = {
        "state": "unavailable",
        "reason": "content_type_mismatch",
        "preferred_url": "",
        "confidence": "low",
        "retained": False,
        "display_label": "链接失效",
    }
    if result_fake_200 != expected_fake_200:
        raise AssertionError(f"unexpected Android fake-200 interpretation: {result_fake_200!r}")

    result_small = adapter.interpret([
        android_probe(url, ok=True, status=200, content_type="application/vnd.android.package-archive", size=16)
    ], {"game_id": "android-test", "version": "1.0.0", "url": url, "filename": "game.apk"})
    if result_small["state"] != "unavailable" or result_small["reason"] != "size_zero":
        raise AssertionError(f"unexpected Android small APK interpretation: {result_small!r}")

    result_retained = adapter.interpret([
        android_probe(url, ok=False, status=404, content_type="text/html", size=0, error="HTTP 404")
    ], {
        "game_id": "android-test",
        "version": "0.9.0",
        "url": url,
        "filename": "game.apk",
        "captured_at": "2026-01-01T00:00:00Z",
        "source": "Wayback Machine historical URL",
    })
    expected_retained = {
        "state": "unavailable",
        "reason": "retained_historical",
        "preferred_url": "",
        "confidence": "low",
        "retained": True,
        "display_label": "链接失效",
    }
    if result_retained != expected_retained:
        raise AssertionError(f"unexpected Android retained interpretation: {result_retained!r}")


def mutated_versions_with(path_parts: tuple[str, ...], value: Any) -> dict[str, Any]:
    versions = deepcopy(load_json(ARKNIGHTS_ROOT / "versions.json"))
    package = first_package(versions)
    target: Any = package
    for part in path_parts[:-1]:
        target = target[part]
    target[path_parts[-1]] = value
    return versions


def assert_validator_rejects(path_parts: tuple[str, ...], value: Any, expected_token: str) -> None:
    with tempfile.TemporaryDirectory(prefix="availability-negative-") as temp:
        temp_root = Path(temp)
        write_json(temp_root / "versions.json", mutated_versions_with(path_parts, value))
        errors = validate_arknights(temp_root)
    if not any(expected_token in error for error in errors):
        raise AssertionError(f"validator did not reject {'.'.join(path_parts)}={value!r}; errors={errors!r}")


def valid_android_index() -> dict[str, Any]:
    url = "https://example.invalid/game.apk"
    record = {
        "game_id": "android-test",
        "version": "1.0.0",
        "channel": "official",
        "url": url,
        "filename": "game.apk",
    }
    probe = android_probe(
        url,
        ok=True,
        status=200,
        content_type="application/vnd.android.package-archive",
        size=2 * 1024 * 1024,
    )
    interpretation = AndroidAvailabilityAdapter().interpret([probe], record)
    record["availability"] = availability_block([probe], "live_probe", interpretation, "scripts/test_availability_negative.py")
    return {
        "games": {
            "android-test": {
                "name": "Android Test",
                "versions": [record],
            }
        }
    }


def mutated_android_index_with(path_parts: tuple[str, ...], value: Any) -> dict[str, Any]:
    index = valid_android_index()
    record = index["games"]["android-test"]["versions"][0]
    target: Any = record
    for part in path_parts[:-1]:
        target = target[part]
    target[path_parts[-1]] = value
    return index


def assert_android_validator_rejects(path_parts: tuple[str, ...], value: Any, expected_token: str) -> None:
    with tempfile.TemporaryDirectory(prefix="android-availability-negative-") as temp:
        temp_root = Path(temp)
        write_json(temp_root / "index.json", mutated_android_index_with(path_parts, value))
        errors = validate_android(temp_root)
    if not any(expected_token in error for error in errors):
        raise AssertionError(f"Android validator did not reject {'.'.join(path_parts)}={value!r}; errors={errors!r}")


def main() -> None:
    assert_arknights_failed_probe_maps_to_unavailable()
    assert_android_negative_paths()
    assert_validator_rejects(("availability", "interpretation", "state"), "foobar", ":state:foobar")
    assert_validator_rejects(("availability", "interpretation", "reason"), "because_magic", ":reason:because_magic")
    assert_validator_rejects(("availability", "source", "kind"), "side_channel", ":source_kind:side_channel")
    assert_validator_rejects(("availability", "interpretation", "confidence"), "certain", ":confidence:certain")
    assert_android_validator_rejects(("availability", "interpretation", "state"), "foobar", ":state:foobar")
    assert_android_validator_rejects(("availability", "interpretation", "reason"), "because_magic", ":reason:because_magic")
    assert_android_validator_rejects(("availability", "source", "kind"), "side_channel", ":source_kind:side_channel")
    assert_android_validator_rejects(("availability", "interpretation", "confidence"), "certain", ":confidence:certain")

    print("Availability negative-path checks")
    print("arknights_failed_probe=PASS")
    print("android_failed_probe=PASS")
    print("android_fake_200=PASS")
    print("android_retained_historical=PASS")
    print("closed_vocab_rejection=PASS")
    print("result=PASS")


if __name__ == "__main__":
    main()
