# How the four-bitplane patch works

This describes why Workbench 1.3 starts with two bitplanes, what goes wrong
when only the depth is changed, and what each patch does. Addresses are ROM
addresses for Kickstart 1.3 (34.5), mapped at `$FC0000`; the file offset is the
address minus `$FC0000`.

Evidence types are labelled:

- **Documented:** stated in contemporary Amiga manuals or the 1.3 include files.
- **Static:** found by reading the ROM bytes and disassembly.
- **Emulator:** observed in FS-UAE with its debugger. No real hardware was used.

## 1. Where the depth comes from

**Static.** When Intuition opens the Workbench screen (`OpenWorkBench()`), it
copies a 32-byte `NewScreen` template from `$FDE8A6` onto the stack. Its fields
are Left 0, Top 0, Width −1, Height −1, **Depth 2**, DetailPen 0, BlockPen 1,
ViewModes `HIRES`, and Type `WBENCHSCREEN`.

Before the screen is opened, the routine changes only two fields:

- if the Preferences flag `LaceWB` is set, it adds `LACE` to ViewModes;
- it replaces the width with Intuition's current display width.

The Depth word is used unchanged. The Preferences field `wb_Depth` is not read
on this path, so neither Preferences nor `DEVS:system-configuration` can
change the depth. The depth is a constant in the ROM.

**Emulator.** With the depth word changed to 4, Intuition opened a 640×512
screen with a four-plane bitmap. The Copper list set four bitplane pointers and
`BPLCON0 = $C204` (hires, four planes, interlace).

**Documented.** Four bitplanes (16 colours) is the OCS limit in high
resolution, so 4 is the largest useful value here.

## 2. Why the depth change alone crashes

With only the depth patched, Workbench boots and looks normal. But pressing the
mouse button on a drawer icon and then opening the drawer can crash, reset or
hang the machine.

**Static.** When an icon is pressed, `workbench.task` builds a GEL *Bob* (a
blitter object) for the drag image. It sizes the Bob's `SaveBuffer`, which
holds the screen background behind the dragged icon, from the icon image's
depth. That is 2 for every Workbench 1.3 icon.

**Documented and emulator.** `DrawGList()` saves the background for each plane
it draws into on the screen, which now has 4 planes. The blitter therefore
writes two planes' worth of data past the end of the buffer. The CPU never
sees these writes because the blitter makes them.

**Emulator.** For drawer icons, the overrun landed in the header of the large
free Chip RAM block and wiped it. The Chip RAM free list then held only a few
hundred bytes, while the memory header still reported about 800 KiB free. When
the drawer was opened, an allocation for icon images failed. The code that
loaded the icons did not check for that failure, and the image data was
copied to address 0. That overwrote the exception vectors and the ExecBase
pointer, and the system ran wild.

Icons that are highlighted by complementing kept the overrun inside their own
image copy, so they did not crash. They were only drawn in odd colours while
dragged.

## 3. Patch: a SaveBuffer for four planes

Two instructions read the icon depth (`VSprite.Depth`) when the drag Bob's
memory is laid out:

| Address | Before | After |
| --- | --- | --- |
| `$FF2D0C` | `MOVE.W $1E(A3),D1` | `MOVEQ #4,D1 ; NOP` |
| `$FF2D5C` | `MOVE.W $1E(A3),D0` | `MOVEQ #4,D0 ; NOP` |

The first computes the size of the allocation, and the second computes where
the rest of the Bob's data starts after the SaveBuffer. Both now use 4 planes.
Both replacements have the same length as the originals, so no code moves.

**Static.** The memory is freed with the size recorded at allocation time, so
nothing else needs to change. No other part of `workbench.task` derives a
buffer layout from that depth.

**Emulator.** The Chip RAM free list stayed consistent through repeated drags,
opening several drawers, and overlapping windows. After a drag, free Chip RAM
returned to exactly its earlier value, so there was no leak.

The constant 4 matches the high-resolution limit. A deeper low-resolution
Workbench would need a larger value.

## 4. Patch: drag-image colours

With the SaveBuffer fixed, icons that are highlighted by complementing (such as
disk icons) were drawn in light purple while dragged.

**Static.** An Amiga image has `PlanePick` (which planes get image data) and
`PlaneOnOff` (what to do with the other planes). For the drag image, Workbench
sets the Bob's `PlaneOnOff` to the complement of the icon's value. All the 75
icons checked on the Workbench and Extras 1.3 disks use PlanePick `$03` and
PlaneOnOff `$00`. On a four-plane screen, the complement therefore fills
planes 2 and 3, which selects colours 4–15. Workbench never sets those
colours.

| Address | Before | After |
| --- | --- | --- |
| `$FF2D7E` | `MOVE.B $F(A2),D0 ; MOVE.L D0,D7 ; NOT.L D7` | `MOVEQ #3,D7 ; MOVE.B $F(A2),D0 ; EOR.B D0,D7` |

The new code computes `PlaneOnOff ^ 3`. Planes 0–1 are still inverted as
before, and planes 2–3 are cleared. The replacement has the same length.
Static checks confirmed that the registers are not used again afterwards and
that no branch jumps into the patched bytes.

**Emulator.** Dragged icons then looked the same as with the original
two-plane ROM.

## 5. The Kickstart checksum

**Static.** Kickstart verifies its ROM at startup. The sum of all 32-bit
longwords, where each carry out of bit 31 is added back in (end-around carry),
must be `$FFFFFFFF`. The checksum longword at `$FFFFE8` makes this true. After
patching, the script sets it to zero, sums the image, and stores the
complement of the sum.

## 6. Colours 4–15

**Documented.** The 1.3 `Preferences` structure has only `color0`–`color3` for
Workbench. Intuition applies these four colours to the Workbench screen and
does nothing with the others.

**Emulator.** At boot, entries 4–15 of the Workbench colour map held leftover
values that Workbench never sets. Extras `Tools/Palette` showed 16 colours and
could change them live, but the changes were lost after a reset.

Making colours 4–15 persistent would need something extra, such as a small
program run from `S:Startup-Sequence` after `LoadWB`, or more ROM changes.
This project does not do that yet.

## 7. Open questions

- Behaviour on a pure OCS chipset, with 512 KiB Chip RAM, without Fast RAM,
  and on real hardware.
- The effect of a nonzero `wb_Depth` in Preferences. It is not read on the
  traced path, but other code was not examined for it.
- Third-party programs that assume a two-plane Workbench.

## References

- *Amiga ROM Kernel Reference Manual: Includes and Autodocs* (1.3):
  `OpenScreen()`, `SetPrefs()`, `SetRGB4()`, and the 1.3 `Preferences` layout.
- *Amiga Intuition Reference Manual*: Workbench screen, display modes and
  Preferences.
- Weltner, Trapp, Jennrich, *Amiga Graphics Inside & Out* (Abacus, 1988):
  bitplane limits, GELs, Bobs and the `SaveBuffer`.
- 1.3 include files `intuition/screens.h`, `intuition/preferences.h`,
  `graphics/gels.h`, `graphics/gfx.h`, `graphics/view.h`.
