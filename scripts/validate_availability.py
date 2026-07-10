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
from adapters.nte import NteAvailabilityAdapter  # noqa: E402
from adapters.p5x import P5xAvailabilityAdapter  # noqa: E402
from adapters.tof import TofAvailabilityAdapter  # noqa: E402
from adapters.wuwa import WuwaAvailabilityAdapter  # noqa: E402
from nte_versioning import version_family, version_key  # noqa: E402
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
DEFAULT_NTE = ROOT / "docs" / "data"
DEFAULT_P5X = ROOT / "docs" / "data" / "p5x"
DEFAULT_TOF = ROOT / "docs" / "data" / "tof"
DEFAULT_WUWA = ROOT / "docs" / "data" / "wuwa"
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


def validate_nte(root: Path) -> list[str]:
    errors: list[str] = []
    catalog_path = root / "catalog.json"
    catalog = load_json(catalog_path)
    adapter = NteAvailabilityAdapter()
    if not isinstance(catalog, dict):
        return ["nte:catalog_not_object"]
    versions = catalog.get("versions")
    if not isinstance(versions, list):
        return ["nte:versions_missing"]

    errors.extend(validate_nte_release_types(versions))

    for row in versions:
        if not isinstance(row, dict):
            errors.append("nte:version_not_object")
            continue
        version = str(row.get("version") or "")
        summary_path = f"nte:{version}:summary"
        errors.extend(validate_availability(row, summary_path, adapter))
        source = (row.get("availability") or {}).get("source") or {}
        if source.get("kind") != "live_probe":
            errors.append(f"{summary_path}:source_kind_not_live_probe:{source.get('kind')}")

        for section_name in ("full", "patches"):
            section = row.get(section_name)
            if not isinstance(section, dict) or not section.get("json"):
                continue
            shard_path = root / Path(str(section["json"])).relative_to("data")
            if not shard_path.exists():
                errors.append(f"nte:{version}:{section_name}:shard_missing:{shard_path}")
                continue
            items = load_json(shard_path)
            if not isinstance(items, list):
                errors.append(f"nte:{version}:{section_name}:shard_not_list")
                continue
            for index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    errors.append(f"nte:{version}:{section_name}:item_{index}_not_object")
                    continue
                item_path = f"nte:{version}:{section_name}:item_{index}"
                errors.extend(validate_availability(item, item_path, adapter))
                item_source = (item.get("availability") or {}).get("source") or {}
                item_interpretation = (item.get("availability") or {}).get("interpretation") or {}
                if item_source.get("kind") != "metadata_inference":
                    errors.append(f"{item_path}:source_kind_not_metadata_inference:{item_source.get('kind')}")
                if item_interpretation.get("confidence") == "high" or item_source.get("confidence") == "high":
                    errors.append(f"{item_path}:metadata_high_confidence")
    return errors


def validate_tof(root: Path) -> list[str]:
    errors: list[str] = []
    catalog_path = root / "catalog.json"
    catalog = load_json(catalog_path)
    adapter = TofAvailabilityAdapter()
    if not isinstance(catalog, dict):
        return ["tof:catalog_not_object"]
    versions = catalog.get("versions")
    if not isinstance(versions, list):
        return ["tof:versions_missing"]

    for row in versions:
        if not isinstance(row, dict):
            errors.append("tof:version_not_object")
            continue
        version = str(row.get("version") or "")
        summary_path = f"tof:{version}:summary"
        errors.extend(validate_availability(row, summary_path, adapter))
        source = (row.get("availability") or {}).get("source") or {}
        if source.get("kind") != "live_probe":
            errors.append(f"{summary_path}:source_kind_not_live_probe:{source.get('kind')}")

        for section_name in ("full", "patches"):
            section = row.get(section_name)
            if not isinstance(section, dict) or not section.get("json"):
                continue
            rel = Path(str(section["json"]))
            shard_path = root.parent / rel.relative_to("data") if rel.parts and rel.parts[0] == "data" else root / rel
            if not shard_path.exists():
                errors.append(f"tof:{version}:{section_name}:shard_missing:{shard_path}")
                continue
            items = load_json(shard_path)
            if not isinstance(items, list):
                errors.append(f"tof:{version}:{section_name}:shard_not_list")
                continue
            for index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    errors.append(f"tof:{version}:{section_name}:item_{index}_not_object")
                    continue
                item_path = f"tof:{version}:{section_name}:item_{index}"
                errors.extend(validate_availability(item, item_path, adapter))
                item_source = (item.get("availability") or {}).get("source") or {}
                item_interpretation = (item.get("availability") or {}).get("interpretation") or {}
                if item_source.get("kind") != "metadata_inference":
                    errors.append(f"{item_path}:source_kind_not_metadata_inference:{item_source.get('kind')}")
                if item_interpretation.get("confidence") == "high" or item_source.get("confidence") == "high":
                    errors.append(f"{item_path}:metadata_high_confidence")
    return errors


