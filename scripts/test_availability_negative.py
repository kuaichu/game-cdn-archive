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
from scripts.availability_schema import ProbeResult, probe_fact_defaults  # noqa: E402
from scripts.validate_availability import validate_arknights  # noqa: E402


ARKNIGHTS_ROOT = ROOT / "docs" / "data" / "arknights"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def failed_probe(url: str) -> ProbeResult:
    return {"url": url, "probe": probe_fact_defaults(ok=False, status=404, method="HEAD", checked_at="2026-07-06T00:00:00.000Z", final_url=url, content_type="", size=0, error="HTTP 404", stale=False, scheduler_confidence="high")}


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
    result = ArknightsAvailabilityAdapter().interpret([failed_probe(url)], {"name": "missing.zip", "url": url})
    expected = {"state": "unavailable", "reason": "http_404", "preferred_url": "", "confidence": "low", "retained": False, "display_label": "链接失效"}
    if result != expected:
        raise AssertionError(f"unexpected Arknights failure interpretation: {result!r}")


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


def main() -> None:
    assert_arknights_failed_probe_maps_to_unavailable()
    assert_validator_rejects(("availability", "interpretation", "state"), "foobar", ":state:foobar")
    assert_validator_rejects(("availability", "interpretation", "reason"), "because_magic", ":reason:because_magic")
    assert_validator_rejects(("availability", "source", "kind"), "side_channel", ":source_kind:side_channel")
    assert_validator_rejects(("availability", "interpretation", "confidence"), "certain", ":confidence:certain")
    print("Availability negative-path checks")
    print("arknights_failed_probe=PASS")
    print("closed_vocab_rejection=PASS")
    print("result=PASS")


if __name__ == "__main__":
    main()
