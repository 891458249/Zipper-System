# -*- coding: utf-8 -*-
"""Generate the Zipper System brand icon (no third-party deps).

Writes a 256x256 RGB PNG with a simple "zipper teeth" motif used as both the
PyInstaller .exe icon and the installer window icon. Run:

    python tools/make_icon.py

Output: modules/ZipperSystem/icons/ZipperSystem.png
"""

import os
import struct
import zlib

W = H = 256

BG = (24, 32, 44)          # dark slate
TEETH = (74, 200, 196)     # teal
SEAM = (236, 240, 241)     # near-white center seam


def _draw():
    px = bytearray()
    cx = W // 2
    tooth_h = 22
    tooth_gap = 10
    tooth_len = 64
    period = tooth_h + tooth_gap
    for y in range(H):
        row = bytearray()
        band = (y % period) < tooth_h
        # which side gets the tooth this band (interlock: alternate sides)
        left_band = ((y // period) % 2) == 0
        for x in range(W):
            r, g, b = BG
            # center seam line
            if abs(x - cx) <= 3:
                r, g, b = SEAM
            else:
                d = abs(x - cx)
                if band and d <= tooth_len:
                    on_left = x < cx
                    if (on_left and left_band) or ((not on_left) and not left_band):
                        # taper the tooth toward its tip for a tooth-like shape
                        tip = tooth_len * (1.0 - (y % period) / float(tooth_h))
                        if d <= max(8, tip):
                            r, g, b = TEETH
            # rounded-corner mask
            if _outside_rounded(x, y):
                r, g, b = (0, 0, 0)
            row += bytes((r, g, b))
        px += b"\x00" + row  # filter byte 0 per scanline
    return bytes(px)


def _outside_rounded(x, y):
    rad = 28
    for (cxr, cyr) in ((rad, rad), (W - rad, rad),
                       (rad, H - rad), (W - rad, H - rad)):
        inx = (x < cxr) if cxr < W / 2 else (x > cxr)
        iny = (y < cyr) if cyr < H / 2 else (y > cyr)
        if inx and iny:
            dx = x - cxr
            dy = y - cyr
            if dx * dx + dy * dy > rad * rad:
                return True
    return False


def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def main():
    raw = _draw()
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)  # 8-bit RGB
    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", ihdr)
           + _chunk(b"IDAT", zlib.compress(raw, 9))
           + _chunk(b"IEND", b""))
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(here, "modules", "ZipperSystem", "icons",
                       "ZipperSystem.png")
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    with open(out, "wb") as fh:
        fh.write(png)
    print("wrote", out, len(png), "bytes")


if __name__ == "__main__":
    main()