def validate_p5x(root: Path) -> list[str]:
    errors: list[str] = []
    catalog_path = root / "catalog.json"
    catalog = load_json(catalog_path)
    adapter = P5xAvailabilityAdapter()
    if not isinstance(catalog, dict):
        return ["p5x:catalog_not_object"]
    versions = catalog.get("versions")
    if not isinstance(versions, list):
        return ["p5x:versions_missing"]

    for row in versions:
        if not isinstance(row, dict):
            errors.append("p5x:version_not_object")
            continue
        version = str(row.get("version") or "")
        summary_path = f"p5x:{version}:summary"
        errors.extend(validate_availability(row, summary_path, adapter))
        source = (row.get("availability") or {}).get("source") or {}
        if source.get("kind") != "live_probe":
            errors.append(f"{summary_path}:source_kind_not_live_probe:{source.get('kind')}")

        for section_name in ("full", "patches"):
            section = row.get(section_name)
            if not isinstance(section, dict) or not section.get("json"):
                continue
            rel = Path(str(section["json"]))
            shard_path = root.parent / rel.relative_to("data") if rel.parts and rel.parts[0] == "data" else root / rel
            if not shard_path.exists():
                errors.append(f"p5x:{version}:{section_name}:shard_missing:{shard_path}")
                continue
            items = load_json(shard_path)
            if not isinstance(items, list):
                errors.append(f"p5x:{version}:{section_name}:shard_not_list")
                continue
            for index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    errors.append(f"p5x:{version}:{section_name}:item_{index}_not_object")
                    continue
                item_path = f"p5x:{version}:{section_name}:item_{index}"
                errors.extend(validate_availability(item, item_path, adapter))
                item_source = (item.get("availability") or {}).get("source") or {}
                item_interpretation = (item.get("availability") or {}).get("interpretation") or {}
                if item_source.get("kind") != "metadata_inference":
                    errors.append(f"{item_path}:source_kind_not_metadata_inference:{item_source.get('kind')}")
                if item_interpretation.get("confidence") == "high" or item_source.get("confidence") == "high":
                    errors.append(f"{item_path}:metadata_high_confidence")
    return errors


def validate_nte_release_types(versions: list[Any]) -> list[str]:
    errors: list[str] = []
    families: dict[str, list[dict[str, Any]]] = {}

    for row in versions:
        if not isinstance(row, dict):
            continue
        version = str(row.get("version") or "")
        try:
            family = version_family(version)
        except ValueError:
            errors.append(f"nte:{version}:invalid_version")
            continue

        if row.get("status") == 200 and row.get("full"):
            release_type = row.get("release_type")
            if release_type not in {"major", "patch"}:
                errors.append(f"nte:{version}:release_type:{release_type}")
            families.setdefault(family, []).append(row)
        elif row.get("release_type") is not None:
            errors.append(f"nte:{version}:release_type_on_unavailable:{row.get('release_type')}")

    for family, rows in sorted(families.items()):
        major_rows = [row for row in rows if row.get("release_type") == "major"]
        if len(major_rows) != 1:
            errors.append(f"nte:{family}:release_type_major_count:{len(major_rows)}")
            continue
        expected = min(rows, key=lambda row: version_key(str(row.get("version") or "")))
        actual_version = major_rows[0].get("version")
        expected_version = expected.get("version")
        if actual_version != expected_version:
            errors.append(f"nte:{family}:release_type_major_not_min:{actual_version}!={expected_version}")

    return errors


