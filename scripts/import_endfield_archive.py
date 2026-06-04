#!/usr/bin/env python3
"""Build compact Endfield static indexes from ak-endfield-api-archive."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit


SOURCE_REPO = "https://github.com/daydreamer-json/ak-endfield-api-archive"
SOURCE_SITE = "https://ak-endfield-api-archive.daydreamer-json.cc/"
OFFICIAL_API = (
    "https://launcher.hypergryph.com/api/game/get_latest"
    "?appcode=6LL0KJuqHBVz33WK&launcher_appcode=abYeZZ16BPluCFyT"
    "&channel=1&sub_channel=1&launcher_sub_channel=1"
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def strip_query(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def filename(url: str) -> str:
    return unquote(Path(urlsplit(url).path).name)


def timestamp(value: str) -> float:
    return datetime.fromisoformat(value).timestamp()


def version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def enrich_file(item: dict, mirrors: dict[str, dict]) -> dict:
    official_url = item["url"]
    match = mirrors.get(strip_query(official_url))
    mirror_url = match.get("mirror") if match else None
    official_available = bool(match.get("origStatus")) if match else True
    preferred_url = official_url if official_available or not mirror_url else mirror_url
    return {
        "name": filename(official_url),
        "size": int(item.get("package_size") or 0),
        "md5": item.get("md5") or "",
        "official_url": official_url,
        "official_available": official_available,
        "mirror_url": mirror_url,
        "preferred_url": preferred_url,
    }


def write_download_lists(
    output_dir: Path, version: str, mode: str, items: list[dict]
) -> dict[str, str]:
    lists_dir = output_dir / "lists"
    lists_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{version}_{mode}"
    urls_path = lists_dir / f"{stem}.urls.txt"
    aria2_path = lists_dir / f"{stem}.aria2.txt"

    urls_path.write_text(
        "\n".join(item["preferred_url"] for item in items) + "\n",
        encoding="utf-8",
    )
    aria2_lines = []
    for item in items:
        aria2_lines.extend(
            [
                item["preferred_url"],
                f"  out={item['name']}",
                f"  checksum=md5={item['md5']}",
                "",
            ]
        )
    aria2_path.write_text("\n".join(aria2_lines), encoding="utf-8")
    prefix = "data/endfield/lists"
    return {
        "urls": f"{prefix}/{urls_path.name}",
        "aria2": f"{prefix}/{aria2_path.name}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive_root", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "data" / "endfield",
    )
    args = parser.parse_args()

    game_dir = args.archive_root / "output" / "akEndfield" / "launcher" / "game" / "1"
    full_records = load_json(game_dir / "all.json")
    patch_records = load_json(game_dir / "all_patch.json")
    mirror_records = load_json(args.archive_root / "output" / "mirror_file_list.json")
    mirrors = {item["orig"]: item for item in mirror_records}

    full_by_version: dict[str, dict] = {}
    released_at: dict[str, str] = {}
    for record in full_records:
        version = record["rsp"]["version"]
        current_release = released_at.get(version)
        if current_release is None or timestamp(record["updatedAt"]) < timestamp(current_release):
            released_at[version] = record["updatedAt"]
        if (
            version not in full_by_version
            or timestamp(record["updatedAt"]) > timestamp(full_by_version[version]["updatedAt"])
        ):
            full_by_version[version] = record

    patch_by_route: dict[tuple[str, str], dict] = {}
    patch_released_at: dict[tuple[str, str], str] = {}
    for record in patch_records:
        route = (record["rsp"]["request_version"], record["rsp"]["version"])
        current_release = patch_released_at.get(route)
        if current_release is None or timestamp(record["updatedAt"]) < timestamp(current_release):
            patch_released_at[route] = record["updatedAt"]
        if route not in patch_by_route or timestamp(record["updatedAt"]) > timestamp(
            patch_by_route[route]["updatedAt"]
        ):
            patch_by_route[route] = record

    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    versions: dict[str, dict] = {}
    summaries = []

    for version in sorted(full_by_version, key=version_key, reverse=True):
        record = full_by_version[version]
        pkg = record["rsp"]["pkg"]
        packages = [enrich_file(item, mirrors) for item in pkg.get("packs", [])]
        routes = []
        flat_patch_parts = []
        matching_routes = [
            (route, patch_by_route[route])
            for route in patch_by_route
            if route[1] == version
        ]
        for (from_version, to_version), patch_record in sorted(
            matching_routes, key=lambda item: version_key(item[0][0]), reverse=True
        ):
            patch = patch_record["rsp"].get("patch") or {}
            parts = [enrich_file(item, mirrors) for item in patch.get("patches", [])]
            for part in parts:
                part["route"] = f"{from_version} -> {to_version}"
            flat_patch_parts.extend(parts)
            routes.append(
                {
                    "from": from_version,
                    "to": to_version,
                    "released_at": patch_released_at[(from_version, to_version)],
                    "size": int(patch.get("package_size") or 0),
                    "unpacked_size": int(patch.get("total_size") or 0),
                    "md5": patch.get("md5") or "",
                    "parts": parts,
                }
            )

        links = {
            "packages": write_download_lists(output_dir, version, "packages", packages),
            "patches": write_download_lists(output_dir, version, "patches", flat_patch_parts)
            if flat_patch_parts
            else None,
        }
        packed_size = sum(item["size"] for item in packages)
        mirror_items = sum(bool(item["mirror_url"]) for item in packages)
        versions[version] = {
            "version": version,
            "released_at": released_at[version],
            "observed_at": record["updatedAt"],
            "packed_size": packed_size,
            "unpacked_size": int(pkg.get("total_size") or 0),
            "file_path": pkg.get("file_path") or "",
            "packages": packages,
            "patches": routes,
            "links": links,
        }
        summaries.append(
            {
                "version": version,
                "released_at": released_at[version],
                "package_items": len(packages),
                "patch_routes": len(routes),
                "packed_size": packed_size,
                "unpacked_size": int(pkg.get("total_size") or 0),
                "mirror_items": mirror_items,
            }
        )

    latest_observation = max(
        [record["updatedAt"] for record in full_records + patch_records],
        key=timestamp,
    )
    index = {
        "source": SOURCE_REPO,
        "source_site": SOURCE_SITE,
        "official_api": OFFICIAL_API,
        "generated_from_observation": latest_observation,
        "game": {
            "id": "endfield",
            "name": "明日方舟：终末地",
            "subName": "Arknights: Endfield",
            "shortName": "EF",
            "icon": "assets/icons/endfield.svg",
            "kind": "endfield",
        },
        "versions": summaries,
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "versions.json").write_text(
        json.dumps(versions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(versions)} versions and {len(patch_by_route)} patch routes "
        f"to {output_dir}"
    )


if __name__ == "__main__":
    main()
