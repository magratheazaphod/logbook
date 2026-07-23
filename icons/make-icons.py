#!/usr/bin/env python3
"""Render the Logbook app icon (a bespectacled log reading a book) to every
size the browser tab, the PWA manifest, and an iOS/macOS home-screen tile want.

    python3 icons/make-icons.py

The art lives here as one string so the four variants below can't drift apart:

  logbook.svg           rounded tile   -> icon-192/512.png, the <link rel=icon> SVG
  logbook-square.svg    full bleed     -> icon-180.png (iOS masks it itself, so
                                          transparent corners would go black)
  logbook-maskable.svg  full bleed, art at 80% inside the Android safe circle
  logbook-small.svg     simplified     -> favicon 16/32/48 + favicon.ico

Needs rsvg-convert (brew install librsvg); the .ico is assembled in pure Python.
Dev-time only — the server just serves the committed PNGs.
"""
import shutil
import struct
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent

PAPER = "#F1E6E4"   # app background
RIM = "#E8D6D3"     # tile edge, one step darker

# The character, drawn in a 100x100 field. Kept free of any background so each
# variant can supply its own (rounded tile / full bleed / safe-zone inset).
ART = """
  <!-- leaf sprig on top -->
  <path d="M52 17 Q53 12 51 8" fill="none" stroke="#6B4A31" stroke-width="1.3" stroke-linecap="round"/>
  <path d="M51 8 Q45 4 40 7 Q44 12 51 8 Z" fill="#7E9C60"/>
  <path d="M51 8 Q55 2 61 4 Q59 10 51 8 Z" fill="#8FAC6E"/>

  <!-- log, end-on: bark rim + tree rings -->
  <circle cx="50" cy="43" r="27" fill="#8A5A3B" stroke="#6B4A31" stroke-width="1.6"/>
  <g stroke="#6B4A31" stroke-width="1.2" stroke-linecap="round" fill="none">
    <path d="M28.5 32 l3.4 1.9"/>
    <path d="M71.5 32 l-3.4 1.9"/>
    <path d="M24 47 l3.9 -0.4"/>
    <path d="M76 47 l-3.9 -0.4"/>
    <path d="M33 63.5 l2.6 -2.9"/>
    <path d="M67 63.5 l-2.6 -2.9"/>
  </g>
  <circle cx="50" cy="43" r="22.5" fill="#EBD5B6"/>
  <circle cx="50" cy="43" r="18" fill="none" stroke="#D9B98C" stroke-width="1.5"/>
  <circle cx="50" cy="43" r="13" fill="none" stroke="#D9B98C" stroke-width="1.3"/>

  <!-- glasses -->
  <g fill="#F7EEDF" stroke="#3A2A20" stroke-width="1.5">
    <circle cx="42.5" cy="41" r="6"/>
    <circle cx="57.5" cy="41" r="6"/>
  </g>
  <path d="M48.5 41 Q50 39.8 51.5 41" fill="none" stroke="#3A2A20" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M36.5 40 L31 38.5" stroke="#3A2A20" stroke-width="1.3" stroke-linecap="round"/>
  <path d="M63.5 40 L69 38.5" stroke="#3A2A20" stroke-width="1.3" stroke-linecap="round"/>
  <circle cx="42.5" cy="42" r="2" fill="#3A2A20"/>
  <circle cx="57.5" cy="42" r="2" fill="#3A2A20"/>

  <!-- smile + blush -->
  <path d="M45.5 50 Q50 53.5 54.5 50" fill="none" stroke="#3A2A20" stroke-width="1.5" stroke-linecap="round"/>
  <ellipse cx="35.5" cy="49" rx="3" ry="1.8" fill="#E89A90" opacity="0.75"/>
  <ellipse cx="64.5" cy="49" rx="3" ry="1.8" fill="#E89A90" opacity="0.75"/>

  <!-- stub arms holding the book -->
  <g stroke="#6B4A31" stroke-width="4.6" stroke-linecap="round" fill="none">
    <path d="M30 58 L31.5 68"/>
    <path d="M70 58 L68.5 68"/>
  </g>

  <!-- open book: brick cover, then cream pages -->
  <path d="M50 73 C42 68.5 33 67.5 26 69.8 L26 84 C33 81.8 42 82.8 50 87.5
           C58 82.8 67 81.8 74 84 L74 69.8 C67 67.5 58 68.5 50 73 Z"
        fill="#B23A2E" stroke="#8E2B22" stroke-width="1"/>
  <path d="M50 72.5 C43 68.5 35.5 67.8 29 69.8 L29 81.5 C35.5 79.8 43 80.8 50 84.8 Z"
        fill="#FBF3E9" stroke="#3A2A20" stroke-width="0.9" stroke-linejoin="round"/>
  <path d="M50 72.5 C57 68.5 64.5 67.8 71 69.8 L71 81.5 C64.5 79.8 57 80.8 50 84.8 Z"
        fill="#FBF3E9" stroke="#3A2A20" stroke-width="0.9" stroke-linejoin="round"/>
  <g fill="none" stroke="#DACBB8" stroke-width="0.9" stroke-linecap="round">
    <path d="M33 73.4 C38 72.2 43.5 72.8 47 74.6"/>
    <path d="M33 76.6 C38 75.4 43.5 76.0 47 77.8"/>
    <path d="M53 74.6 C56.5 72.8 62 72.2 67 73.4"/>
    <path d="M53 77.8 C56.5 76.0 62 75.4 67 76.6"/>
  </g>
"""