def iter_wuwa_patch_parts(row: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for route in row.get("patches") or []:
        if not isinstance(route, dict):
            continue
        items.extend(item for item in route.get("parts") or [] if isinstance(item, dict))
    return items


def iter_wuwa_file_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    files = [item for item in row.get("files") or [] if isinstance(item, dict)]
    return [*files, *iter_wuwa_patch_parts(row)]


def wuwa_data_path(root: Path, link: str) -> Path:
    rel = Path(str(link))
    if not str(link).startswith("data/wuwa/"):
        raise ValueError(f"Unexpected WuWa data link: {link}")
    return root.parents[1] / rel


def validate_wuwa(root: Path) -> list[str]:
    errors: list[str] = []
    index_path = root / "index.json"
    index = load_json(index_path)
    adapter = WuwaAvailabilityAdapter()
    if not isinstance(index, dict):
        return ["wuwa:index_not_object"]
    summaries = index.get("versions")
    if not isinstance(summaries, list):
        return ["wuwa:summaries_missing"]

    for summary in summaries:
        if not isinstance(summary, dict):
            errors.append("wuwa:summary_not_object")
            continue
        version = str(summary.get("version") or "")
        summary_path = f"wuwa:{version}:summary"
        errors.extend(validate_availability(summary, summary_path, adapter))
        source = (summary.get("availability") or {}).get("source") or {}
        interpretation = (summary.get("availability") or {}).get("interpretation") or {}
        if source.get("kind") not in {"metadata_inference", "live_probe"}:
            errors.append(f"{summary_path}:source_kind_not_wuwa_allowed:{source.get('kind')}")
        if source.get("kind") == "metadata_inference" and (interpretation.get("confidence") == "high" or source.get("confidence") == "high"):
            errors.append(f"{summary_path}:metadata_high_confidence")

        shard_path = root / "versions" / f"{version}.json"
        if not shard_path.exists():
            errors.append(f"wuwa:{version}:shard_missing")
            continue
        row = load_json(shard_path)
        if not isinstance(row, dict):
            errors.append(f"wuwa:{version}:shard_not_object")
            continue
        for index, item in enumerate(iter_wuwa_file_items(row), start=1):
            item_path = f"wuwa:{version}:item_{index}"
            errors.extend(validate_availability(item, item_path, adapter))
            item_source = (item.get("availability") or {}).get("source") or {}
            item_interpretation = (item.get("availability") or {}).get("interpretation") or {}
            if item_source.get("kind") not in {"metadata_inference", "live_probe"}:
                errors.append(f"{item_path}:source_kind_not_wuwa_allowed:{item_source.get('kind')}")
            if item_source.get("kind") == "metadata_inference" and (item_interpretation.get("confidence") == "high" or item_source.get("confidence") == "high"):
                errors.append(f"{item_path}:metadata_high_confidence")

        list_sections: list[tuple[str, Any]] = [("files", (row.get("links") or {}).get("files"))]
        for route in row.get("patches") or []:
            if isinstance(route, dict):
                list_sections.append(("patches", route.get("links")))
        for section_name, section in list_sections:
            if not isinstance(section, dict) or not section.get("json"):
                continue
            list_path = wuwa_data_path(root, str(section["json"]))
            if not list_path.exists():
                errors.append(f"wuwa:{version}:{section_name}:list_missing:{list_path}")
                continue
            items = load_json(list_path)
            if not isinstance(items, list):
                errors.append(f"wuwa:{version}:{section_name}:list_not_array")
                continue
            for index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    errors.append(f"wuwa:{version}:{section_name}:list_{index}_not_object")
                    continue
                item_path = f"wuwa:{version}:{section_name}:list_{index}"
                errors.extend(validate_availability(item, item_path, adapter))
                item_source = (item.get("availability") or {}).get("source") or {}
                item_interpretation = (item.get("availability") or {}).get("interpretation") or {}
                if item_source.get("kind") not in {"metadata_inference", "live_probe"}:
                    errors.append(f"{item_path}:source_kind_not_wuwa_allowed:{item_source.get('kind')}")
                if item_source.get("kind") == "metadata_inference" and (item_interpretation.get("confidence") == "high" or item_source.get("confidence") == "high"):
                    errors.append(f"{item_path}:metadata_high_confidence")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arknights-root", type=Path, default=DEFAULT_ARKNIGHTS)
    parser.add_argument("--android-root", type=Path, default=DEFAULT_ANDROID)
    parser.add_argument("--endfield-root", type=Path, default=DEFAULT_ENDFIELD)
    parser.add_argument("--hoyo-root", type=Path, default=DEFAULT_HOYO)
    parser.add_argument("--nte-root", type=Path, default=DEFAULT_NTE)
    parser.add_argument("--p5x-root", type=Path, default=DEFAULT_P5X)
    parser.add_argument("--tof-root", type=Path, default=DEFAULT_TOF)
    parser.add_argument("--wuwa-root", type=Path, default=DEFAULT_WUWA)
    args = parser.parse_args()

    errors = []
    errors.extend(validate_adapter_no_network(ROOT / "adapters"))
    errors.extend(validate_arknights(args.arknights_root))
    errors.extend(validate_android(args.android_root))
    errors.extend(validate_endfield(args.endfield_root))
    errors.extend(validate_hoyo(args.hoyo_root))
    errors.extend(validate_nte(args.nte_root))
    errors.extend(validate_p5x(args.p5x_root))
    errors.extend(validate_tof(args.tof_root))
    errors.extend(validate_wuwa(args.wuwa_root))

    print("Availability validation")
    print(f"arknights_root={args.arknights_root.resolve()}")
    print(f"android_root={args.android_root.resolve()}")
    print(f"endfield_root={args.endfield_root.resolve()}")
    print(f"hoyo_root={args.hoyo_root.resolve()}")
    print(f"nte_root={args.nte_root.resolve()}")
    print(f"p5x_root={args.p5x_root.resolve()}")
    print(f"tof_root={args.tof_root.resolve()}")
    print(f"wuwa_root={args.wuwa_root.resolve()}")
    print(f"errors={len(errors)}")
    if errors:
        print("result=FAIL")
        print("\n".join(errors[:100]))
        raise SystemExit(1)
    print("result=PASS")


if __name__ == "__main__":
    main()
