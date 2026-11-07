# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Minimal PNG inspection and PNG-embedded Windows .ico packing (standard library only)."""
import struct

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        raise ValueError("not a PNG file")
    return struct.unpack(">II", data[16:24])


def pack_ico(pngs: dict[int, bytes]) -> bytes:
    """Pack square PNG images into one .ico; sizes must be in ICO_SIZES and match the PNGs."""
    for size, data in pngs.items():
        if size not in ICO_SIZES:
            raise ValueError(f"unsupported icon size {size}; allowed: {ICO_SIZES}")
        if png_size(data) != (size, size):
            raise ValueError(f"PNG for size {size} is {png_size(data)}")
    sizes = sorted(pngs)
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = len(header) + 16 * len(sizes)
    entries, images = b"", b""
    for size in sizes:
        data = pngs[size]
        dim = 0 if size == 256 else size  # 0 means 256 in the ICONDIRENTRY
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        images += data
        offset += len(data)
    return header + entries + images


def read_ico_sizes(data: bytes) -> list[int]:
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    if reserved != 0 or kind != 1:
        raise ValueError("not an .ico file")
    sizes = []
    for i in range(count):
        width = data[6 + 16 * i]
        sizes.append(256 if width == 0 else width)
    return sizes
