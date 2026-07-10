#!/usr/bin/env python3
"""Negative-path checks for the availability migration."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch


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
from adapters.tof import TofAvailabilityAdapter  # noqa: E402
from adapters.wuwa import WuwaAvailabilityAdapter  # noqa: E402
from scripts.availability_schema import ProbeResult, availability_block, probe_fact_defaults  # noqa: E402
from scripts.build_android_availability import protect_known_good_interpretation, stabilize_recovery_interpretation, write_linked_json_lists  # noqa: E402
from scripts.build_wuwa_availability import apply_availability, load_versions  # noqa: E402
from scripts.probe_scheduler import PersistentProbeCache, ProbeScheduleConfig, should_probe_previous  # noqa: E402
from scripts.validate_availability import validate_android, validate_arknights, validate_endfield, validate_hoyo, validate_nte, validate_tof, validate_wuwa  # noqa: E402


ARKNIGHTS_ROOT = ROOT / "docs" / "data" / "arknights"
TEST_CHECKED_AT = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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
            checked_at=TEST_CHECKED_AT,
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
    bot_challenge: bool = False,
) -> ProbeResult:
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=status,
            method="HEAD",
            checked_at=TEST_CHECKED_AT,
            final_url=url,
            content_type=content_type,
            size=size,
            error=error,
            bot_challenge=bot_challenge,
            stale=False,
            scheduler_confidence="high",
        ),
    }


def hoyo_metadata_probe(url: str, *, size: int, ok: bool = True, error: str = "") -> ProbeResult:
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=0,
            method="METADATA_SIZE",
            checked_at=TEST_CHECKED_AT,
            final_url=url,
            content_type="",
            size=size,
            error=error,
            stale=False,
            scheduler_confidence="medium" if ok else "low",
        ),
    }


def endfield_upstream_probe(url: str, *, ok: bool, size: int = 1024, error: str = "") -> ProbeResult:
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=0,
            method="UPSTREAM_ARCHIVE",
            checked_at=TEST_CHECKED_AT,
            final_url=url,
            content_type="",
            size=size,
            error=error,
            stale=False,
            scheduler_confidence="medium",
        ),
    }


def nte_live_probe(url: str, *, ok: bool, status: int, size: int = 0, error: str = "") -> ProbeResult:
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=status,
            method="GET",
            checked_at=TEST_CHECKED_AT,
            final_url=url,
            content_type="application/zip" if ok else "",
            size=size,
            error=error,
            stale=False,
            scheduler_confidence="high" if status else "low",
        ),
    }


def nte_metadata_probe(url: str, *, size: int, ok: bool = True) -> ProbeResult:
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=0,
            method="RESLIST_METADATA",
            checked_at=TEST_CHECKED_AT,
            final_url=url,
            content_type="",
            size=size,
            error="" if ok else "size_zero",
            stale=False,
            scheduler_confidence="medium" if ok else "low",
        ),
    }


def wuwa_metadata_probe(url: str, *, size: int, ok: bool = True, error: str = "") -> ProbeResult:
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=0,
            method="WUWA_METADATA",
            checked_at=TEST_CHECKED_AT,
            final_url=url,
            content_type="",
            size=size,
            error=error,
            stale=False,
            scheduler_confidence="medium" if ok else "low",
        ),
    }


def wuwa_live_probe(url: str, *, ok: bool, status: int, size: int = 1024, error: str = "", method: str = "HEAD") -> ProbeResult:
    return {
        "url": url,
        "probe": probe_fact_defaults(
            ok=ok,
            status=status,
            method=method,
            checked_at=TEST_CHECKED_AT,
            final_url=url,
            content_type="application/octet-stream" if ok else "",
            size=size,
            error=error,
            stale=False,
            scheduler_confidence="high" if ok else "low",
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
    if result_non_apk["state"] != "unknown" or result_non_apk["reason"] != "content_type_mismatch":
        raise AssertionError(f"unexpected Android non-APK interpretation: {result_non_apk!r}")

    result_bot_challenge = adapter.interpret([
        android_probe(
            url,
            ok=False,
            status=200,
            content_type="text/html",
            size=2660,
            error="HTTP 200",
            bot_challenge=True,
        )
    ], {"game_id": "android-test", "version": "1.0.0", "url": url, "filename": "game.apk"})
    if result_bot_challenge["state"] != "unknown" or result_bot_challenge["reason"] != "bot_challenge":
        raise AssertionError(f"unexpected Android bot-challenge interpretation: {result_bot_challenge!r}")

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

    result_fake_range = adapter.interpret([
        android_probe(url, ok=True, status=206, content_type="text/plain", size=3)
    ], {"game_id": "android-test", "version": "1.0.0", "url": url, "filename": "game.apk"})
    if result_fake_range != expected_fake_200:
        raise AssertionError(f"unexpected Android fake range interpretation: {result_fake_range!r}")

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

    historical_record = {
        "game_id": "android-test",
        "version": "0.9.0",
        "url": url,
        "filename": "game.apk",
        "captured_at": "2026-01-01T00:00:00Z",
        "source": "Wayback Machine historical URL",
    }
    result_historical_403 = adapter.interpret([
        android_probe(url, ok=False, status=403, content_type="application/xml", size=334, error="HTTP 403")
    ], historical_record)
    if result_historical_403["state"] != "unknown" or result_historical_403["reason"] != "http_403":
        raise AssertionError(f"unexpected Android historical 403 interpretation: {result_historical_403!r}")

    result_historical_dns = adapter.interpret([
        android_probe(url, ok=False, status=0, content_type="", size=0, error="dns: getaddrinfo failed")
    ], historical_record)
    if result_historical_dns["state"] != "unknown" or result_historical_dns["reason"] != "dns_error":
        raise AssertionError(f"unexpected Android historical DNS interpretation: {result_historical_dns!r}")


def assert_android_known_good_conflict_protection() -> None:
    url = "https://example.invalid/game.apk"
    record = {
        "game_id": "android-test",
        "version": "1.0.0",
        "url": url,
        "filename": "game.apk",
        "status": 200,
        "content_type": "application/vnd.android.package-archive",
        "size": 2 * 1024 * 1024 * 1024,
        "error": "",
    }
    tiny_probe = android_probe(url, ok=True, status=206, content_type="text/plain", size=3)
    interpretation = AndroidAvailabilityAdapter().interpret([tiny_probe], record)
    protected = protect_known_good_interpretation(record, [tiny_probe], interpretation)
    if protected["state"] != "unknown" or protected["reason"] != "content_type_mismatch":
        raise AssertionError(f"known-good APK conflict was not protected: {protected!r}")

    missing_probe = android_probe(url, ok=False, status=404, content_type="application/xml", size=0, error="HTTP 404")
    missing_interpretation = AndroidAvailabilityAdapter().interpret([missing_probe], record)
    missing_result = protect_known_good_interpretation(record, [missing_probe], missing_interpretation)
    if missing_result != missing_interpretation:
        raise AssertionError(f"definitive 404 must not be conflict-protected: {missing_result!r}")


def assert_android_failed_probe_ttl() -> None:
    with patch.dict(os.environ, {
        "ANDROID_APK_REPROBE_TTL_HOURS": "20",
        "ANDROID_APK_FAILED_REPROBE_TTL_HOURS": "",
    }):
        config = ProbeScheduleConfig.android_apks_from_env()
    if config.ttl_hours != 20 or config.failed_ttl_hours != 4:
        raise AssertionError(f"unexpected Android probe TTL config: {config!r}")

    now = datetime.now(timezone.utc)
    checked_at = (now - timedelta(hours=5)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    failed = android_probe(
        "https://example.invalid/game.apk",
        ok=False,
        status=403,
        content_type="application/xml",
        size=334,
        error="HTTP 403",
    )
    failed["probe"]["checked_at"] = checked_at
    if not should_probe_previous(failed, now, config):
        raise AssertionError("five-hour-old Android failure must be reprobed")

    successful = deepcopy(failed)
    successful["probe"]["ok"] = True
    successful["probe"]["status"] = 206
    successful["probe"]["error"] = ""
    if should_probe_previous(successful, now, config):
        raise AssertionError("five-hour-old Android success must remain cached")


def assert_android_linked_list_sync() -> None:
    index = valid_android_index()
    game = index["games"]["android-test"]
    game["links"] = {
        "1.0.0": {
            "json": "data/android/lists/android-test_1.0.0_android.json",
        }
    }
    with tempfile.TemporaryDirectory(prefix="android-linked-list-") as temp:
        root = Path(temp)
        stale = deepcopy(game["versions"])
        stale[0].pop("availability", None)
        list_path = root / "lists" / "android-test_1.0.0_android.json"
        list_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(list_path, stale)
        write_linked_json_lists(root, index)
        updated = load_json(list_path)
    if updated != game["versions"]:
        raise AssertionError(f"Android linked JSON list did not receive updated availability: {updated!r}")


def assert_android_recovery_stability() -> None:
    url = "https://example.invalid/game.apk"
    previous_probe = android_probe(
        url,
        ok=False,
        status=403,
        content_type="application/xml",
        size=334,
        error="HTTP 403",
    )
    record = {
        "game_id": "android-test",
        "version": "1.0.0",
        "url": url,
        "filename": "game.apk",
        "status": 404,
        "content_type": "application/xml",
        "size": 0,
        "error": "APK object unavailable",
        "availability": availability_block(
            [previous_probe],
            "live_probe",
            {
                "state": "unknown",
                "reason": "http_403",
                "preferred_url": "",
                "confidence": "low",
                "retained": False,
                "display_label": "状态未知",
            },
            "scripts/test_availability_negative.py",
        ),
    }
    current_probe = android_probe(
        url,
        ok=True,
        status=206,
        content_type="application/vnd.android.package-archive",
        size=2 * 1024 * 1024 * 1024,
    )
    available = AndroidAvailabilityAdapter().interpret([current_probe], record)
    first_success = stabilize_recovery_interpretation(record, [current_probe], available)
    if first_success["state"] != "unknown" or first_success["reason"] != available["reason"]:
        raise AssertionError(f"first recovery success must remain provisional: {first_success!r}")

    record["availability"] = availability_block(
        [current_probe],
        "live_probe",
        first_success,
        "scripts/test_availability_negative.py",
    )
    second_success = stabilize_recovery_interpretation(record, [current_probe], available)
    if second_success != available:
        raise AssertionError(f"second consecutive recovery success must become available: {second_success!r}")

    known_good = dict(record)
    known_good.update({
        "status": 200,
        "content_type": "application/vnd.android.package-archive",
        "size": 2 * 1024 * 1024 * 1024,
        "error": "",
        "availability": availability_block(
            [previous_probe],
            "live_probe",
            first_success,
            "scripts/test_availability_negative.py",
        ),
    })
    immediate = stabilize_recovery_interpretation(known_good, [current_probe], available)
    if immediate != available:
        raise AssertionError(f"known-good APK metadata must allow immediate recovery: {immediate!r}")


def assert_hoyo_metadata_paths() -> None:
    adapter = HoyoAvailabilityAdapter()
    url = "https://example.invalid/YuanShen_1.0.0.zip"

    zero_record = {"name": "YuanShen_1.0.0.zip", "url": url, "size": 0}
    zero_probe = hoyo_metadata_probe(url, size=0, ok=False, error="size_zero")
    zero_result = adapter.interpret([zero_probe], zero_record)
    expected_zero = {
        "state": "unavailable",
        "reason": "size_zero",
        "preferred_url": "",
        "confidence": "low",
        "retained": False,
        "display_label": "链接失效",
    }
    if zero_result != expected_zero:
        raise AssertionError(f"unexpected HoYo size-zero interpretation: {zero_result!r}")
    zero_record["availability"] = availability_block([zero_probe], "metadata_inference", zero_result, "scripts/test_availability_negative.py")
    if zero_record["availability"]["source"]["kind"] != "metadata_inference":
        raise AssertionError(f"unexpected HoYo source kind: {zero_record['availability']!r}")
    if zero_record["availability"]["source"]["confidence"] == "high":
        raise AssertionError(f"HoYo metadata inference must not use high confidence: {zero_record['availability']!r}")

    valid_record = {"name": "YuanShen_1.0.0.zip", "url": url, "size": 2 * 1024 * 1024}
    valid_probe = hoyo_metadata_probe(url, size=2 * 1024 * 1024)
    valid_result = adapter.interpret([valid_probe], valid_record)
    expected_valid = {
        "state": "available",
        "reason": "not_probed",
        "preferred_url": url,
        "confidence": "medium",
        "retained": False,
        "display_label": "可用",
    }
    if valid_result != expected_valid:
        raise AssertionError(f"unexpected HoYo valid interpretation: {valid_result!r}")


def assert_endfield_upstream_paths() -> None:
    adapter = EndfieldAvailabilityAdapter()
    official_url = "https://example.invalid/official.zip.001"
    mirror_url = "https://github.com/example/archive/releases/download/pkg/official.zip.001"

    mirror_record = {
        "name": "official.zip.001",
        "size": 1024,
        "official_url": official_url,
        "official_available": False,
        "mirror_url": mirror_url,
        "preferred_url": mirror_url,
    }
    mirror_result = adapter.interpret([
        endfield_upstream_probe(official_url, ok=False, error="upstream_marked_unavailable"),
        endfield_upstream_probe(mirror_url, ok=True, error="mirror_fallback"),
    ], mirror_record)
    expected_mirror = {
        "state": "mirror_only",
        "reason": "mirror_fallback",
        "preferred_url": mirror_url,
        "confidence": "medium",
        "retained": False,
        "display_label": "镜像可用",
    }
    if mirror_result != expected_mirror:
        raise AssertionError(f"unexpected Endfield mirror interpretation: {mirror_result!r}")
    mirror_record["availability"] = availability_block(
        [
            endfield_upstream_probe(official_url, ok=False, error="upstream_marked_unavailable"),
            endfield_upstream_probe(mirror_url, ok=True, error="mirror_fallback"),
        ],
        "upstream_archive",
        mirror_result,
        "scripts/test_availability_negative.py",
    )
    if mirror_record["availability"]["source"]["kind"] != "upstream_archive":
        raise AssertionError(f"unexpected Endfield source kind: {mirror_record['availability']!r}")
    if mirror_record["availability"]["source"]["confidence"] == "high":
        raise AssertionError(f"Endfield upstream archive must not use high confidence: {mirror_record['availability']!r}")

    official_record = {
        "name": "official.zip.001",
        "size": 1024,
        "official_url": official_url,
        "official_available": True,
        "preferred_url": official_url,
    }
    official_result = adapter.interpret([endfield_upstream_probe(official_url, ok=True)], official_record)
    expected_official = {
        "state": "available",
        "reason": "not_probed",
        "preferred_url": official_url,
        "confidence": "medium",
        "retained": False,
        "display_label": "可用",
    }
    if official_result != expected_official:
        raise AssertionError(f"unexpected Endfield official interpretation: {official_result!r}")


def assert_nte_paths() -> None:
    adapter = NteAvailabilityAdapter()
    reslist_url = "https://yhcdn1.wmupd.com/clientRes/publish_PC/Version/Windows/version/1.0.2/ResList.bin.zip"
    object_url = "https://yhcdn1.wmupd.com/clientRes/publish_PC/Res/a/abc.1024"

    missing_record = {"version": "1.0.2", "status": 404, "reslist_url": reslist_url}
    missing_result = adapter.interpret([
        nte_live_probe(reslist_url, ok=False, status=404, size=488, error="HTTP 404")
    ], missing_record)
    expected_missing = {
        "state": "unavailable",
        "reason": "http_404",
        "preferred_url": "",
        "confidence": "high",
        "retained": False,
        "display_label": "链接失效",
    }
    if missing_result != expected_missing:
        raise AssertionError(f"unexpected NTE missing ResList interpretation: {missing_result!r}")
    missing_record["availability"] = availability_block(
        [nte_live_probe(reslist_url, ok=False, status=404, size=488, error="HTTP 404")],
        "live_probe",
        missing_result,
        "scripts/test_availability_negative.py",
    )
    if missing_record["availability"]["source"]["kind"] != "live_probe":
        raise AssertionError(f"unexpected NTE ResList source kind: {missing_record['availability']!r}")

    object_record = {
        "filename": "Client/Test.bin",
        "filesize": 1024,
        "md5": "abc",
        "object": "abc.1024",
        "url": object_url,
    }
    object_result = adapter.interpret([nte_metadata_probe(object_url, size=1024)], object_record)
    expected_object = {
        "state": "available",
        "reason": "not_probed",
        "preferred_url": object_url,
        "confidence": "medium",
        "retained": False,
        "display_label": "可用",
    }
    if object_result != expected_object:
        raise AssertionError(f"unexpected NTE object interpretation: {object_result!r}")
    object_record["availability"] = availability_block(
        [nte_metadata_probe(object_url, size=1024)],
        "metadata_inference",
        object_result,
        "scripts/test_availability_negative.py",
    )
    if object_record["availability"]["source"]["kind"] != "metadata_inference":
        raise AssertionError(f"unexpected NTE object source kind: {object_record['availability']!r}")
    if object_record["availability"]["source"]["confidence"] == "high":
        raise AssertionError(f"NTE object metadata inference must not use high confidence: {object_record['availability']!r}")


def assert_tof_paths() -> None:
    adapter = TofAvailabilityAdapter()
    reslist_url = "https://htcdn1.wmupd.com/clientRes/Windows55/Version/Windows/version/6.2.2/ResList.bin.zip"
    object_url = "https://htcdn1.wmupd.com/clientRes/Windows55/Res/a/abc.1024"

    missing_record = {"version": "6.2.2", "status": 404, "reslist_url": reslist_url}
    missing_result = adapter.interpret([
        nte_live_probe(reslist_url, ok=False, status=404, size=488, error="HTTP 404")
    ], missing_record)
    expected_missing = {
        "state": "unavailable",
        "reason": "http_404",
        "preferred_url": "",
        "confidence": "high",
        "retained": False,
        "display_label": "链接失效",
    }
    if missing_result != expected_missing:
        raise AssertionError(f"unexpected TOF missing ResList interpretation: {missing_result!r}")

    object_record = {
        "filename": "Client/Test.bin",
        "filesize": 1024,
        "md5": "abc",
        "object": "abc.1024",
        "url": object_url,
    }
    object_result = adapter.interpret([nte_metadata_probe(object_url, size=1024)], object_record)
    expected_object = {
        "state": "available",
        "reason": "not_probed",
        "preferred_url": object_url,
        "confidence": "medium",
        "retained": False,
        "display_label": "可用",
    }
    if object_result != expected_object:
        raise AssertionError(f"unexpected TOF object interpretation: {object_result!r}")


def assert_wuwa_metadata_paths() -> None:
    adapter = WuwaAvailabilityAdapter()
    primary_url = "https://pcdownload-aliyun.aki-game.com/game/invalid.pak"
    fallback_url = "https://pcdownload-huoshan.aki-game.com/game/valid.pak"
    record = {
        "dest": "Client/Content/Paks/chunk.pak",
        "name": "chunk.pak",
        "md5": "abc",
        "size": 1024,
        "url": primary_url,
        "urls": [primary_url, fallback_url],
    }
    fallback_result = adapter.interpret(
        [
            wuwa_metadata_probe(primary_url, size=1024, ok=False, error="not_probed"),
            wuwa_metadata_probe(fallback_url, size=1024, ok=True),
        ],
        record,
    )
    expected_fallback = {
        "state": "available",
        "reason": "multi_cdn_preferred",
        "preferred_url": fallback_url,
        "confidence": "medium",
        "retained": False,
        "display_label": "可用",
    }
    if fallback_result != expected_fallback:
        raise AssertionError(f"unexpected WuWa fallback interpretation: {fallback_result!r}")
    record["availability"] = availability_block(
        [
            wuwa_metadata_probe(primary_url, size=1024, ok=False, error="not_probed"),
            wuwa_metadata_probe(fallback_url, size=1024, ok=True),
        ],
        "metadata_inference",
        fallback_result,
        "scripts/test_availability_negative.py",
    )
    if record["availability"]["source"]["kind"] != "metadata_inference":
        raise AssertionError(f"unexpected WuWa source kind: {record['availability']!r}")
    if record["availability"]["source"]["confidence"] == "high":
        raise AssertionError(f"WuWa metadata inference must not use high confidence: {record['availability']!r}")

    dead_record = {
        "dest": "Client/Content/Paks/dead.pak",
        "name": "dead.pak",
        "md5": "def",
        "size": 0,
        "url": primary_url,
        "urls": [primary_url, fallback_url],
    }
    dead_result = adapter.interpret(
        [
            wuwa_metadata_probe(primary_url, size=0, ok=False, error="size_zero"),
            wuwa_metadata_probe(fallback_url, size=0, ok=False, error="size_zero"),
        ],
        dead_record,
    )
    expected_dead = {
        "state": "unavailable",
        "reason": "size_zero",
        "preferred_url": "",
        "confidence": "low",
        "retained": False,
        "display_label": "链接失效",
    }
    if dead_result != expected_dead:
        raise AssertionError(f"unexpected WuWa all-dead interpretation: {dead_result!r}")

    live_result = adapter.interpret(
        [
            wuwa_live_probe(primary_url, ok=False, status=404, size=0, error="HTTP 404"),
            wuwa_live_probe(fallback_url, ok=True, status=200, size=1024),
        ],
        record,
    )
    expected_live = {
        "state": "available",
        "reason": "multi_cdn_preferred",
        "preferred_url": fallback_url,
        "confidence": "high",
        "retained": False,
        "display_label": "可用",
    }
    if live_result != expected_live:
        raise AssertionError(f"unexpected WuWa live fallback interpretation: {live_result!r}")
    live_record = deepcopy(record)
    live_record["availability"] = availability_block(
        [
            wuwa_live_probe(primary_url, ok=False, status=404, size=0, error="HTTP 404"),
            wuwa_live_probe(fallback_url, ok=True, status=200, size=1024),
        ],
        "live_probe",
        live_result,
        "scripts/test_availability_negative.py",
    )
    if live_record["availability"]["source"]["kind"] != "live_probe":
        raise AssertionError(f"unexpected WuWa live source kind: {live_record['availability']!r}")

    all_failed_result = adapter.interpret(
        [
            wuwa_live_probe(primary_url, ok=False, status=404, size=0, error="HTTP 404"),
            wuwa_live_probe(fallback_url, ok=False, status=0, size=0, error="timeout"),
        ],
        record,
    )
    expected_all_failed = {
        "state": "unavailable",
        "reason": "http_404",
        "preferred_url": "",
        "confidence": "low",
        "retained": False,
        "display_label": "链接失效",
    }
    if all_failed_result != expected_all_failed:
        raise AssertionError(f"unexpected WuWa live all-failed interpretation: {all_failed_result!r}")


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


def valid_hoyo_root(root: Path) -> None:
    game_id = "hoyo-test"
    version = "1.0.0"
    url = "https://example.invalid/YuanShen_1.0.0.zip"
    item = {
        "name": "YuanShen_1.0.0.zip",
        "url": url,
        "checksum": "",
        "size": 2 * 1024 * 1024,
    }
    item_probe = hoyo_metadata_probe(url, size=2 * 1024 * 1024)
    item_interpretation = HoyoAvailabilityAdapter().interpret([item_probe], item)
    item["availability"] = availability_block(
        [item_probe],
        "metadata_inference",
        item_interpretation,
        "scripts/test_availability_negative.py",
    )

    summary = {
        "version": version,
        "package_items": 1,
        "update_items": 0,
        "direct_bytes": item["size"],
        "has_chunk": False,
        "has_decompressed_path": False,
        "unavailable_items": 0,
    }
    summary_interpretation = HoyoAvailabilityAdapter().interpret([item_probe], summary)
    summary["availability"] = availability_block(
        [item_probe],
        "metadata_inference",
        summary_interpretation,
        "scripts/test_availability_negative.py",
    )
    summary["availability_counts"] = {"available": 1}

    write_json(root / "games.json", {
        "games": [{
            "id": game_id,
            "name": "HoYo Test",
            "versions": [summary],
        }]
    })
    shard = {
        "version": version,
        "game": {"full": item},
        "voice": {},
        "update": {},
        "chunk": None,
    }
    shard_path = root / "versions" / game_id / f"{version}.json"
    shard_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(shard_path, shard)


def mutate_hoyo_item(root: Path, path_parts: tuple[str, ...], value: Any) -> None:
    valid_hoyo_root(root)
    shard_path = root / "versions" / "hoyo-test" / "1.0.0.json"
    shard = load_json(shard_path)
    target: Any = shard["game"]["full"]
    for part in path_parts[:-1]:
        target = target[part]
    target[path_parts[-1]] = value
    write_json(shard_path, shard)


def assert_hoyo_validator_rejects(path_parts: tuple[str, ...], value: Any, expected_token: str) -> None:
    with tempfile.TemporaryDirectory(prefix="hoyo-availability-negative-") as temp:
        temp_root = Path(temp)
        mutate_hoyo_item(temp_root, path_parts, value)
        errors = validate_hoyo(temp_root)
    if not any(expected_token in error for error in errors):
        raise AssertionError(f"HoYo validator did not reject {'.'.join(path_parts)}={value!r}; errors={errors!r}")


def valid_endfield_root(root: Path) -> None:
    version = "1.0.0"
    official_url = "https://example.invalid/official.zip.001"
    item = {
        "name": "official.zip.001",
        "size": 1024,
        "md5": "",
        "official_url": official_url,
        "official_available": True,
        "preferred_url": official_url,
    }
    probe = endfield_upstream_probe(official_url, ok=True)
    interpretation = EndfieldAvailabilityAdapter().interpret([probe], item)
    item["availability"] = availability_block(
        [probe],
        "upstream_archive",
        interpretation,
        "scripts/test_availability_negative.py",
    )
    summary_probe = endfield_upstream_probe(f"endfield-upstream://{version}", ok=False, size=0, error="not_probed")
    summary = {
        "version": version,
        "package_items": 1,
        "patch_routes": 0,
        "packed_size": 1024,
        "unpacked_size": 0,
        "mirror_items": 0,
        "availability_counts": {"available": 1},
        "availability_reasons": {"not_probed": 1},
    }
    summary_interpretation = EndfieldAvailabilityAdapter().interpret([summary_probe], summary)
    summary["availability"] = availability_block(
        [summary_probe],
        "upstream_archive",
        summary_interpretation,
        "scripts/test_availability_negative.py",
    )

    write_json(root / "index.json", {"versions": [summary]})
    write_json(root / "versions.json", {
        version: {
            "version": version,
            "packages": [item],
            "patches": [],
            "availability_counts": {"available": 1},
            "availability_reasons": {"not_probed": 1},
        }
    })


def mutate_endfield_item(root: Path, path_parts: tuple[str, ...], value: Any) -> None:
    valid_endfield_root(root)
    versions_path = root / "versions.json"
    versions = load_json(versions_path)
    target: Any = versions["1.0.0"]["packages"][0]
    for part in path_parts[:-1]:
        target = target[part]
    target[path_parts[-1]] = value
    write_json(versions_path, versions)


def assert_endfield_validator_rejects(path_parts: tuple[str, ...], value: Any, expected_token: str) -> None:
    with tempfile.TemporaryDirectory(prefix="endfield-availability-negative-") as temp:
        temp_root = Path(temp)
        mutate_endfield_item(temp_root, path_parts, value)
        errors = validate_endfield(temp_root)
    if not any(expected_token in error for error in errors):
        raise AssertionError(f"Endfield validator did not reject {'.'.join(path_parts)}={value!r}; errors={errors!r}")


def valid_nte_root(root: Path) -> None:
    version = "1.0.0"
    reslist_url = "https://yhcdn1.wmupd.com/clientRes/publish_PC/Version/Windows/version/1.0.0/ResList.bin.zip"
    object_url = "https://yhcdn1.wmupd.com/clientRes/publish_PC/Res/a/abc.1024"
    item = {
        "filename": "Client/Test.bin",
        "filesize": 1024,
        "md5": "abc",
        "object": "abc.1024",
        "url": object_url,
    }
    item_probe = nte_metadata_probe(object_url, size=1024)
    item_interpretation = NteAvailabilityAdapter().interpret([item_probe], item)
    item["availability"] = availability_block(
        [item_probe],
        "metadata_inference",
        item_interpretation,
        "scripts/test_availability_negative.py",
    )

    row = {
        "version": version,
        "release_type": "major",
        "status": 200,
        "reslist_url": reslist_url,
        "last_modified": "Mon, 06 Jul 2026 00:00:00 GMT",
        "reslist_bytes": 1024,
        "full": {
            "items": 1,
            "bytes": 1024,
            "json": "data/url_lists/1.0.0-full.json",
            "urls": "data/url_lists/1.0.0-full.urls.txt",
            "aria2": "data/url_lists/1.0.0-full.files.aria2.txt",
        },
        "patches": {
            "items": 0,
            "bytes": 0,
            "json": "data/url_lists/1.0.0-patches.json",
            "urls": "data/url_lists/1.0.0-patches.urls.txt",
            "aria2": "data/url_lists/1.0.0-patches.patches.aria2.txt",
        },
    }
    row_probe = nte_live_probe(reslist_url, ok=True, status=200, size=1024)
    row_interpretation = NteAvailabilityAdapter().interpret([row_probe], row)
    row["availability"] = availability_block(
        [row_probe],
        "live_probe",
        row_interpretation,
        "scripts/test_availability_negative.py",
    )
    row["availability_counts"] = {"full": {"available": 1}, "patches": {}}
    row["availability_reasons"] = {"full": {"not_probed": 1}, "patches": {}}

    write_json(root / "catalog.json", {"versions": [row]})
    list_dir = root / "url_lists"
    list_dir.mkdir(parents=True, exist_ok=True)
    write_json(list_dir / "1.0.0-full.json", [item])
    write_json(list_dir / "1.0.0-patches.json", [])


def mutate_nte_item(root: Path, path_parts: tuple[str, ...], value: Any) -> None:
    valid_nte_root(root)
    shard_path = root / "url_lists" / "1.0.0-full.json"
    items = load_json(shard_path)
    target: Any = items[0]
    for part in path_parts[:-1]:
        target = target[part]
    target[path_parts[-1]] = value
    write_json(shard_path, items)


def assert_nte_validator_rejects(path_parts: tuple[str, ...], value: Any, expected_token: str) -> None:
    with tempfile.TemporaryDirectory(prefix="nte-availability-negative-") as temp:
        temp_root = Path(temp)
        mutate_nte_item(temp_root, path_parts, value)
        errors = validate_nte(temp_root)
    if not any(expected_token in error for error in errors):
        raise AssertionError(f"NTE validator did not reject {'.'.join(path_parts)}={value!r}; errors={errors!r}")


def assert_nte_release_type_validator() -> None:
    with tempfile.TemporaryDirectory(prefix="nte-release-type-negative-") as temp:
        temp_root = Path(temp)
        valid_nte_root(temp_root)
        catalog_path = temp_root / "catalog.json"
        catalog = load_json(catalog_path)
        base_row = catalog["versions"][0]
        first_row = deepcopy(base_row)
        first_row["version"] = "1.2.5"
        first_row["release_type"] = "patch"
        second_row = deepcopy(base_row)
        second_row["version"] = "1.2.6"
        second_row["release_type"] = "major"
        catalog["versions"] = [first_row, second_row]
        write_json(catalog_path, catalog)
        errors = validate_nte(temp_root)
    expected = "nte:1.2:release_type_major_not_min:1.2.6!=1.2.5"
    if expected not in errors:
        raise AssertionError(f"NTE validator did not reject wrong major release; errors={errors!r}")


def valid_tof_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    version = "6.2.2"
    reslist_url = "https://htcdn1.wmupd.com/clientRes/Windows55/Version/Windows/version/6.2.2/ResList.bin.zip"
    object_url = "https://htcdn1.wmupd.com/clientRes/Windows55/Res/a/abc.1024"
    item = {
        "filename": "Client/Test.bin",
        "filesize": 1024,
        "md5": "abc",
        "object": "abc.1024",
        "url": object_url,
    }
    item_probe = nte_metadata_probe(object_url, size=1024)
    item_interpretation = TofAvailabilityAdapter().interpret([item_probe], item)
    item["availability"] = availability_block(
        [item_probe],
        "metadata_inference",
        item_interpretation,
        "scripts/test_availability_negative.py",
    )

    row = {
        "version": version,
        "status": 200,
        "reslist_url": reslist_url,
        "last_modified": "Mon, 06 Jul 2026 00:00:00 GMT",
        "reslist_bytes": 1024,
        "full": {
            "items": 1,
            "bytes": 1024,
            "json": "data/tof/url_lists/6.2.2-full.json",
            "urls": "data/tof/url_lists/6.2.2-full.urls.txt",
            "aria2": "data/tof/url_lists/6.2.2-full.files.aria2.txt",
        },
    }
    row_probe = nte_live_probe(reslist_url, ok=True, status=200, size=1024)
    row_interpretation = TofAvailabilityAdapter().interpret([row_probe], row)
    row["availability"] = availability_block(
        [row_probe],
        "live_probe",
        row_interpretation,
        "scripts/test_availability_negative.py",
    )
    row["availability_counts"] = {"full": {"available": 1}}
    row["availability_reasons"] = {"full": {"not_probed": 1}}

    write_json(root / "catalog.json", {"versions": [row]})
    list_dir = root / "url_lists"
    list_dir.mkdir(parents=True, exist_ok=True)
    write_json(list_dir / "6.2.2-full.json", [item])


def mutate_tof_item(root: Path, path_parts: tuple[str, ...], value: Any) -> None:
    valid_tof_root(root)
    shard_path = root / "url_lists" / "6.2.2-full.json"
    items = load_json(shard_path)
    target: Any = items[0]
    for part in path_parts[:-1]:
        target = target[part]
    target[path_parts[-1]] = value
    write_json(shard_path, items)


def assert_tof_validator_rejects(path_parts: tuple[str, ...], value: Any, expected_token: str) -> None:
    with tempfile.TemporaryDirectory(prefix="tof-availability-negative-") as temp:
        temp_root = Path(temp) / "tof"
        mutate_tof_item(temp_root, path_parts, value)
        errors = validate_tof(temp_root)
    if not any(expected_token in error for error in errors):
        raise AssertionError(f"TOF validator did not reject {'.'.join(path_parts)}={value!r}; errors={errors!r}")


def valid_wuwa_root(root: Path) -> None:
    version = "1.0.0"
    url = "https://pcdownload-aliyun.aki-game.com/game/chunk.pak"
    item = {
        "dest": "Client/Content/Paks/chunk.pak",
        "name": "chunk.pak",
        "md5": "abc",
        "size": 1024,
        "url": url,
        "urls": [url, "https://pcdownload-huoshan.aki-game.com/game/chunk.pak"],
    }
    probes = [
        wuwa_metadata_probe(item["urls"][0], size=1024),
        wuwa_metadata_probe(item["urls"][1], size=1024),
    ]
    item_interpretation = WuwaAvailabilityAdapter().interpret(probes, item)
    item["availability"] = availability_block(
        probes,
        "metadata_inference",
        item_interpretation,
        "scripts/test_availability_negative.py",
    )

    summary_probe = wuwa_metadata_probe(f"wuwa-metadata://{version}", size=0, ok=False, error="not_probed")
    summary = {
        "version": version,
        "channel": "live",
        "region": "cn",
        "file_count": 1,
        "cdn_count": 2,
        "patch_routes": 0,
        "size": 1024,
        "availability_counts": {"available": 1},
        "availability_reasons": {"not_probed": 1},
        "links": {
            "files": {
                "json": "data/wuwa/lists/1.0.0-files.json",
                "urls": "data/wuwa/lists/1.0.0-files.urls.txt",
                "aria2": "data/wuwa/lists/1.0.0-files.aria2.txt",
            }
        },
    }
    summary_interpretation = WuwaAvailabilityAdapter().interpret([summary_probe], summary)
    summary["availability"] = availability_block(
        [summary_probe],
        "metadata_inference",
        summary_interpretation,
        "scripts/test_availability_negative.py",
    )

    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "index.json", {"versions": [summary]})
    shard_path = root / "versions" / f"{version}.json"
    shard_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(shard_path, {
        "version": version,
        "channel": "live",
        "region": "cn",
        "files": [item],
        "patches": [],
        "links": summary["links"],
        "availability_counts": {"available": 1},
        "availability_reasons": {"not_probed": 1},
    })
    list_dir = root / "lists"
    list_dir.mkdir(parents=True, exist_ok=True)
    write_json(list_dir / "1.0.0-files.json", [item])


def mutate_wuwa_item(root: Path, path_parts: tuple[str, ...], value: Any) -> None:
    valid_wuwa_root(root)
    shard_path = root / "versions" / "1.0.0.json"
    shard = load_json(shard_path)
    target: Any = shard["files"][0]
    for part in path_parts[:-1]:
        target = target[part]
    target[path_parts[-1]] = value
    write_json(shard_path, shard)
    list_path = root / "lists" / "1.0.0-files.json"
    items = load_json(list_path)
    target = items[0]
    for part in path_parts[:-1]:
        target = target[part]
    target[path_parts[-1]] = value
    write_json(list_path, items)


def assert_wuwa_validator_rejects(path_parts: tuple[str, ...], value: Any, expected_token: str) -> None:
    with tempfile.TemporaryDirectory(prefix="wuwa-availability-negative-") as temp:
        temp_root = Path(temp) / "docs" / "data" / "wuwa"
        mutate_wuwa_item(temp_root, path_parts, value)
        errors = validate_wuwa(temp_root)
    if not any(expected_token in error for error in errors):
        raise AssertionError(f"WuWa validator did not reject {'.'.join(path_parts)}={value!r}; errors={errors!r}")


def assert_wuwa_build_cache_paths() -> None:
    config = ProbeScheduleConfig(ttl_hours=24, failed_ttl_hours=24, grace_hours=168, force_full=False)
    with tempfile.TemporaryDirectory(prefix="wuwa-cache-negative-") as temp:
        temp_root = Path(temp) / "docs" / "data" / "wuwa"
        valid_wuwa_root(temp_root)
        index = load_json(temp_root / "index.json")
        versions = load_versions(temp_root)
        empty_cache = PersistentProbeCache(Path(temp) / "empty-cache.json")
        _, _, _, errors, _, _, _ = apply_availability(
            temp_root,
            index,
            versions,
            live_versions={"1.0.0"},
            config=config,
            cache=empty_cache,
        )
        if errors:
            raise AssertionError(f"WuWa missing-cache build should not error: {errors!r}")
        item = versions["1.0.0"]["files"][0]
        availability = item["availability"]
        if availability["source"]["kind"] != "metadata_inference":
            raise AssertionError(f"WuWa missing cache must downgrade to metadata_inference: {availability!r}")
        if availability["interpretation"]["confidence"] == "high":
            raise AssertionError(f"WuWa missing cache must not use high confidence: {availability!r}")

    with tempfile.TemporaryDirectory(prefix="wuwa-cache-negative-") as temp:
        temp_root = Path(temp) / "docs" / "data" / "wuwa"
        valid_wuwa_root(temp_root)
        index = load_json(temp_root / "index.json")
        versions = load_versions(temp_root)
        item = versions["1.0.0"]["files"][0]
        cache = PersistentProbeCache(Path(temp) / "probe-cache.json")
        cache.put(wuwa_live_probe(item["urls"][0], ok=False, status=404, size=0, error="HTTP 404"))
        cache.put(wuwa_live_probe(item["urls"][1], ok=False, status=0, size=0, error="timeout"))
        cache.flush()
        _, _, _, errors, _, _, _ = apply_availability(
            temp_root,
            index,
            versions,
            live_versions={"1.0.0"},
            config=config,
            cache=PersistentProbeCache(Path(temp) / "probe-cache.json"),
        )
        if errors:
            raise AssertionError(f"WuWa failed-cache build should not error: {errors!r}")
        result = versions["1.0.0"]["files"][0]["availability"]
        if result["source"]["kind"] != "live_probe":
            raise AssertionError(f"WuWa complete failed cache should remain live_probe: {result!r}")
        interpretation = result["interpretation"]
        if interpretation["state"] != "unavailable" or interpretation["reason"] != "http_404":
            raise AssertionError(f"WuWa failed cache should map to http_404 unavailable: {interpretation!r}")


def assert_wuwa_build_stage_zero_network() -> None:
    source = (ROOT / "scripts" / "build_wuwa_availability.py").read_text(encoding="utf-8")
    forbidden = ("url_probe", "probe_candidates", "schedule_probe_candidates")
    offenders = [token for token in forbidden if token in source]
    if offenders:
        raise AssertionError(f"WuWa build stage contains network probe references: {offenders!r}")


def main() -> None:
    assert_arknights_failed_probe_maps_to_unavailable()
    assert_android_negative_paths()
    assert_android_known_good_conflict_protection()
    assert_android_failed_probe_ttl()
    assert_android_linked_list_sync()
    assert_android_recovery_stability()
    assert_hoyo_metadata_paths()
    assert_endfield_upstream_paths()
    assert_nte_paths()
    assert_tof_paths()
    assert_nte_release_type_validator()
    assert_wuwa_metadata_paths()
    assert_wuwa_build_cache_paths()
    assert_wuwa_build_stage_zero_network()
    assert_validator_rejects(("availability", "interpretation", "state"), "foobar", ":state:foobar")
    assert_validator_rejects(("availability", "interpretation", "reason"), "because_magic", ":reason:because_magic")
    assert_validator_rejects(("availability", "source", "kind"), "side_channel", ":source_kind:side_channel")
    assert_validator_rejects(("availability", "interpretation", "confidence"), "certain", ":confidence:certain")
    assert_android_validator_rejects(("availability", "interpretation", "state"), "foobar", ":state:foobar")
    assert_android_validator_rejects(("availability", "interpretation", "reason"), "because_magic", ":reason:because_magic")
    assert_android_validator_rejects(("availability", "source", "kind"), "side_channel", ":source_kind:side_channel")
    assert_android_validator_rejects(("availability", "interpretation", "confidence"), "certain", ":confidence:certain")
    assert_hoyo_validator_rejects(("availability", "interpretation", "state"), "foobar", ":state:foobar")
    assert_hoyo_validator_rejects(("availability", "interpretation", "reason"), "because_magic", ":reason:because_magic")
    assert_hoyo_validator_rejects(("availability", "source", "kind"), "side_channel", ":source_kind:side_channel")
    assert_hoyo_validator_rejects(("availability", "interpretation", "confidence"), "certain", ":confidence:certain")
    assert_endfield_validator_rejects(("availability", "interpretation", "state"), "foobar", ":state:foobar")
    assert_endfield_validator_rejects(("availability", "interpretation", "reason"), "because_magic", ":reason:because_magic")
    assert_endfield_validator_rejects(("availability", "source", "kind"), "side_channel", ":source_kind:side_channel")
    assert_endfield_validator_rejects(("availability", "interpretation", "confidence"), "certain", ":confidence:certain")
    assert_nte_validator_rejects(("availability", "interpretation", "state"), "foobar", ":state:foobar")
    assert_nte_validator_rejects(("availability", "interpretation", "reason"), "because_magic", ":reason:because_magic")
    assert_nte_validator_rejects(("availability", "source", "kind"), "side_channel", ":source_kind:side_channel")
    assert_nte_validator_rejects(("availability", "interpretation", "confidence"), "certain", ":confidence:certain")
    assert_tof_validator_rejects(("availability", "interpretation", "state"), "foobar", ":state:foobar")
    assert_tof_validator_rejects(("availability", "interpretation", "reason"), "because_magic", ":reason:because_magic")
    assert_tof_validator_rejects(("availability", "source", "kind"), "side_channel", ":source_kind:side_channel")
    assert_tof_validator_rejects(("availability", "interpretation", "confidence"), "certain", ":confidence:certain")
    assert_wuwa_validator_rejects(("availability", "interpretation", "state"), "foobar", ":state:foobar")
    assert_wuwa_validator_rejects(("availability", "interpretation", "reason"), "because_magic", ":reason:because_magic")
    assert_wuwa_validator_rejects(("availability", "source", "kind"), "side_channel", ":source_kind:side_channel")
    assert_wuwa_validator_rejects(("availability", "interpretation", "confidence"), "certain", ":confidence:certain")

    print("Availability negative-path checks")
    print("arknights_failed_probe=PASS")
    print("android_failed_probe=PASS")
    print("android_fake_200=PASS")
    print("android_retained_historical=PASS")
    print("android_known_good_conflict=PASS")
    print("android_failed_probe_ttl=PASS")
    print("android_linked_list_sync=PASS")
    print("android_recovery_stability=PASS")
    print("hoyo_metadata_inference=PASS")
    print("endfield_upstream_archive=PASS")
    print("nte_live_probe_and_metadata=PASS")
    print("tof_live_probe_and_metadata=PASS")
    print("nte_release_type_invariant=PASS")
    print("wuwa_metadata_multicdn=PASS")
    print("wuwa_live_multicdn=PASS")
    print("wuwa_probe_cache_paths=PASS")
    print("wuwa_build_zero_network=PASS")
    print("closed_vocab_rejection=PASS")
    print("result=PASS")


if __name__ == "__main__":
    main()
