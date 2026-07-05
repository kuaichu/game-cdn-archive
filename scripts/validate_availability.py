#!/usr/bin/env python3
"""Read-only validator for migrated availability records."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from adapters.arknights import ArknightsAvailabilityAdapter  # noqa: E402
from scripts.availability_schema import (  # noqa: E402
    AVAILABILITY_REASONS,
    AVAILABILITY_STATES,
    CONFIDENCES,
    SOURCE_KINDS,
)


DEFAULT_ARKNIGHTS = ROOT / "docs" / "data" / "arknights"
FORBIDDEN_ADAPTER_MODULES = {"urllib", "requests", "http", "http.client", "subprocess", "socket"}
FORBIDDEN_ADAPTER_NAMES = {"urlopen", "Request", "HTTPConnection", "HTTPSConnection", "curl", "fetch"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_adapter_no_network(adapter_dir: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted(adapter_dir.glob("*.py")):
        if path.name in {"__init__.py", "base.py"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if alias.name in FORBIDDEN_ADAPTER_MODULES or root in FORBIDDEN_ADAPTER_MODULES:
                        errors.append(f"{path.name}:forbidden_import:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                root = module.split(".")[0]
                if module in FORBIDDEN_ADAPTER_MODULES or root in FORBIDDEN_ADAPTER_MODULES:
                    errors.append(f"{path.name}:forbidden_import:{module}")
            elif isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in FORBIDDEN_ADAPTER_NAMES:
                    errors.append(f"{path.name}:forbidden_network_call:{name}")
    return errors


def validate_probe(candidate: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    if not is_nonempty_string(candidate.get("url")):
        errors.append(f"{path}:candidate_url")
    probe = candidate.get("probe")
    if not isinstance(probe, dict):
        return [*errors, f"{path}:probe_missing"]
    required = {"ok", "status", "method", "checked_at", "final_url", "content_type", "size", "error", "stale", "scheduler_confidence"}
    missing = sorted(required - set(probe.keys()))
    if missing:
        errors.append(f"{path}:probe_missing:{','.join(missing)}")
    if probe.get("scheduler_confidence") not in CONFIDENCES:
        errors.append(f"{path}:probe_scheduler_confidence:{probe.get('scheduler_confidence')}")
    if not isinstance(probe.get("ok"), bool):
        errors.append(f"{path}:probe_ok_not_bool")
    if not isinstance(probe.get("stale"), bool):
        errors.append(f"{path}:probe_stale_not_bool")
    for key in ("status", "size"):
        try:
            int(probe.get(key))
        except (TypeError, ValueError):
            errors.append(f"{path}:probe_{key}_not_int")
    return errors


def validate_availability(record: dict[str, Any], path: str, adapter: Any) -> list[str]:
    errors: list[str] = []
    availability = record.get("availability")
    if not isinstance(availability, dict):
        return [f"{path}:availability_missing"]
    candidates = availability.get("candidates")
    source = availability.get("source")
    interpretation = availability.get("interpretation")
    if not isinstance(candidates, list) or not candidates:
        errors.append(f"{path}:candidates_missing")
        candidates = []
    if not isinstance(source, dict):
        errors.append(f"{path}:source_missing")
        source = {}
    if not isinstance(interpretation, dict):
        errors.append(f"{path}:interpretation_missing")
        interpretation = {}
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            errors.append(f"{path}:candidate_{index}_not_object")
            continue
        errors.extend(validate_probe(candidate, f"{path}:candidate_{index}"))
    candidate_urls = {candidate.get("url") for candidate in candidates if isinstance(candidate, dict)}
    preferred_url = interpretation.get("preferred_url")
    declared_mirrors = {record.get("mirror_url"), record.get("preferred_url")} - {None, ""}
    if preferred_url and preferred_url not in candidate_urls and preferred_url not in declared_mirrors:
        errors.append(f"{path}:preferred_url_not_candidate")
    if source.get("kind") not in SOURCE_KINDS:
        errors.append(f"{path}:source_kind:{source.get('kind')}")
    if source.get("confidence") not in CONFIDENCES:
        errors.append(f"{path}:source_confidence:{source.get('confidence')}")
    state = interpretation.get("state")
    reason = interpretation.get("reason")
    confidence = interpretation.get("confidence")
    if state not in AVAILABILITY_STATES:
        errors.append(f"{path}:state:{state}")
    if reason not in AVAILABILITY_REASONS:
        errors.append(f"{path}:reason:{reason}")
    if confidence not in CONFIDENCES:
        errors.append(f"{path}:confidence:{confidence}")
    if state and not is_nonempty_string(interpretation.get("display_label")):
        errors.append(f"{path}:display_label_missing")
    if not isinstance(interpretation.get("retained"), bool):
        errors.append(f"{path}:retained_not_bool")
    if interpretation.get("retained") and (state != "unavailable" or reason != "retained_historical"):
        errors.append(f"{path}:retained_requires_unavailable_retained_historical")
    any_stale = any(isinstance(candidate, dict) and isinstance(candidate.get("probe"), dict) and candidate["probe"].get("stale") for candidate in candidates)
    if any_stale and confidence == "high" and state != "unknown":
        errors.append(f"{path}:stale_probe_high_confidence")
    if candidates:
        expected = adapter.interpret(candidates, record)
        expected_keys = {"state", "reason", "preferred_url", "confidence", "retained", "display_label"}
        if set(expected.keys()) != expected_keys:
            errors.append(f"{path}:adapter_shape:{','.join(sorted(expected.keys()))}")
    return errors


def validate_arknights(root: Path) -> list[str]:
    errors: list[str] = []
    versions = load_json(root / "versions.json")
    adapter = ArknightsAvailabilityAdapter()
    if not isinstance(versions, dict):
        return ["arknights:versions_not_object"]
    for version, row in versions.items():
        packages = row.get("packages") if isinstance(row, dict) else None
        if not isinstance(packages, list):
            errors.append(f"arknights:{version}:packages_missing")
            continue
        for index, package in enumerate(packages, start=1):
            if not isinstance(package, dict):
                errors.append(f"arknights:{version}:{index}:package_not_object")
                continue
            errors.extend(validate_availability(package, f"arknights:{version}:{index}", adapter))
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arknights-root", type=Path, default=DEFAULT_ARKNIGHTS)
    args = parser.parse_args()
    errors = []
    errors.extend(validate_adapter_no_network(ROOT / "adapters"))
    errors.extend(validate_arknights(args.arknights_root))
    print("Availability validation")
    print(f"arknights_root={args.arknights_root.resolve()}")
    print(f"errors={len(errors)}")
    if errors:
        print("result=FAIL")
        print("\n".join(errors[:100]))
        raise SystemExit(1)
    print("result=PASS")


if __name__ == "__main__":
    main()
