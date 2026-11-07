# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import hashlib
import io
import os
import random
import shutil
import struct
import tempfile
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

    # --- review I7: real RSA signature verification ------------------------------------------
    def test_valid_rsa_signature_verifies(self):
        data, ext_id = _signed_crx(b"PK\x03\x04 archive bytes")
        self.assertEqual(crx_id.verify_crx(data), [(ext_id, True)])

    def test_tampered_archive_fails_verification(self):
        data, ext_id = _signed_crx(b"PK\x03\x04 archive bytes")
        tampered = data[:-1] + bytes([data[-1] ^ 1])
        self.assertEqual(crx_id.verify_crx(tampered), [(ext_id, False)])

    def test_forged_signature_with_real_key_fails(self):
        key = b"K" * 32
        proof = _field(1, key) + _field(2, b"sig")
        hdr = _field(2, proof) + _field(10000, _field(1, hashlib.sha256(key).digest()[:16]))
        data = b"Cr24" + struct.pack("<II", 3, len(hdr)) + hdr
        self.assertFalse(any(ok for _id, ok in crx_id.verify_crx(data)))

    def test_main_requires_valid_signature_and_expected_id(self):
        data, ext_id = _signed_crx(b"archive")
        tmp = tempfile.mkdtemp(prefix="thoron-test-")
        try:
            path = os.path.join(tmp, "x.crx")
            with open(path, "wb") as f:
                f.write(data)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(crx_id.main([path, "--expect", ext_id]), 0)
                self.assertEqual(crx_id.main([path, "--expect", "a" * 32]), 1)
        finally:
            shutil.rmtree(tmp)


# --- test helpers: tiny RSA (512-bit, test-only) and DER/CRX3 builders -------------------------
def _is_probable_prime(n, rounds=24):
    if n < 4:
        return n in (2, 3)
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        x = pow(random.randrange(2, n - 2), d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime(bits):
    while True:
        candidate = random.getrandbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if _is_probable_prime(candidate):
            return candidate


def _der(tag, content):
    n = len(content)
    length = bytes([n]) if n < 128 else bytes([0x80 | ((n.bit_length() + 7) // 8)]) + n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([tag]) + length + content


def _der_int(x):
    raw = x.to_bytes((x.bit_length() + 7) // 8 or 1, "big")
    return _der(0x02, (b"\x00" + raw) if raw[0] & 0x80 else raw)


def _signed_crx(archive: bytes):
    e = 65537
    while True:
        p, q = _prime(256), _prime(256)
        phi = (p - 1) * (q - 1)
        if p != q and phi % e:
            break
    n, d = p * q, pow(e, -1, (p - 1) * (q - 1))
    spki = _der(0x30, _der(0x30, bytes.fromhex("06092a864886f70d010101") + bytes.fromhex("0500"))
                + _der(0x03, b"\x00" + _der(0x30, _der_int(n) + _der_int(e))))
    digest = hashlib.sha256(spki)
    signed_header = _field(1, digest.digest()[:16])
    payload = b"CRX3 SignedData\x00" + struct.pack("<I", len(signed_header)) + signed_header + archive
    k = (n.bit_length() + 7) // 8
    t = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(payload).digest()
    em = b"\x00\x01" + b"\xff" * (k - 3 - len(t)) + b"\x00" + t
    sig = pow(int.from_bytes(em, "big"), d, n).to_bytes(k, "big")
    hdr = _field(2, _field(1, spki) + _field(2, sig)) + _field(10000, signed_header)
    ext_id = "".join("abcdefghijklmnop"[int(c, 16)] for c in digest.hexdigest()[:32])
    return b"Cr24" + struct.pack("<II", 3, len(hdr)) + hdr + archive, ext_id


if __name__ == "__main__":
    unittest.main()
