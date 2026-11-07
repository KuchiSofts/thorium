# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import struct
import unittest
import zlib

from tools.branding import ico


def make_png(width: int, height: int) -> bytes:
    """Minimal valid RGBA PNG filled with one colour."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    row = b"\x00" + b"\x7b\x2f\xf7\xff" * width
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(row * height)) + chunk(b"IEND", b""))


class IcoTests(unittest.TestCase):
    def test_pack_and_read_roundtrip(self):
        data = ico.pack_ico({256: make_png(256, 256), 16: make_png(16, 16)})
        self.assertTrue(data.startswith(b"\x00\x00\x01\x00"))
        self.assertEqual(ico.read_ico_sizes(data), [16, 256])

    def test_rejects_unsupported_size(self):
        with self.assertRaises(ValueError):
            ico.pack_ico({20: make_png(20, 20)})

    def test_rejects_mismatched_png(self):
        with self.assertRaises(ValueError):
            ico.pack_ico({32: make_png(16, 16)})

    def test_png_size_rejects_non_png(self):
        with self.assertRaises(ValueError):
            ico.png_size(b"GIF89a")

    def test_png_size_reads_ihdr(self):
        self.assertEqual(ico.png_size(make_png(48, 24)), (48, 24))


if __name__ == "__main__":
    unittest.main()
