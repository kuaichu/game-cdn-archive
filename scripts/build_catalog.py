#!/usr/bin/env python3
"""Build a static catalog from archived NTE capture files."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    capture_summary = read_json(DATA / "nte" / "1.1.5" / "capture-2026-06-04.json")
    verification = read_json(DATA / "nte" / "1.1.5" / "capture-2026-06-04.verify.json")
    reslist_probe = read_json(DATA / "nte" / "reslist-probe.json")

    catalog = {
        "game": {
            "id": "nte",
            "name": "Neverness to Everness",
            "branch": "publish_PC",
            "platform": "Windows",
            "cdn_hosts": [
                "https://yhcdn1.wmupd.com/clientRes",
                "https://yhcdn2.wmupd.com/clientRes",
            ],
        },
        "reslist_entry_template": (
            "https://yhcdn1.wmupd.com/clientRes/publish_PC/"
            "Version/Windows/version/{version}/ResList.bin.zip"
        ),
        "versions": reslist_probe,
        "captures": [
            {
                "version": "1.1.5",
                "captured_at": "2026-06-04",
                "type": "resource-objects",
                "objects": capture_summary["unique_objects"],
                "total_bytes": capture_summary["total_bytes"],
                "total_gb": capture_summary["total_gb"],
                "verified": verification["summary"],
                "files": {
                    "urls": "data/nte/1.1.5/capture-2026-06-04.urls.txt",
                    "aria2": "data/nte/1.1.5/capture-2026-06-04.aria2.txt",
                    "verify": "data/nte/1.1.5/capture-2026-06-04.verify.json",
                },
                "top_largest": capture_summary["top_20_largest"],
            }
        ],
        "notes": [
            "ResList.bin.zip contains packed PatcherXML0 data.",
            "Object URLs are verified with HTTP Range 0-0 requests.",
            "This archive stores URLs and metadata only; no game files are mirrored.",
        ],
    }

    (DATA / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    docs_data = ROOT / "docs" / "data"
    docs_data.mkdir(parents=True, exist_ok=True)
    (docs_data / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
