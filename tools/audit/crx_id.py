#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Show the extension ID a CRX3 file declares and the IDs derived from its signing keys.

A genuine CRX's declared ID equals one of its key-derived IDs. Use this to verify any
extension Thoron bundles:  py -3 -I tools/audit/crx_id.py path/to/extension.crx
"""
import hashlib
import struct
import sys

_ALPHABET = "abcdefghijklmnop"


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        byte = buf[i]
        i += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, i


def _fields(buf: bytes):
    i = 0
    while i < len(buf):
        key, i = _varint(buf, i)
        number, wire = key >> 3, key & 7
        if wire == 2:
            length, i = _varint(buf, i)
            yield number, buf[i:i + length]
            i += length
        elif wire == 0:
            _, i = _varint(buf, i)
        elif wire == 1:
            i += 8
        elif wire == 5:
            i += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")


def _to_id(hex_digest: str) -> str:
    return "".join(_ALPHABET[int(c, 16)] for c in hex_digest[:32])


def crx_ids(data: bytes) -> tuple[str, list[str]]:
    if len(data) < 12 or data[:4] != b"Cr24" or struct.unpack("<I", data[4:8])[0] != 3:
        raise ValueError("not a CRX3 file")
    header_len = struct.unpack("<I", data[8:12])[0]
    header = data[12:12 + header_len]
    try:
        derived = []
        declared = None
        for number, payload in _fields(header):
            if number in (2, 3):  # sha256_with_rsa / sha256_with_ecdsa proofs
                key = dict(_fields(payload)).get(1)
                if key:
                    derived.append(_to_id(hashlib.sha256(key).hexdigest()))
            elif number == 10000:  # signed_header_data -> SignedData.crx_id
                crx_id = dict(_fields(payload)).get(1)
                if crx_id:
                    declared = _to_id(crx_id.hex())
    except (IndexError, struct.error) as exc:
        raise ValueError(f"malformed CRX3 header: {exc}") from exc
    if declared is None:
        raise ValueError("CRX3 header has no declared crx_id")
    return declared, derived


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: crx_id.py FILE.crx", file=sys.stderr)
        return 2
    with open(argv[0], "rb") as f:
        declared, derived = crx_ids(f.read())
    print(f"declared ID: {declared}")
    for key_id in derived:
        print(f"key-derived ID: {key_id}{'  (matches)' if key_id == declared else ''}")
    return 0 if declared in derived else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
