#!/usr/bin/env python3
"""Regression checks for game-specific Android version parsing."""

from __future__ import annotations

import sync_android_apks as sync


def main() -> None:
    latest_url = "https://ak.hycdn.cn/path/arknights-hg-2751.apk"
    cases = {
        latest_url: "2.7.5.1",
        "https://ak.hycdn.cn/path/arknights-hg-2741.apk": "2.7.4.1",
        "https://ak.hycdn.cn/path/ARKNIGHTS-HG-2441.APK": "2.4.4.1",
    }
    for url, expected in cases.items():
        actual = sync.arknights_version_from_apk_url(url)
        assert actual == expected, f"{url}: expected {expected}, got {actual}"

    assert sync.arknights_version_from_apk_url("https://ak.hycdn.cn/path/arknights.apk") is None
    assert sync.normalize_version("2.7.5.1") == "2.7.5"

    original_endpoints = sync.HYPERGRYPH_APK_ENDPOINTS
    original_resolve = sync.resolve_download_porter_url
    original_manifest = sync.remote_apk_manifest_version_name
    try:
        sync.HYPERGRYPH_APK_ENDPOINTS = [
            {
                "game_id": "arknights",
                "url": "https://ak.hypergryph.com/downloads/android_lastest",
                "channel": "official",
            }
        ]
        sync.resolve_download_porter_url = lambda _url: latest_url
        sync.remote_apk_manifest_version_name = lambda _url, headers=None: "2.7.5"
        discovered = sync.discover_hypergryph_apks()
    finally:
        sync.HYPERGRYPH_APK_ENDPOINTS = original_endpoints
        sync.resolve_download_porter_url = original_resolve
        sync.remote_apk_manifest_version_name = original_manifest

    assert len(discovered) == 1
    assert discovered[0]["version"] == "2.7.5.1"
    print("arknights_four_part_build_versions=PASS")
    print("arknights_discovery_preserves_four_parts=PASS")
    print("generic_three_part_normalization_unchanged=PASS")
    print("result=PASS")


if __name__ == "__main__":
    main()
