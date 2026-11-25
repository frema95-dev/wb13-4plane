#!/usr/bin/env python3
"""Patch a Kickstart 1.3 (34.5) ROM image for a four-bitplane Workbench.

The script changes the Workbench screen depth from 2 to 4 bitplanes and fixes
two Workbench routines that otherwise misbehave on a deeper screen. See
README.md and docs/HOW_IT_WORKS.md.

You must supply your own Kickstart 1.3 (34.5) ROM image. The input is
identified by its SHA-256 and is never modified. An existing output file is
never overwritten. The output must be byte-identical to the image that was
tested, otherwise nothing is written.

Usage:
  python3 patch_wb4plane.py --input KICK13.ROM --output KICK13-4PLANE.ROM
  python3 patch_wb4plane.py --list

Requires Python 3.8 or later and only the standard library.
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROM_SIZE = 0x40000           # 256 KiB, mapped at $FC0000
ROM_BASE = 0xFC0000
CHECKSUM_OFFSET = 0x3FFE8    # Kickstart checksum longword

# Kickstart 1.3 (34.5) as used on the A500/A1000/A2000.
INPUT_SHA256 = "ee05862d8102a08436ac4056da7d549db31625c7d47b24dfb7b3c9a5c113ca53"
INPUT_SHA1 = "891e9a547772fe0c6c19b610baf8bc4ea7fcb785"
INPUT_CRC32 = "c4f0f55f"

# (stage, file offset, replacement bytes, description)
# The original bytes are not listed: the SHA-256 check above already
# guarantees the exact input. Use --list to show the patches.
PATCHES = [
    ("depth", 0x1E8AE, "0004",
     "Workbench NewScreen template: Depth = 4"),
    ("bob", 0x32D0C, "72044e71",
     "drag Bob size: MOVEQ #4,D1 ; NOP  (SaveBuffer for 4 planes)"),
    ("bob", 0x32D5C, "70044e71",
     "drag Bob layout: MOVEQ #4,D0 ; NOP  (image after 4-plane SaveBuffer)"),
    ("full", 0x32D7E, "7e03102a000fb107",
     "drag image PlaneOnOff: MOVEQ #3,D7 ; MOVE.B $F(A2),D0 ; EOR.B D0,D7"),
]

STAGES = ["depth", "bob", "full"]

# SHA-256 of the result for each stage. "full" is the recommended image;
# "depth" alone is known to corrupt Chip RAM when an icon is dragged.
EXPECTED = {
    "depth": "7fa9f2ebc9603f8120339ccf6fdc58128017a9986bf586db30831d4c31d1c577",
    "bob": "f5920fadb7d54790eef93a4934182acfad9a2b4503de43878a02c0aafab90e82",
    "full": "2be86109cca7fc6a0d7d80a1d59e43e1d6738b6943da8a6f7aea862759fe1541",
}


def fail(msg):
    sys.exit(f"error: {msg}")


def kick_sum(data):
    """32-bit sum of all longwords with end-around carry."""
    total = 0
    for o in range(0, len(data), 4):
        total += int.from_bytes(data[o:o + 4], "big")
        total = (total & 0xFFFFFFFF) + (total >> 32)
    return total


def fix_checksum(data):
    data[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 4] = bytes(4)
    data[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 4] = (
        (~kick_sum(data)) & 0xFFFFFFFF).to_bytes(4, "big")
    if kick_sum(data) != 0xFFFFFFFF:
        fail("checksum correction failed")


def explain_unknown(data):
    """Return a hint for common reasons why an input is not recognized."""
    if data.startswith(b"AMIROMTYPE1"):
        return ("this looks like an encoded Amiga Forever ROM (it needs "
                "rom.key). Decode it with Amiga Forever's own tools first.")
    if len(data) == 2 * ROM_SIZE and data[:ROM_SIZE] == data[ROM_SIZE:]:
        if hashlib.sha256(data[:ROM_SIZE]).hexdigest() == INPUT_SHA256:
            return ("this is a 512 KiB file holding the ROM twice. Use the "
                    "first 256 KiB only.")
        return "this is a 512 KiB file holding a 256 KiB image twice."
    if len(data) == ROM_SIZE and data[:4] == bytes.fromhex("1111f94e"):
        return "this image appears to be byte-swapped (16-bit words swapped)."
    if len(data) != ROM_SIZE:
        return f"size is {len(data)} bytes; a Kickstart 1.3 image is {ROM_SIZE}."
    if data[:4] == bytes.fromhex("11114ef9"):
        return "this is a 256 KiB Kickstart image, but not version 34.5."
    return "the file does not look like a Kickstart 1.3 (34.5) image."


def romtool_check(path):
    """Optional structural check with amitools' romtool."""
    if shutil.which("romtool") is None:
        fail("--romtool given, but romtool (amitools) is not installed")
    out = subprocess.run(["romtool", "info", str(path)], check=True,
                         capture_output=True, text=True).stdout
    fields = dict(l.split(None, 1) for l in out.splitlines() if l.strip())
    for key in ("size", "header", "footer", "size_field", "chk_sum",
                "magic_reset", "is_kick"):
        if fields.get(key) != "ok":
            fail(f"romtool {key}: {fields.get(key)}")
    for key, want in (("base_addr", "00fc0000"), ("boot_pc", "00fc00d2"),
                      ("rom_rev", "34.5"), ("exec_rev", "34.2")):
        if fields.get(key) != want:
            fail(f"romtool {key}: {fields.get(key)} != {want}")
    print("romtool: structural checks ok")


