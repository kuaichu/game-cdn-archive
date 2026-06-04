#!/usr/bin/env python3
"""Build CDN URL lists from decoded NTE ResList/PatchList XML files."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote


DEFAULT_BASE_URL = "https://yhcdn1.wmupd.com/clientRes/publish_PC/Res"


def object_url(base_url: str, object_name: str) -> str:
    return f"{base_url.rstrip('/')}/{object_name[0]}/{object_name}"


def parse_reslist(path: Path, base_url: str) -> list[dict[str, str | int]]:
    root = ET.parse(path).getroot()
    if root.tag != "ResList":
        raise ValueError(f"{path} is not a ResList XML")

    items: list[dict[str, str | int]] = []
    for res in root.findall(".//Res"):
        filename = res.attrib["filename"]
        filesize = int(res.attrib["filesize"])
        md5 = res.attrib["md5"]
        object_name = f"{md5}.{filesize}"
        items.append(
            {
                "filename": filename,
                "filesize": filesize,
                "md5": md5,
                "object": object_name,
                "url": object_url(base_url, object_name),
            }
        )
    return items


def parse_patchlist(path: Path, base_url: str) -> list[dict[str, str | int]]:
    root = ET.parse(path).getroot()
    if root.tag != "PatchList":
        raise ValueError(f"{path} is not a PatchList XML")

    items: list[dict[str, str | int]] = []
    for patch in root.findall(".//Patch"):
        object_name = patch.attrib["patch"]
        size = int(object_name.rsplit(".", 1)[1])
        items.append(
            {
                "oldfile": patch.attrib.get("oldfile", ""),
                "newfile": patch.attrib.get("newfile", ""),
                "patch": object_name,
                "version_hash": patch.attrib.get("v", ""),
                "filesize": size,
                "url": object_url(base_url, object_name),
            }
        )
    return items


def write_urls(items: list[dict[str, str | int]], path: Path) -> None:
    path.write_text("\n".join(str(item["url"]) for item in items) + "\n", encoding="utf-8")


def write_aria2_reslist(items: list[dict[str, str | int]], path: Path, download_dir: str) -> None:
    lines: list[str] = []
    for item in items:
        filename = str(item["filename"]).replace("\\", "/")
        parent = str(Path(filename).parent).replace("\\", "/")
        name = Path(filename).name
        if parent == ".":
            dir_value = download_dir
        else:
            dir_value = f"{download_dir.rstrip('/')}/{parent}"
        lines.append(str(item["url"]))
        lines.append(f"  dir={dir_value}")
        lines.append(f"  out={name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_aria2_objects(items: list[dict[str, str | int]], path: Path, download_dir: str) -> None:
    lines: list[str] = []
    for item in items:
        object_name = str(item.get("object") or item.get("patch"))
        lines.append(str(item["url"]))
        lines.append(f"  dir={download_dir.rstrip('/')}/{object_name[0]}")
        lines.append(f"  out={object_name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build NTE CDN URL lists from decoded XML.")
    parser.add_argument("xml", type=Path)
    parser.add_argument("--kind", choices=["reslist", "patchlist"], default="reslist")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--name", help="Output file prefix. Defaults to XML parent directory name.")
    parser.add_argument("--download-dir", default="downloads")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    name = args.name or args.xml.parent.name

    if args.kind == "reslist":
        items = parse_reslist(args.xml, args.base_url)
        write_aria2_reslist(items, args.out_dir / f"{name}.files.aria2.txt", args.download_dir)
    else:
        items = parse_patchlist(args.xml, args.base_url)
        write_aria2_objects(items, args.out_dir / f"{name}.patches.aria2.txt", args.download_dir)

    write_urls(items, args.out_dir / f"{name}.urls.txt")
    (args.out_dir / f"{name}.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total = sum(int(item["filesize"]) for item in items)
    print(f"{args.xml}: {len(items)} items, {total} bytes")


if __name__ == "__main__":
    main()
