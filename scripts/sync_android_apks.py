#!/usr/bin/env python3
"""Build static Android APK indexes from known official CDN URLs."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


KNOWN_APKS = [
    {
        "game_id": "nte",
        "version": "1.1.5",
        "channel": "official",
        "url": "https://download982100001.wmupd.com/DBBAcAsHETkPNZ/KahEjcXPZw/ZMHiHAAKS/rMETwPrjYHWX/WSsWamksBPBi/xJJBDjteYbWDjH/yGjMzBb/nnaDzeXeMNR/KwmNRJZa.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "wuwa",
        "version": "3.3.2",
        "channel": "官渠",
        "url": "https://mirrors-package-mc.aki-game.com/client/download/20260516183706_FRC8o8CQS9L44Ra4WW/%E9%B8%A3%E6%BD%AE_3.3.2_168377155_33_%E5%AE%98%E6%B8%A0_32e97887831ba8ca620f93b4aa2ad0ff_shelled.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "wuwa",
        "version": "3.0.0",
        "channel": "官渠",
        "url": "https://mirrors-package-mc.aki-game.com/client/download/20251218163511_GpB6itW0p623nE4SMi/%E9%B8%A3%E6%BD%AE_3.0.0_156399220_33_%E5%AE%98%E6%B8%A0_e76c2d8ea383e31af9a8ac20ae3f02e1_shelled.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "wuwa",
        "version": "2.7.0",
        "channel": "官渠",
        "url": "https://mirrors-package-mc.aki-game.com/client/download/20250928105540_sgxqWxKbrnRT8KgK16/%E9%B8%A3%E6%BD%AE_2.7.0_149269354_33_%E5%AE%98%E6%B8%A0_a8cc769870e6ffbad35575179e98b30d_shelled.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "nap",
        "version": "2.8.0",
        "channel": "mktbackup2",
        "url": "https://autopatchcn.juequling.com/package_download/op/client_app/download/20260415151146_HP6JUMY1mL9VnQWt/mktbackup2/ZenlessZoneZero_2.8.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "nap",
        "version": "2.4.0",
        "channel": "gf_1_7",
        "url": "https://autopatchcn.juequling.com/package_download/op/client_app/download/20251107154705_0ujPjXffZwY0voqI/gf_1_7/ZenlessZoneZero_2.4.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "nap",
        "version": "2.3.0",
        "channel": "oonrzywymxk1",
        "url": "https://autopatchcn.juequling.com/package_download/op/client_app/download/20250926175650_zf2LhFSf10NBg5iB/oonrzywymxk1/ZenlessZoneZero_2.3.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "6.6.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20260509191652_EElRT82l302SABA2/mihoyo/yuanshen_6.6.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "6.2.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20251124182449_lRpe1GTcjzBZQBU1/mihoyo/yuanshen_6.2.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "6.0.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20250901103926_RXhoUrzBjjseDGPk/mihoyo/yuanshen_6.0.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "5.6.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20250427153413_1kLIh8wFZegAqpHw/mihoyo/yuanshen_5.6.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "4.5.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20240301202146_2eos1Ghjnr2cl6UN/mihoyo/yuanshen_4.5.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hk4e",
        "version": "4.2.0",
        "channel": "mihoyo",
        "url": "https://autopatchcn.yuanshen.com/client_app/download/Android/20231030114712_nMiBDLnfI0ibjPR1/mihoyo/yuanshen_4.2.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "4.3.0",
        "channel": "mihoyo_1",
        "url": "https://autopatchcn.bhsr.com/client/cn/20260523161433_yrgZsgGJ4R1J210J/mihoyo_1/StarRail_4.3.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "3.8.0",
        "channel": "gw_An",
        "url": "https://autopatchcn.bhsr.com/client/cn/20251205193454_2JAzO0tkfc1lPb0c/gw_An/StarRail_3.8.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "3.7.0",
        "channel": "mihoyo_1",
        "url": "https://autopatchcn.bhsr.com/client/cn/20251025162622_alR6Tz1Le986Lu9q/mihoyo_1/StarRail_3.7.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "3.5.0",
        "channel": "ad_dyst12_An",
        "url": "https://autopatchcn.bhsr.com/client/cn/20250801095521_kFIVD1SzuosxW9vr/ad_dyst12_An/StarRail_3.5.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "3.4.0",
        "channel": "gw_An",
        "url": "https://autopatchcn.bhsr.com/client/cn/20250623112713_2bg6PaxrWLL0CPvF/gw_An/StarRail_3.4.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "1.6.0",
        "channel": "mihoyo_8",
        "url": "https://autopatchcn.bhsr.com/client/cn/20231215090743_ffCg5V2j0gON2tvr/mihoyo_8/StarRail_1.6.0.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "1.3.0",
        "channel": "mihoyo_8",
        "url": "https://autopatchcn.bhsr.com/client/cn/20230818153431_sMKzYZ9EOeT15oNn/StarRail_1.3.0_mihoyo_8.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "hkrpg",
        "version": "1.2.0",
        "channel": "mihoyo_8",
        "url": "https://autopatchcn.bhsr.com/client/cn/20230709224719_3CcrEpEKT9iaObJh/StarRail_1.2.0_mihoyo_8.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "8.9.0",
        "channel": "gw",
        "url": "https://autopatchcn.bh3.com/ptpublic/rel/20260521184041_fIpuozZUX1U7jnuv/CPS/20260514-004049-gf_android_ota-versions-v8_9-Lives_Flourish_gw.apk",
        "source": "official CDN URL captured manually",
    },
    {
        "game_id": "bh3",
        "version": "1.9.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20171123-android_versions_v1_9_resurrection_of_the_sacramental_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.8.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20171012-android_versions_v1_8_Scarlet_Mitama_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.7.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20170824-android_versions_v1_7_The_Awakening_of_SliverWolf_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.6.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20170630-android_versions-v1_6_TogetherinSummer_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.5.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20170525-android_versions-v1_5_Theresa_Fight_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.4.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20170407-184918-gf_android_ota-versions-v1_4-4R-6d1fb22-ASB-il2cpp_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.3.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20170228-202036-gf_android_ota-versions-v1_3_bugfix-updateota-2de1573-ASB-il2cpp_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.1.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/20161108-112940-gf_android-versions-v1_1-4R-705fcfd-ASB-il2cpp_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
    {
        "game_id": "bh3",
        "version": "1.0.0",
        "channel": "guofu",
        "url": "http://app.bh3.com/public/Android/0_gf_android-versions-v1_0_2nd-4R-b2b8e16-ASB-mono_guofu.apk",
        "source": "Wayback Machine historical URL; original domain no longer resolves",
    },
]

GAME_NAMES = {
    "nte": {"name": "异环", "subName": "Neverness to Everness"},
    "endfield": {"name": "明日方舟：终末地", "subName": "Arknights: Endfield"},
    "wuwa": {"name": "鸣潮", "subName": "Wuthering Waves"},
    "hk4e": {"name": "原神", "subName": "Genshin Impact"},
    "hkrpg": {"name": "崩坏：星穹铁道", "subName": "Honkai: Star Rail"},
    "nap": {"name": "绝区零", "subName": "Zenless Zone Zero"},
    "bh3": {"name": "崩坏3", "subName": "Honkai Impact 3rd"},
}


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def head_url(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "game-cdn-archive/1.0"}, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            headers = response.headers
            return {
                "status": response.status,
                "content_type": headers.get("Content-Type", ""),
                "size": int(headers.get("Content-Length") or 0),
                "last_modified": headers.get("Last-Modified", ""),
                "etag": (headers.get("ETag") or "").strip('"'),
                "md5": headers.get("X-Cos-Meta-Md5", ""),
                "crc64": headers.get("X-Cos-Hash-Crc64ecma", ""),
                "error": "",
            }
    except Exception as exc:
        return {
            "status": 0,
            "content_type": "",
            "size": 0,
            "last_modified": "",
            "etag": "",
            "md5": "",
            "crc64": "",
            "error": str(exc),
        }


def filename_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    return urllib.parse.unquote(Path(path).name)


def write_lists(output_dir: Path, game_id: str, version: str, entries: list[dict]) -> dict[str, str]:
    lists_dir = output_dir / "lists"
    lists_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{game_id}_{version}_android"
    urls_path = lists_dir / f"{stem}.urls.txt"
    aria2_path = lists_dir / f"{stem}.aria2.txt"
    json_path = lists_dir / f"{stem}.json"

    urls_path.write_text("\n".join(entry["url"] for entry in entries) + "\n", encoding="utf-8")
    lines: list[str] = []
    for entry in entries:
        lines.append(entry["url"])
        lines.append(f"  dir=Android/{game_id}/{version}")
        lines.append(f"  out={entry['filename']}")
        if entry.get("md5"):
            lines.append(f"  checksum=md5={entry['md5']}")
        lines.append("")
    aria2_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "urls": f"data/android/lists/{urls_path.name}",
        "aria2": f"data/android/lists/{aria2_path.name}",
        "json": f"data/android/lists/{json_path.name}",
    }


def main() -> None:
    output_dir = Path(__file__).resolve().parents[1] / "docs" / "data" / "android"
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    entries: list[dict] = []

    for seed in KNOWN_APKS:
        meta = head_url(seed["url"])
        filename = filename_from_url(seed["url"])
        md5 = meta["md5"] or ""
        if not md5 and filename.endswith(".apk"):
            parts = filename.split("_")
            md5_candidates = [part for part in parts if len(part) == 32 and all(ch in "0123456789abcdef" for ch in part.lower())]
            md5 = md5_candidates[-1] if md5_candidates else ""
        entries.append({
            **seed,
            **meta,
            "md5": md5,
            "filename": filename,
            "captured_at": generated_at,
        })

    games: dict[str, dict] = {}
    for entry in entries:
        game_id = entry["game_id"]
        game = games.setdefault(game_id, {**GAME_NAMES.get(game_id, {"name": game_id, "subName": game_id}), "versions": []})
        game["versions"].append(entry)

    for game_id, game in games.items():
        game["versions"].sort(key=lambda item: version_key(item["version"]), reverse=True)
        by_version: dict[str, list[dict]] = {}
        for entry in game["versions"]:
            by_version.setdefault(entry["version"], []).append(entry)
        links = {}
        for version, version_entries in by_version.items():
            links[version] = write_lists(output_dir, game_id, version, version_entries)
        game["links"] = links

    index = {
        "generated_at": generated_at,
        "source": "manually captured official Android APK CDN URLs",
        "games": games,
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote Android APK index for {len(entries)} APKs")


if __name__ == "__main__":
    main()
