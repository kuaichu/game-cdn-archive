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
from adapters.android import AndroidAvailabilityAdapter  # noqa: E402
from adapters.endfield import EndfieldAvailabilityAdapter  # noqa: E402
from adapters.hoyo import HoyoAvailabilityAdapter  # noqa: E402
from scripts.availability_schema import (  # noqa: E402
    AVAILABILITY_REASONS,
    AVAILABILITY_STATES,
    CONFIDENCES,
    SOURCE_KINDS,
)


DEFAULT_ARKNIGHTS = ROOT / "docs" / "data" / "arknights"
DEFAULT_ANDROID = ROOT / "docs" / "data" / "android"
DEFAULT_ENDFIELD = ROOT / "docs" / "data" / "endfield"
DEFAULT_HOYO = ROOT / "docs" / "data" / "hoyo"
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
    required = {
        "ok",
        "status",
        "method",
        "checked_at",
        "final_url",
        "content_type",
        "size",
        "error",
        "stale",
        "scheduler_confidence",
    }
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

    any_stale = any(
        isinstance(candidate, dict)
        and isinstance(candidate.get("probe"), dict)
        and candidate["probe"].get("stale")
        for candidate in candidates
    )
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
    versions_path = root / "versions.json"
    versions = load_json(versions_path)
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


def validate_android(root: Path) -> list[str]:
    errors: list[str] = []
    index_path = root / "index.json"
    index = load_json(index_path)
    adapter = AndroidAvailabilityAdapter()
    if not isinstance(index, dict):
        return ["android:index_not_object"]
    games = index.get("games")
    if not isinstance(games, dict):
        return ["android:games_missing"]
    for game_id, game in games.items():
        versions = game.get("versions") if isinstance(game, dict) else None
        if not isinstance(versions, list):
            errors.append(f"android:{game_id}:versions_missing")
            continue
        for index, entry in enumerate(versions, start=1):
            if not isinstance(entry, dict):
                errors.append(f"android:{game_id}:{index}:entry_not_object")
                continue
            errors.extend(validate_availability(entry, f"android:{game_id}:{index}", adapter))
    return errors


def as_list(value: Any) -> list[Any]:
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def iter_hoyo_download_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    game = row.get("game") or {}
    for key in ("full", "segments"):
        items.extend(item for item in as_list(game.get(key)) if isinstance(item, dict) and item.get("url"))
    for voice in (row.get("voice") or {}).values():
        items.extend(item for item in as_list(voice) if isinstance(item, dict) and item.get("url"))
    for patch in (row.get("update") or {}).values():
        items.extend(item for item in as_list((patch or {}).get("game")) if isinstance(item, dict) and item.get("url"))
        for voice in ((patch or {}).get("voice") or {}).values():
            items.extend(item for item in as_list(voice) if isinstance(item, dict) and item.get("url"))
    return items


def validate_hoyo(root: Path) -> list[str]:
    errors: list[str] = []
    index_path = root / "games.json"
    index = load_json(index_path)
    adapter = HoyoAvailabilityAdapter()
    if not isinstance(index, dict):
        return ["hoyo:index_not_object"]
    games = index.get("games")
    if not isinstance(games, list):
        return ["hoyo:games_missing"]
    for game in games:
        if not isinstance(game, dict):
            errors.append("hoyo:game_not_object")
            continue
        game_id = str(game.get("id") or "")
        versions = game.get("versions")
        if not isinstance(versions, list):
            errors.append(f"hoyo:{game_id}:versions_missing")
            continue
        for summary in versions:
            if not isinstance(summary, dict):
                errors.append(f"hoyo:{game_id}:summary_not_object")
                continue
            version = str(summary.get("version") or "")
            summary_path = f"hoyo:{game_id}:{version}:summary"
            errors.extend(validate_availability(summary, summary_path, adapter))
            source = (summary.get("availability") or {}).get("source") or {}
            interpretation = (summary.get("availability") or {}).get("interpretation") or {}
            if source.get("kind") != "metadata_inference":
                errors.append(f"{summary_path}:source_kind_not_metadata_inference:{source.get('kind')}")
            if interpretation.get("confidence") == "high" or source.get("confidence") == "high":
                errors.append(f"{summary_path}:metadata_high_confidence")

            shard_path = root / "versions" / game_id / f"{version}.json"
            if not shard_path.exists():
                errors.append(f"hoyo:{game_id}:{version}:shard_missing")
                continue
            row = load_json(shard_path)
            if not isinstance(row, dict):
                errors.append(f"hoyo:{game_id}:{version}:shard_not_object")
                continue
            for index, item in enumerate(iter_hoyo_download_items(row), start=1):
                item_path = f"hoyo:{game_id}:{version}:item_{index}"
                errors.extend(validate_availability(item, item_path, adapter))
                item_source = (item.get("availability") or {}).get("source") or {}
                item_interpretation = (item.get("availability") or {}).get("interpretation") or {}
                if item_source.get("kind") != "metadata_inference":
                    errors.append(f"{item_path}:source_kind_not_metadata_inference:{item_source.get('kind')}")
                if item_interpretation.get("confidence") == "high" or item_source.get("confidence") == "high":
                    errors.append(f"{item_path}:metadata_high_confidence")
    return errors


