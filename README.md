# Four-bitplane (16-colour) Workbench for Kickstart 1.3

A small Python script that patches **your own** Kickstart 1.3 (34.5) ROM image
so that Workbench opens a four-bitplane high-resolution screen instead of the
usual two bitplanes. It also fixes two Workbench routines that misbehave on the
deeper screen: one of them corrupts Chip RAM.

**No ROM, Kickstart or Workbench files are included.** You must supply a ROM
image you are legally entitled to use.

## Status

This is an experiment. Read this section before you use the result.

| | |
| --- | --- |
| Tested | FS-UAE 3.1.66: A500, 68000, ECS Agnus (FS-UAE's default for A500), 1 MiB Chip RAM, 8 MiB Fast RAM, Workbench 1.3.4 disk |
| Not tested | Pure OCS chipset, 512 KiB Chip RAM, no Fast RAM, real hardware, EPROMs, other Workbench disks |
| Worked in the tests | Booting to a 640×512×4 Workbench; opening drawers; dragging icons (normal colours); moving, sizing and overlapping windows; Chip RAM free list stayed consistent; Extras `Tools/Palette` showed and changed 16 colours |

If you burn an EPROM, you do so at your own risk.

## Requirements

- Python 3.8 or later (standard library only).
- A Kickstart 1.3 rev 34.5 image (the A500/A1000/A2000 ROM):

  | | |
  | --- | --- |
  | Size | 262,144 bytes |
  | CRC32 | `c4f0f55f` |
  | SHA-1 | `891e9a547772fe0c6c19b610baf8bc4ea7fcb785` |
  | SHA-256 | `ee05862d8102a08436ac4056da7d549db31625c7d47b24dfb7b3c9a5c113ca53` |

  Some Amiga Forever editions and older installations store ROMs encoded
  (with a `rom.key` file). Such files must be decoded with Amiga Forever's own
  tools first. The script tells you if the input looks encoded, byte-swapped,
  or duplicated to 512 KiB.

- Optional: [amitools](https://github.com/cnvogelg/amitools) `romtool` for an
  extra structural check (`--romtool`).

## Usage

```sh
python3 patch_wb4plane.py --list                      # show what will change
python3 patch_wb4plane.py --input kick13.rom --output kick13-4plane.rom
```

The script:

1. refuses any input whose SHA-256 is not the one above;
2. applies the patches and recomputes the Kickstart checksum;
3. refuses to write unless the result is byte-identical to the tested image
   (SHA-256 `2be86109cca7fc6a0d7d80a1d59e43e1d6738b6943da8a6f7aea862759fe1541`);
4. never modifies the input and never overwrites an existing output.

`--stage depth` and `--stage bob` build the intermediate images used during
the investigation. They are for testing only: `depth` alone corrupts Chip RAM
as soon as a drawer icon is dragged.

## What changes

21 bytes change in total. File offsets are from the start of the ROM file; the
ROM is mapped at `$FC0000`.

| ROM address | File offset | Change | Why |
| --- | --- | --- | --- |
| `$FDE8AE` | `$1E8AE` | Depth `2` → `4` | Depth of the Workbench screen template |
| `$FF2D0C` | `$32D0C` | `MOVEQ #4,D1 ; NOP` | Drag-icon background buffer sized for 4 planes |
| `$FF2D5C` | `$32D5C` | `MOVEQ #4,D0 ; NOP` | Rest of the drag-icon buffer placed after the 4 planes |
| `$FF2D7E` | `$32D7E` | `PlaneOnOff ^ 3` | Dragged icons use colours 0–3 instead of 4–15 |
| `$FFFFE8` | `$3FFE8` | new checksum | The ROM must still pass the Kickstart checksum |

[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) explains how each patch was found and why it is needed.

## Known limitations

- **Colours 4–15 are not saved.** The 1.3 Preferences format stores only the
  four Workbench colours 0–3. Colours 4–15 can be changed at runtime (for
  example with Extras `Tools/Palette`), but they revert after a reset.
- **Icons still use four colours.** Workbench 1.3 icons are two-plane images.
- **More Chip RAM.** A 640×512 interlaced screen needs 160 KiB of bitplanes
  instead of 80 KiB (80 KiB instead of 40 KiB at 640×256). This has not been
  tried on a machine with only 512 KiB Chip RAM.
- **More display DMA.** Four high-resolution bitplanes are the OCS maximum.
  The extra display fetches leave fewer bus cycles for the CPU and blitter
  while the display is drawn, so Chip RAM-heavy work can slow down. This was
  not measured.
- Programs that assume a two-plane Workbench screen may look or behave
  differently. Only the operations listed under Status were tried.

## Legal

Kickstart and Workbench are copyrighted. This project does not distribute
them, or any part of them: the script contains only its replacement bytes and
checks the input by hash. Use it only with a ROM image you are entitled to use.
Amiga is a trademark of its respective owner; this project is not affiliated
with or endorsed by any rights holder.

## Licence

The script is released under the MIT licence (see [LICENSE](LICENSE)). The
documentation is released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The software is provided "as is", without warranty of any kind.
