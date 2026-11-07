# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import hashlib
import struct
import unittest

from tools.audit import crx_id


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _field(num, payload: bytes):
    return _varint((num << 3) | 2) + _varint(len(payload)) + payload


class CrxIdTests(unittest.TestCase):
    def test_ids_from_handmade_crx3(self):
        key = b"K" * 32
        digest = hashlib.sha256(key)
        proof = _field(1, key) + _field(2, b"sig")
        signed = _field(1, digest.digest()[:16])
        hdr = _field(2, proof) + _field(10000, signed)
        data = b"Cr24" + struct.pack("<II", 3, len(hdr)) + hdr
        expected = "".join("abcdefghijklmnop"[int(c, 16)] for c in digest.hexdigest()[:32])
        declared, derived = crx_id.crx_ids(data)
        self.assertEqual(declared, expected)
        self.assertEqual(derived, [expected])

    def test_rejects_non_crx(self):
        with self.assertRaises(ValueError):
            crx_id.crx_ids(b"PK\x03\x04")


if __name__ == "__main__":
    unittest.main()
