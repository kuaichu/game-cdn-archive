#!/usr/bin/env python3
"""Decode NTE PatcherXML0 protected XML files."""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


MAGIC = b"PatcherXML0\0"


def pad16_ascii_zero(value: bytes) -> bytes:
    return value[:16].ljust(16, b"0")


def decode_patcherxml0(data: bytes, key_seed: str, iv_seed: str = "PatcherSDK") -> bytes:
    if not data.startswith(MAGIC):
        return data

    expected_size = struct.unpack_from("<I", data, 12)[0]
    payload = data[16:]

    key = pad16_ascii_zero(key_seed.encode("utf-8"))
    iv = pad16_ascii_zero(iv_seed.encode("utf-8"))
    decrypted = AES.new(key, AES.MODE_CBC, iv).decrypt(payload)

    try:
        decrypted = unpad(decrypted, 16)
    except ValueError:
        pass

    plain = zlib.decompress(decrypted)
    if len(plain) != expected_size:
        raise ValueError(f"decoded size mismatch: expected {expected_size}, got {len(plain)}")
    return plain


def main() -> None:
    parser = argparse.ArgumentParser(description="Decode NTE PatcherXML0 protected XML.")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--key", default="1289@Patcher", help="AES key seed before ASCII-0 padding")
    parser.add_argument("--iv", default="PatcherSDK", help="AES IV seed before ASCII-0 padding")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--suffix", default=".decoded.xml")
    args = parser.parse_args()

    for src in args.files:
        plain = decode_patcherxml0(src.read_bytes(), args.key, args.iv)
        if args.out_dir:
            dst_dir = args.out_dir / src.parent.name
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / f"{src.name}{args.suffix}"
        else:
            dst = src.with_name(f"{src.name}{args.suffix}")
        dst.write_bytes(plain)
        print(f"{src} -> {dst} ({len(plain)} bytes)")


if __name__ == "__main__":
    main()