def selected(stage):
    return [p for p in PATCHES if STAGES.index(p[0]) <= STAGES.index(stage)]


def list_patches(stage):
    print(f"Input: Kickstart 1.3 (34.5), {ROM_SIZE} bytes")
    print(f"  SHA-256 {INPUT_SHA256}")
    print(f"  SHA-1   {INPUT_SHA1}")
    print(f"  CRC32   {INPUT_CRC32}")
    print(f"Patches up to stage '{stage}':")
    for st, off, new, what in selected(stage):
        print(f"  [{st:5}] file ${off:05X}  ROM ${ROM_BASE + off:06X}  "
              f"-> {new}  {what}")
    print(f"  [chk  ] file ${CHECKSUM_OFFSET:05X}  ROM "
          f"${ROM_BASE + CHECKSUM_OFFSET:06X}  Kickstart checksum recomputed")
    print(f"Output SHA-256: {EXPECTED[stage]}")


def main():
    ap = argparse.ArgumentParser(
        description="Patch Kickstart 1.3 (34.5) for a four-bitplane Workbench.")
    ap.add_argument("--input", help="your Kickstart 1.3 (34.5) ROM image")
    ap.add_argument("--output", help="new file to create (never overwritten)")
    ap.add_argument("--stage", choices=STAGES, default="full",
                    help="apply patches up to this stage (default: full; "
                         "'depth' alone is unsafe and only for testing)")
    ap.add_argument("--list", action="store_true",
                    help="show the patches and exit without reading a ROM")
    ap.add_argument("--romtool", action="store_true",
                    help="also check the result with amitools' romtool")
    a = ap.parse_args()

    if a.list:
        list_patches(a.stage)
        return
    if not a.input or not a.output:
        ap.error("--input and --output are required (or use --list)")

    src, out = Path(a.input), Path(a.output)
    if out.exists():
        fail(f"refusing to overwrite {out}")
    original = src.read_bytes()

    digest = hashlib.sha256(original).hexdigest()
    if digest != INPUT_SHA256:
        fail(f"input SHA-256 {digest} is not Kickstart 1.3 (34.5): "
             f"{explain_unknown(original)}")
    if kick_sum(original) != 0xFFFFFFFF:
        fail("input Kickstart checksum is invalid")

    patches = selected(a.stage)
    data = bytearray(original)
    allowed = set(range(CHECKSUM_OFFSET, CHECKSUM_OFFSET + 4))
    for _, off, new, _ in patches:
        new_b = bytes.fromhex(new)
        data[off:off + len(new_b)] = new_b
        allowed |= set(range(off, off + len(new_b)))
    fix_checksum(data)

    changed = {o for o in range(ROM_SIZE) if original[o] != data[o]}
    if not changed <= allowed:
        fail(f"unexpected changes at {sorted(hex(o) for o in changed - allowed)}")

    result = hashlib.sha256(data).hexdigest()
    if result != EXPECTED[a.stage]:
        fail(f"output SHA-256 {result} differs from the tested image "
             f"{EXPECTED[a.stage]}; nothing written")

    with open(out, "xb") as f:   # "x": fail if the file appeared meanwhile
        f.write(data)
    if a.romtool:
        romtool_check(out)

    print(f"input:  {src.name}  sha256={digest}")
    for st, off, new, what in patches:
        print(f"  [{st:5}] ROM ${ROM_BASE + off:06X}  "
              f"{original[off:off + len(new) // 2].hex()} -> {new}  {what}")
    print(f"  [chk  ] ROM ${ROM_BASE + CHECKSUM_OFFSET:06X}  "
          f"{original[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 4].hex()} -> "
          f"{data[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 4].hex()}")
    print(f"changed bytes: {len(changed)}")
    print(f"output: {out.name}  sha256={result}  (matches tested image)")
    if a.stage != "full":
        print(f"warning: stage '{a.stage}' is incomplete; use 'full' for normal use")


if __name__ == "__main__":
    main()