# At 16px the rings, blush and ruled lines turn to mud. This variant keeps only
# what still reads: bark rim, two rings, glasses, and the book as a red wedge.
ART_SMALL = """
  <circle cx="50" cy="41" r="30" fill="#8A5A3B" stroke="#6B4A31" stroke-width="2.5"/>
  <circle cx="50" cy="41" r="24" fill="#EBD5B6"/>
  <circle cx="50" cy="41" r="17" fill="none" stroke="#D9B98C" stroke-width="2.5"/>
  <g fill="#F7EEDF" stroke="#3A2A20" stroke-width="2.6">
    <circle cx="41" cy="39" r="7.5"/>
    <circle cx="59" cy="39" r="7.5"/>
  </g>
  <path d="M48.5 39 H51.5" stroke="#3A2A20" stroke-width="2.6" stroke-linecap="round"/>
  <circle cx="41" cy="40" r="2.6" fill="#3A2A20"/>
  <circle cx="59" cy="40" r="2.6" fill="#3A2A20"/>
  <path d="M50 76 C41 70.5 30 69.5 22 72.5 L22 88 C30 85 41 86 50 92
           C59 86 70 85 78 88 L78 72.5 C70 69.5 59 70.5 50 76 Z"
        fill="#B23A2E" stroke="#8E2B22" stroke-width="1.6"/>
  <path d="M50 77 C42 72.5 33 71.8 26 74 L26 84.5 C33 82.5 42 83.3 50 87.5 Z" fill="#FBF3E9"/>
  <path d="M50 77 C58 72.5 67 71.8 74 74 L74 84.5 C67 82.5 58 83.3 50 87.5 Z" fill="#FBF3E9"/>
"""


def svg(background, art, scale=1.0, dy=0.0):
    """Wrap `art` on a background, scaled about the centre then nudged by dy.

    The art as drawn runs from y=2 (sprig tip) to y=87.5 (book), which clipped
    the top edge of the tile. Pulling it in to 92% and dropping it ~5 units
    leaves an even margin all round.
    """
    tx = f'transform="translate(0 {dy}) translate(50 50) scale({scale}) translate(-50 -50)"'
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" '
        'viewBox="0 0 100 100">\n'
        "  <!-- Generated by icons/make-icons.py — edit the art there, not here. -->\n"
        f"{background}\n  <g {tx}>{art}  </g>\n</svg>\n"
    )


TILE_BG = (
    f'  <rect x="4" y="4" width="92" height="92" rx="22" fill="{RIM}"/>\n'
    f'  <rect x="6" y="6" width="88" height="88" rx="20" fill="{PAPER}"/>'
)
FULL_BG = f'  <rect width="100" height="100" fill="{PAPER}"/>'

VARIANTS = {
    # name              background   art        scale  dy
    "logbook":         (TILE_BG,    ART,       0.92,  4.8),
    "logbook-square":  (FULL_BG,    ART,       0.92,  4.8),
    "logbook-maskable": (FULL_BG,   ART,       0.74,  3.8),
    "logbook-small":   (TILE_BG,    ART_SMALL, 0.90,  1.0),
}

# variant -> [(filename, pixel size), ...]
RENDERS = {
    "logbook": [("icon-192.png", 192), ("icon-512.png", 512)],
    "logbook-square": [("icon-180.png", 180)],
    "logbook-maskable": [("icon-maskable-512.png", 512)],
    "logbook-small": [("icon-16.png", 16), ("icon-32.png", 32), ("icon-48.png", 48)],
}


def main():
    rsvg = shutil.which("rsvg-convert")
    if not rsvg:
        sys.exit("rsvg-convert not found — brew install librsvg")

    for name, (bg, art, scale, dy) in VARIANTS.items():
        (OUT / f"{name}.svg").write_text(svg(bg, art, scale, dy), encoding="utf-8")
        print(f"{name}.svg")

    for name, targets in RENDERS.items():
        src = OUT / f"{name}.svg"
        for filename, size in targets:
            subprocess.run(
                [rsvg, "-w", str(size), "-h", str(size), str(src), "-o", str(OUT / filename)],
                check=True,
            )
            print(f"{filename} ({size}px)")

    write_ico(OUT / "favicon.ico", [OUT / f"icon-{n}.png" for n in (16, 32, 48)])
    print("favicon.ico (16/32/48)")


def write_ico(dest, pngs):
    """Bundle PNGs into a .ico.

    An ICO is a 6-byte header, one 16-byte directory entry per image, then the
    image payloads — and since Vista those payloads may be PNGs verbatim. So no
    image library is needed; we just concatenate. (ImageMagick would do this,
    but the local build is x86-only.)
    """
    blobs = [p.read_bytes() for p in pngs]
    offset = 6 + 16 * len(blobs)
    header = struct.pack("<HHH", 0, 1, len(blobs))
    entries = b""
    for png, blob in zip(pngs, blobs):
        # Side length is inferred from the filename; 256 is encoded as 0.
        size = int(png.stem.rsplit("-", 1)[1])
        entries += struct.pack(
            "<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(blob), offset
        )
        offset += len(blob)
    dest.write_bytes(header + entries + b"".join(blobs))


if __name__ == "__main__":
    main()
