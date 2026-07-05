#!/usr/bin/env python3
"""Sync HoYo game metadata from the public HoyoFiles API."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HOYO_DATA = ROOT / "docs" / "data" / "hoyo"
CHUNK_DATA = HOYO_DATA / "chunk"
GAMES_PATH = HOYO_DATA / "games.json"

API_BASE = "https://autopatch.amarea.cn/pkg_version"
SOURCE_URL = "https://hoyo-files.amarea.cn"
HEAD_TIMEOUT_SECONDS = 10

GAMES = [
    {
        "id": "hk4e",
        "name": "原神",
        "shortName": "YS",
        "domain": "autopatchcn.yuanshen.com",
    },
    {
        "id": "hkrpg",
        "name": "崩坏：星穹铁道",
        "shortName": "HSR",
        "domain": "autopatchcn.bhsr.com",
    },
    {
        "id": "nap",
        "name": "绝区零",
        "shortName": "ZZZ",
        "domain": "autopatchcn.juequling.com",
    },
    {
        "id": "bh3",
        "name": "崩坏3",
        "shortName": "BH3",
        "domain": "autopatchcn.bh3.com",
    },
]


MANUAL_HOYO_VERSION_PATCHES: dict[str, dict[str, dict[str, Any]]] = {
    "nap": {
        "0.2.0": {
            "game": {
                "full": {
                    "name": "JueQuLing(Beta).zip",
                    "url": "https://autopatchcn.juequling.com/download/windows/0.2.0/j0fGHf10yF5n/JueQuLing(Beta).zip",
                    "checksum": "",
                    "size": 0,
                    "source": "User-provided historical beta URL; original URL now returns 404",
                    "archive": {
                        "original": "https://autopatchcn.juequling.com/download/windows/0.2.0/j0fGHf10yF5n/JueQuLing(Beta).zip%0A",
                        "timestamp": "20240703060935",
                        "status": 404,
                        "length": 689,
                        "digest": "ATFH4E36D2P65LMWU7PULO3H2WVT3YMQ",
                        "mimetype": "text/html",
                    },
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        }
    },
    "bh3": {
        "3.7.0": {
            "game": {
                "full": {
                    "name": "BH3_v3.7.0_39ef5ab7dab.7z",
                    "url": "http://bundle.bh3.com/tmp/pc/BH3_v3.7.0_39ef5ab7dab.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "3.8.0": {
            "game": {
                "full": {
                    "name": "BH3_v3.8.0_12d334ef92e.7z",
                    "url": "http://bundle.bh3.com/tmp/pc/BH3_v3.8.0_12d334ef92e.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "3.9.1": {
            "game": {
                "full": {
                    "name": "BH3_v3.9.1_23d0982b635.7z",
                    "url": "https://app.bh3.com/public/download/BH3_v3.9.1_23d0982b635.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "4.1.0": {
            "game": {
                "full": {
                    "name": "BH3_v4.1.0_02467decb1c.7z",
                    "url": "http://bundle.bh3.com/tmp/pc/BH3_v4.1.0_02467decb1c.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "4.2.0": {
            "game": {
                "full": {
                    "name": "BH3_v4.2.0_c3dc0f097be.7z",
                    "url": "http://bundle.bh3.com/tmp/pc/BH3_v4.2.0_c3dc0f097be.7z",
                    "checksum": "",
                    "size": 4553098731,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "4.3.0": {
            "game": {
                "full": {
                    "name": "BH3_v4.3.0_9b6faec931e.7z",
                    "url": "http://bundle.bh3.com/tmp/pc/BH3_v4.3.0_9b6faec931e.7z",
                    "checksum": "",
                    "size": 4637027964,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "4.3.1": {
            "game": {
                "full": {
                    "name": "BH3_v4.3.1_1885cca652d.7z",
                    "url": "http://bundle.bh3.com/tmp/pc/BH3_v4.3.1_1885cca652d.7z",
                    "checksum": "",
                    "size": 4634044068,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "4.4.0": {
            "game": {
                "full": {
                    "name": "BH3_v4.4.0_dde841d5e22.7z",
                    "url": "http://bundle.bh3.com/tmp/pc/BH3_v4.4.0_dde841d5e22.7z",
                    "checksum": "",
                    "size": 4800027777,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "4.5.0": {
            "game": {
                "full": {
                    "name": "BH3_v4.5.0_9f70c980de6.7z",
                    "url": "http://bundle.bh3.com/tmp/pc/BH3_v4.5.0_9f70c980de6.7z",
                    "checksum": "",
                    "size": 5179182836,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "4.6.0": {
            "game": {
                "full": {
                    "name": "BH3_v4.6.0_c54b862e55b.7z",
                    "url": "https://bundle.bh3.com/public/PC/BH3_v4.6.0_c54b862e55b.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "4.7.0": {
            "game": {
                "full": {
                    "name": "BH3_v4.7.0_980657d4019.7z",
                    "url": "https://bundle.bh3.com/public/PC/BH3_v4.7.0_980657d4019.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "4.8.0": {
            "game": {
                "full": {
                    "name": "BH3_v4.8.0_7355ad6fdb7.7z",
                    "url": "https://bundle.bh3.com/public/PC/BH3_v4.8.0_7355ad6fdb7.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "4.9.0": {
            "game": {
                "full": {
                    "name": "BH3_v4.9.0_f359e675f8e.7z",
                    "url": "https://bundle.bh3.com/public/PC/BH3_v4.9.0_f359e675f8e.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "5.0.0": {
            "game": {
                "full": {
                    "name": "BH3_v5.0.0_7a3047d5be1.7z",
                    "url": "https://bundle.bh3.com/public/PC/BH3_v5.0.0_7a3047d5be1.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "5.1.0": {
            "game": {
                "full": {
                    "name": "BH3_v5.1.0_4d7e266e4fa.7z",
                    "url": "https://bundle.bh3.com/public/PC/BH3_v5.1.0_4d7e266e4fa.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "5.2.0": {
            "game": {
                "full": {
                    "name": "BH3_v5.2.0_77f090b6a721.7z",
                    "url": "https://bundle.bh3.com/public/PC/BH3_v5.2.0_77f090b6a721.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "5.3.0": {
            "game": {
                "full": {
                    "name": "BH3_v5.3.0_a3a92da6712f.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20211103104259_693ct8KNQRPrRgww/PC/BH3_v5.3.0_a3a92da6712f.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "5.4.0": {
            "game": {
                "full": {
                    "name": "BH3_v5.4.0_571c0ff55162.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20211215100712_yZnkyc197WEAbpXD/PC/BH3_v5.4.0_571c0ff55162.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "5.5.0": {
            "game": {
                "full": {
                    "name": "BH3_v5.5.0_56e0f53e9241.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20220125172258_G8SfUTQ2pert78RO/PC/BH3_v5.5.0_56e0f53e9241.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "5.6.0": {
            "game": {
                "full": {
                    "name": "BH3_v5.6.0_e9b301f2edac.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20220308195925_CQP628TAPz6hlV25/PC/BH3_v5.6.0_e9b301f2edac.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "5.7.0": {
            "game": {
                "full": {
                    "name": "BH3_v5.7.0_87c27c9bd47a.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20220418185848_OBkB8bi84cA2655H/PC/BH3_v5.7.0_87c27c9bd47a.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "5.8.0": {
            "game": {
                "full": {
                    "name": "BH3_v5.8.0_0e38ab9b9519.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20220530180356_zQkusPa43Hl6Pm21/PC/BH3_v5.8.0_0e38ab9b9519.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "5.9.0": {
            "game": {
                "full": {
                    "name": "BH3_v5.9.0_e61b333c9991.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20220711190415_uAJEjoWCS53uMXSJ/pc/BH3_v5.9.0_e61b333c9991.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "6.0.1": {
            "game": {
                "full": {
                    "name": "BH3_v6.0.1_2d927448f4c3.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20220829102342_5OzDI6dZmyn8DiSR/PC/BH3_v6.0.1_2d927448f4c3.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "chunk": None,
        },
        "6.1.0": {
            "game": {
                "full": {
                    "name": "BH3_v6.1.0_cd4c898e2f15.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20220927105429_ALm4C1zHrTLNlwkq/PC/BH3_v6.1.0_cd4c898e2f15.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20220927105429_ALm4C1zHrTLNlwkq/PC/extract",
            "chunk": None,
        },
        "6.2.0": {
            "game": {
                "full": {
                    "name": "BH3_v6.2.0_3eb0db30afc9.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20221106182828_Sd8hWJzQkh5gR2ZV/PC/BH3_v6.2.0_3eb0db30afc9.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20221106182828_Sd8hWJzQkh5gR2ZV/PC/extract",
            "chunk": None,
        },
        "6.3.0": {
            "game": {
                "full": {
                    "name": "BH3_v6.3.0_102c3ff09afb.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20221210130727_kMujQDyj3dcmqupm/PC/BH3_v6.3.0_102c3ff09afb.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20221210130727_kMujQDyj3dcmqupm/PC/extract",
            "chunk": None,
        },
        "6.4.0": {
            "game": {
                "full": {
                    "name": "BH3_v6.4.0_1331e8aa9e17.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20230116101825_JscRRCB6O6EzK9C5/PC/BH3_v6.4.0_1331e8aa9e17.7z",
                    "checksum": "",
                    "size": 10832841217,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20230116101825_JscRRCB6O6EzK9C5/PC/extract",
            "chunk": None,
        },
        "6.5.0": {
            "game": {
                "full": {
                    "name": "BH3_v6.5.0_826e19c5f031.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20230305113140_X4V6Nf5dn6viEyfS/PC/BH3_v6.5.0_826e19c5f031.7z",
                    "checksum": "",
                    "size": 11225162137,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20230305113140_X4V6Nf5dn6viEyfS/PC/extract",
            "chunk": None,
        },
        "6.6.0": {
            "game": {
                "full": {
                    "name": "BH3_v6.6.0_4ed7d53313df.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20230416151857_AsBJm4PVPKKR38YI/PC/BH3_v6.6.0_4ed7d53313df.7z",
                    "checksum": "",
                    "size": 0,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20230416151857_AsBJm4PVPKKR38YI/PC/extract",
            "chunk": None,
        },
        "6.7.0": {
            "game": {
                "full": {
                    "name": "BH3_v6.7.0_c02b55ac37c9.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20230529102233_twzVyW15N4xGFkQ8/PC/BH3_v6.7.0_c02b55ac37c9.7z",
                    "checksum": "",
                    "size": 11813659145,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20230529102233_twzVyW15N4xGFkQ8/PC/extract",
            "chunk": None,
        },
        "6.8.0": {
            "game": {
                "full": {
                    "name": "BH3_v6.8.0_fe00767f5f60.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20230702172043_o8BzGMLGBbVpTjyy/PC/BH3_v6.8.0_fe00767f5f60.7z",
                    "checksum": "",
                    "size": 12218548509,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20230702172043_o8BzGMLGBbVpTjyy/PC/extract",
            "chunk": None,
        },
        "6.9.0": {
            "game": {
                "full": {
                    "name": "BH3_v6.9.0_d09f54ae2822.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20230814114102_KD8RjBDLGc0wU5j9/PC/BH3_v6.9.0_d09f54ae2822.7z",
                    "checksum": "",
                    "size": 12656036672,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20230814114102_KD8RjBDLGc0wU5j9/PC/extract",
            "chunk": None,
        },
        "7.0.0": {
            "game": {
                "full": {
                    "name": "BH3_v7.0.0_ec9940649b00.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20230925103219_8WqdhyRJLpCQJNBY/PC/BH3_v7.0.0_ec9940649b00.7z",
                    "checksum": "",
                    "size": 13615515905,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20230925103219_8WqdhyRJLpCQJNBY/PC/extract",
            "chunk": None,
        },
        "7.1.0": {
            "game": {
                "full": {
                    "name": "BH3_v7.1.0_2370cca635c2.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20231106105308_PSI04xYkMRDoKldh/PC/BH3_v7.1.0_2370cca635c2.7z",
                    "checksum": "",
                    "size": 14270824403,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20231106105308_PSI04xYkMRDoKldh/PC/extract",
            "chunk": None,
        },
        "7.2.0": {
            "game": {
                "full": {
                    "name": "BH3_v7.2.0_a5dedc5699ee.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20231218144111_nFwR8NyQCxVRbXeo/PC/BH3_v7.2.0_a5dedc5699ee.7z",
                    "checksum": "",
                    "size": 13521206825,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20231218144111_nFwR8NyQCxVRbXeo/PC/extract",
            "chunk": None,
        },
        "7.4.0": {
            "game": {
                "full": {
                    "name": "BH3_v7.4.0_52034be0b492.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20240325143924_D6bZkQP9zm8vNajM/PC/BH3_v7.4.0_52034be0b492.7z",
                    "checksum": "",
                    "size": 17342008186,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20240325143924_D6bZkQP9zm8vNajM/PC/extract",
            "chunk": None,
        },
        "7.5.0": {
            "game": {
                "full": {
                    "name": "BH3_v7.5.0_c3433332d6a2.7z",
                    "url": "https://bundle.bh3.com/ptpublic/rel/20240506104443_Eb7wY4fRoYiICW5J/PC/BH3_v7.5.0_c3433332d6a2.7z",
                    "checksum": "",
                    "size": 17891545746,
                }
            },
            "voice": {},
            "update": {},
            "decompressed_path": "https://bundle.bh3.com/ptpublic/rel/20240506104443_Eb7wY4fRoYiICW5J/PC/extract",
            "chunk": None,
        },
    }
}


def fetch_json(url: str, timeout: int = 45, retries: int = 2, backoff: float = 2.0) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, headers={"User-Agent": "game-cdn-archive/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if 400 <= exc.code < 500 and exc.code not in {408, 429}:
                break
        except Exception as exc:
            last_error = exc
        if attempt < retries:
            delay = backoff * (attempt + 1)
            print(f"retry fetch_json {url} after {last_error} (attempt {attempt + 2}/{retries + 1}, sleep {delay:.1f}s)")
            time.sleep(delay)
    raise RuntimeError(f"failed to fetch JSON from {url}: {last_error}") from last_error


def url_for_request(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            urllib.parse.quote(parts.path, safe="/%"),
            urllib.parse.quote(parts.query, safe="=&%:/?+"),
            parts.fragment,
        )
    )


def fetch_head_metadata(url: str, timeout: int = HEAD_TIMEOUT_SECONDS) -> dict[str, Any]:
    if not url:
        return {}
    request = urllib.request.Request(
        url_for_request(url),
        headers={"User-Agent": "game-cdn-archive/1.0"},
        method="HEAD",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "status": response.status,
                "last_modified": response.headers.get("Last-Modified") or "",
                "content_length": int(response.headers.get("Content-Length") or 0),
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "last_modified": exc.headers.get("Last-Modified") or "",
            "content_length": int(exc.headers.get("Content-Length") or 0),
        }
    except Exception as exc:
        return {"status": None, "last_modified": "", "content_length": 0, "error": str(exc)}


def write_json_if_changed(path: Path, data: Any, indent: int = 2) -> bool:
    text = json.dumps(data, ensure_ascii=False, indent=indent) + "\n"
    if path.exists():
        old_text = path.read_text(encoding="utf-8")
        if old_text == text:
            return False
        try:
            if json.loads(old_text) == data:
                return False
        except json.JSONDecodeError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def read_cached_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def item_count_and_bytes(item: Any) -> tuple[int, int]:
    if not item:
        return 0, 0
    if isinstance(item, list):
        count = len(item)
        size = sum(int(entry.get("size") or 0) for entry in item if isinstance(entry, dict))
        return count, size
    if isinstance(item, dict):
        return 1, int(item.get("size") or 0)
    return 0, 0


def as_list(value: Any) -> list[Any]:
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def hoyo_download_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    game = row.get("game") or {}
    for key in ["full", "segments"]:
        items.extend(item for item in as_list(game.get(key)) if isinstance(item, dict))
    for voice in (row.get("voice") or {}).values():
        items.extend(item for item in as_list(voice) if isinstance(item, dict))
    for patch in (row.get("update") or {}).values():
        items.extend(item for item in as_list((patch or {}).get("game")) if isinstance(item, dict))
        for voice in ((patch or {}).get("voice") or {}).values():
            items.extend(item for item in as_list(voice) if isinstance(item, dict))
    return [item for item in items if item.get("url")]


def hoyo_representative_url(row: dict[str, Any], chunk: dict[str, Any] | None) -> tuple[str, str]:
    downloads = hoyo_download_items(row)
    if downloads:
        return str(downloads[0]["url"]), "pc_package"

    for manifest in ((chunk or {}).get("data") or {}).get("manifests") or []:
        if manifest.get("matching_field") != "game":
            continue
        manifest_id = ((manifest.get("manifest") or {}).get("id") or "").strip()
        prefix = ((manifest.get("manifest_download") or {}).get("url_prefix") or "").rstrip("/")
        suffix = (manifest.get("manifest_download") or {}).get("url_suffix") or ""
        if manifest_id and prefix:
            return f"{prefix}/{manifest_id}{suffix}", "chunk_manifest"

    return "", ""


def cached_version_metadata(previous_game: dict[str, Any] | None, version: str, url: str) -> dict[str, Any] | None:
    if not previous_game:
        return None
    for row in previous_game.get("versions") or []:
        if row.get("version") == version and row.get("last_modified_url") == url and (
            row.get("last_modified") or row.get("last_modified_status") is not None
        ):
            return row
    return None


def apply_last_modified(
    stats: dict[str, Any],
    previous_game: dict[str, Any] | None,
    version: str,
    url: str,
    source: str,
) -> None:
    if not url:
        return
    cached = cached_version_metadata(previous_game, version, url)
    if cached:
        for key in ["last_modified", "last_modified_status", "last_modified_url", "last_modified_source"]:
            if cached.get(key) is not None:
                stats[key] = cached[key]
        return

    metadata = fetch_head_metadata(url)
    stats["last_modified_url"] = url
    stats["last_modified_source"] = source
    if metadata.get("last_modified"):
        stats["last_modified"] = metadata["last_modified"]
    if metadata.get("status") is not None:
        stats["last_modified_status"] = metadata["status"]


def version_stats(row: dict[str, Any]) -> dict[str, Any]:
    package_items = 0
    update_items = 0
    direct_bytes = 0

    game = row.get("game") or {}
    for key in ["full", "segments"]:
        count, size = item_count_and_bytes(game.get(key))
        package_items += count
        direct_bytes += size

    for voice in (row.get("voice") or {}).values():
        count, size = item_count_and_bytes(voice)
        package_items += count
        direct_bytes += size

    for patch in (row.get("update") or {}).values():
        count, size = item_count_and_bytes((patch or {}).get("game"))
        update_items += count
        direct_bytes += size
        for voice in ((patch or {}).get("voice") or {}).values():
            count, size = item_count_and_bytes(voice)
            update_items += count
            direct_bytes += size

    return {
        "package_items": package_items,
        "update_items": update_items,
        "direct_bytes": direct_bytes,
        "has_chunk": bool(row.get("chunk")),
        "has_decompressed_path": bool(row.get("decompressed_path")),
    }


def merge_manual_version_patches(game_id: str, versions: dict[str, Any]) -> None:
    patches = MANUAL_HOYO_VERSION_PATCHES.get(game_id, {})
    for version, row in patches.items():
        if version not in versions:
            versions[version] = deepcopy(row)
            continue

        existing = versions[version]
        if not isinstance(existing, dict):
            versions[version] = deepcopy(row)
            continue

        existing.setdefault("voice", {})
        existing.setdefault("update", {})
        existing.setdefault("chunk", row.get("chunk"))
        if row.get("decompressed_path") and not existing.get("decompressed_path"):
            existing["decompressed_path"] = row["decompressed_path"]

        game = existing.setdefault("game", {})
        manual_game = row.get("game") or {}
        if isinstance(game, dict) and isinstance(manual_game, dict):
            for key, value in manual_game.items():
                game.setdefault(key, deepcopy(value))


def stable_compare_games(index: dict[str, Any]) -> dict[str, Any]:
    stable = deepcopy(index)
    stable["generated_at"] = None
    stable["last_checked_at"] = None
    return stable


def main() -> None:
    HOYO_DATA.mkdir(parents=True, exist_ok=True)
    CHUNK_DATA.mkdir(parents=True, exist_ok=True)

    previous = json.loads(GAMES_PATH.read_text(encoding="utf-8")) if GAMES_PATH.exists() else {}
    checked_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    games_summary = []
    synced_chunks = 0
    cached_chunks = 0
    chunk_api_available = True

    for game in GAMES:
        game_id = game["id"]
        previous_game = next(
            (item for item in previous.get("games", []) if item.get("id") == game_id),
            None,
        )
        versions_url = f"{API_BASE}/{game_id}_versions.json"
        versions = fetch_json(versions_url)
        if not isinstance(versions, dict):
            raise RuntimeError(f"unexpected version payload for {game_id}")
        merge_manual_version_patches(game_id, versions)

        write_json_if_changed(HOYO_DATA / f"{game_id}_versions.json", versions, indent=4)

        version_rows = []
        direct_items = 0
        update_items = 0
        chunk_versions = 0
        direct_bytes = 0

        for version in sorted(versions, key=version_key):
            row = versions[version]
            stats = version_stats(row)
            chunk: dict[str, Any] | None = None
            direct_items += int(stats["package_items"])
            update_items += int(stats["update_items"])
            direct_bytes += int(stats["direct_bytes"])
            if stats["has_chunk"]:
                chunk_versions += 1
                chunk_url = f"{API_BASE}/chunk/{game_id}_{version}.json"
                chunk_path = CHUNK_DATA / f"{game_id}_{version}.json"
                fetched_chunk = False
                if chunk_api_available:
                    try:
                        chunk = fetch_json(chunk_url)
                        fetched_chunk = True
                    except RuntimeError as exc:
                        chunk_api_available = False
                        print(
                            "::warning::HoyoFiles chunk API became unavailable; "
                            f"using cached chunk indexes for the rest of this run: {exc}"
                        )
                        chunk = read_cached_json(chunk_path)
                else:
                    chunk = read_cached_json(chunk_path)

                if isinstance(chunk, dict) and chunk.get("retcode") == 0:
                    if fetched_chunk:
                        write_json_if_changed(chunk_path, chunk, indent=4)
                        synced_chunks += 1
                    else:
                        cached_chunks += 1
                else:
                    stats["has_chunk"] = False
                    chunk_versions -= 1
                    source = "fetched" if fetched_chunk else "cached"
                    print(
                        f"::warning::No usable {source} HoyoFiles chunk index is available "
                        f"for {game_id} {version}; disabling its chunk view."
                    )

            metadata_url, metadata_source = hoyo_representative_url(row, chunk)
            apply_last_modified(stats, previous_game, version, metadata_url, metadata_source)
            version_rows.append({"version": version, **stats})

        games_summary.append(
            {
                **game,
                "versions": version_rows,
                "version_count": len(version_rows),
                "first_version": version_rows[0]["version"] if version_rows else None,
                "latest_version": version_rows[-1]["version"] if version_rows else None,
                "direct_items": direct_items,
                "update_items": update_items,
                "chunk_versions": chunk_versions,
                "direct_bytes": direct_bytes,
                "versions_url": versions_url,
            }
        )

    new_index = {
        "source": SOURCE_URL,
        "api_base": API_BASE,
        "last_checked_at": checked_at,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "games": games_summary,
    }
    if stable_compare_games(previous) == stable_compare_games(new_index):
        new_index["generated_at"] = previous.get("generated_at")

    write_json_if_changed(GAMES_PATH, new_index)
    print(
        f"synced {len(games_summary)} HoYo games, {synced_chunks} chunk indexes"
        f", reused {cached_chunks} cached chunk indexes"
    )


if __name__ == "__main__":
    main()