def iter_endfield_file_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    items = [item for item in row.get("packages") or [] if isinstance(item, dict)]
    for route in row.get("patches") or []:
        if not isinstance(route, dict):
            continue
        items.extend(item for item in route.get("parts") or [] if isinstance(item, dict))
    return items


def validate_endfield(root: Path) -> list[str]:
    errors: list[str] = []
    index_path = root / "index.json"
    versions_path = root / "versions.json"
    index = load_json(index_path)
    versions = load_json(versions_path)
    adapter = EndfieldAvailabilityAdapter()
    if not isinstance(index, dict):
        return ["endfield:index_not_object"]
    if not isinstance(versions, dict):
        return ["endfield:versions_not_object"]
    summaries = index.get("versions")
    if not isinstance(summaries, list):
        return ["endfield:summaries_missing"]

    for summary in summaries:
        if not isinstance(summary, dict):
            errors.append("endfield:summary_not_object")
            continue
        version = str(summary.get("version") or "")
        summary_path = f"endfield:{version}:summary"
        errors.extend(validate_availability(summary, summary_path, adapter))
        source = (summary.get("availability") or {}).get("source") or {}
        interpretation = (summary.get("availability") or {}).get("interpretation") or {}
        if source.get("kind") != "upstream_archive":
            errors.append(f"{summary_path}:source_kind_not_upstream_archive:{source.get('kind')}")
        if interpretation.get("confidence") == "high" or source.get("confidence") == "high":
            errors.append(f"{summary_path}:upstream_archive_high_confidence")

        row = versions.get(version)
        if not isinstance(row, dict):
            errors.append(f"endfield:{version}:version_missing")
            continue
        for index, item in enumerate(iter_endfield_file_items(row), start=1):
            item_path = f"endfield:{version}:item_{index}"
            errors.extend(validate_availability(item, item_path, adapter))
            item_source = (item.get("availability") or {}).get("source") or {}
            item_interpretation = (item.get("availability") or {}).get("interpretation") or {}
            if item_source.get("kind") != "upstream_archive":
                errors.append(f"{item_path}:source_kind_not_upstream_archive:{item_source.get('kind')}")
            if item_interpretation.get("confidence") == "high" or item_source.get("confidence") == "high":
                errors.append(f"{item_path}:upstream_archive_high_confidence")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arknights-root", type=Path, default=DEFAULT_ARKNIGHTS)
    parser.add_argument("--android-root", type=Path, default=DEFAULT_ANDROID)
    parser.add_argument("--endfield-root", type=Path, default=DEFAULT_ENDFIELD)
    parser.add_argument("--hoyo-root", type=Path, default=DEFAULT_HOYO)
    args = parser.parse_args()

    errors = []
    errors.extend(validate_adapter_no_network(ROOT / "adapters"))
    errors.extend(validate_arknights(args.arknights_root))
    errors.extend(validate_android(args.android_root))
    errors.extend(validate_endfield(args.endfield_root))
    errors.extend(validate_hoyo(args.hoyo_root))

    print("Availability validation")
    print(f"arknights_root={args.arknights_root.resolve()}")
    print(f"android_root={args.android_root.resolve()}")
    print(f"endfield_root={args.endfield_root.resolve()}")
    print(f"hoyo_root={args.hoyo_root.resolve()}")
    print(f"errors={len(errors)}")
    if errors:
        print("result=FAIL")
        print("\n".join(errors[:100]))
        raise SystemExit(1)
    print("result=PASS")


if __name__ == "__main__":
    main()
