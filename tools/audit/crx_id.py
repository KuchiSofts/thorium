#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Verify a CRX3 extension package: its declared ID, the IDs of its signing keys, and the RSA
signatures themselves (RSASSA-PKCS1-v1_5 / SHA-256, as Chromium's CRX3 format specifies).

A CRX passes only if a signature by the key whose ID equals the declared ID verifies over the
package contents, and (with --expect) that ID is the one you expected, e.g. gorhill's uBlock Origin
GitHub key `fkgkibajhfbepljeaefdnfnegdcjomkh`. ECDSA proofs are reported but not verified here.
Bundled extensions are additionally pinned by SHA-256 in the build, and Chromium re-verifies the
signature at install time.
    py -3 -I tools/audit/crx_id.py FILE.crx [--expect EXTENSION_ID]
"""
import hashlib
import struct
import sys

_ALPHABET = "abcdefghijklmnop"
_SIGNED_DATA_PREFIX = b"CRX3 SignedData\x00"
_SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")
_RSA_OID = bytes.fromhex("2a864886f70d010101")


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


def _parse(data: bytes):
    """-> (header_fields, signed_header_data, archive)."""
    if len(data) < 12 or data[:4] != b"Cr24" or struct.unpack("<I", data[4:8])[0] != 3:
        raise ValueError("not a CRX3 file")
    header_len = struct.unpack("<I", data[8:12])[0]
    header = data[12:12 + header_len]
    try:
        fields = list(_fields(header))
    except (IndexError, struct.error) as exc:
        raise ValueError(f"malformed CRX3 header: {exc}") from exc
    signed = next((payload for number, payload in fields if number == 10000), b"")
    return fields, signed, data[12 + header_len:]


def crx_ids(data: bytes) -> tuple[str, list[str]]:
    fields, signed, _archive = _parse(data)
    crx_id = dict(_fields(signed)).get(1) if signed else None
    if not crx_id:
        raise ValueError("CRX3 header has no declared crx_id")
    derived = []
    for number, payload in fields:
        if number in (2, 3):
            key = dict(_fields(payload)).get(1)
            if key:
                derived.append(_to_id(hashlib.sha256(key).hexdigest()))
    return _to_id(crx_id.hex()), derived


def _der(buf: bytes, i: int) -> tuple[int, bytes, int]:
    tag, length = buf[i], buf[i + 1]
    i += 2
    if length & 0x80:
        count = length & 0x7F
        length = int.from_bytes(buf[i:i + count], "big")
        i += count
    return tag, buf[i:i + length], i + length


def _rsa_public_key(spki: bytes) -> tuple[int, int]:
    tag, body, _ = _der(spki, 0)
    if tag != 0x30:
        raise ValueError("SubjectPublicKeyInfo is not a SEQUENCE")
    _, algorithm, pos = _der(body, 0)
    if _RSA_OID not in algorithm:
        raise ValueError("not an RSA key")
    tag, bitstring, _ = _der(body, pos)
    if tag != 0x03 or bitstring[:1] != b"\x00":
        raise ValueError("bad BIT STRING")
    _, rsa, _ = _der(bitstring[1:], 0)
    _, modulus, pos = _der(rsa, 0)
    _, exponent, _ = _der(rsa, pos)
    return int.from_bytes(modulus, "big"), int.from_bytes(exponent, "big")


def _rsa_pkcs1_sha256_ok(spki: bytes, signature: bytes, message: bytes) -> bool:
    try:
        n, e = _rsa_public_key(spki)
    except (ValueError, IndexError):
        return False
    k = (n.bit_length() + 7) // 8
    s = int.from_bytes(signature, "big")
    if len(signature) != k or s >= n:
        return False
    t = _SHA256_DIGEST_INFO + hashlib.sha256(message).digest()
    if k < len(t) + 11:
        return False
    expected = b"\x00\x01" + b"\xff" * (k - 3 - len(t)) + b"\x00" + t
    return pow(s, e, n).to_bytes(k, "big") == expected


def verify_crx(data: bytes) -> list[tuple[str, bool]]:
    """(key-derived ID, signature valid) for every proof; ECDSA proofs report False (unverified)."""
    fields, signed, archive = _parse(data)
    message = _SIGNED_DATA_PREFIX + struct.pack("<I", len(signed)) + signed + archive
    results = []
    for number, payload in fields:
        if number not in (2, 3):
            continue
        proof = dict(_fields(payload))
        key, signature = proof.get(1, b""), proof.get(2, b"")
        if not key:
            continue
        ok = number == 2 and _rsa_pkcs1_sha256_ok(key, signature, message)
        results.append((_to_id(hashlib.sha256(key).hexdigest()), ok))
    return results


def main(argv: list[str]) -> int:
    expect = None
    if "--expect" in argv:
        i = argv.index("--expect")
        if i + 1 >= len(argv):
            print("usage: crx_id.py FILE.crx [--expect EXTENSION_ID]", file=sys.stderr)
            return 2
        expect = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 1:
        print("usage: crx_id.py FILE.crx [--expect EXTENSION_ID]", file=sys.stderr)
        return 2
    with open(argv[0], "rb") as f:
        data = f.read()
    declared, _ = crx_ids(data)
    proofs = verify_crx(data)
    print(f"declared ID: {declared}")
    for key_id, ok in proofs:
        print(f"key {key_id}: signature {'VALID' if ok else 'NOT VERIFIED'}{'  (declared key)' if key_id == declared else ''}")
    genuine = any(key_id == declared and ok for key_id, ok in proofs)
    if expect is not None and declared != expect:
        print(f"RESULT: ID mismatch - expected {expect}")
        return 1
    print("RESULT: signature by the declared key is valid" if genuine else "RESULT: NOT VERIFIED - do not trust")
    return 0 if genuine else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
