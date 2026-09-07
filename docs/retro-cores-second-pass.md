# Retro cores, second pass: twelve more systems fitted, and what each needs to be playable through the GUI

Written 2026-09-07. The first pass ([retro-cores.md](retro-cores.md)) fitted
GB/GBC, SNES, GBA, PSX and N64. This pass takes everything else MiSTeX
already ports that is a console or a computer, plus the MiSTer consoles
MiSTeX does not port yet — the Saturn and Mega Drive among them — through the
same out-of-context synthesis on both dies, and then answers the second
question: with the host path now built (`hps_pcie` bridge, `video_sink`,
`retroview`, Main_MiSTeX on x86-64 — [host-gui-compatibility.md](host-gui-compatibility.md)),
what does each system still need before a game loads and plays from the menu
on an Ubuntu or Windows PC.

Everything under "measured" was produced by `tools/core-fit.py` with Vivado
2026.1 on 2026-09-06/07. Nothing here has been on hardware; the C1100 is
busy with other work.

## Measured: out-of-context synthesis of `emu`

| system | upstream (commit) | LUTs xcu55n (C1100) | LUTs xcvu33p (FK33) | FF | BRAM | URAM | DSP | WNS ns (u55n / vu33p) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **Sega Saturn** | Saturn_MiSTer `74d50c0` | 48,584 (5.6 %) | 48,584 (11.1 %) | 28,887 | 36.5 | 0 | 31 | +4.98 / +5.55 |
| **Sega Mega Drive / Genesis** | Genesis_MiSTer `adc0c42` | 16,770 (1.9 %) | 16,770 (3.8 %) | 14,141 | 14.5 | 0 | 19 | +4.42 / +5.41 |
| PC Engine / TurboGrafx-16 (+CD) | TurboGrafx16_MiSTer `827d45f` | 22,983 (2.6 %) | 22,983 (5.2 %) | 17,882 | 76.5 | 0 | 18 | +6.13 / +7.29 |
| Sega Master System / Game Gear | MiSTeX SMS over SMS_MiSTer `1dee74f` | 13,629 (1.6 %) | 13,629 (3.1 %) | 16,574 | 40.5 | 0 | 2 | +8.73 / +7.28 |
| SNK Neo Geo (AES/MVS/CD) | MiSTeX NeoGeo over NeoGeo_MiSTer `974e0e7` | 11,964 (1.4 %) | 11,964 (2.7 %) | 9,553 | 78.5 | 0 | 1 | +6.44 / +5.64 |
| Atari Lynx | AtariLynx_MiSTer `3708e45` | 10,388 (1.2 %) | 10,388 (2.4 %) | 9,813 | 44 | 0 | 8 | +11.10 / +11.14 |
| Bandai WonderSwan / Color | WonderSwan_MiSTer `7130fab` | 14,131 (1.6 %) | 14,131 (3.2 %) | 11,208 | 64.5 | 0 | 7 | +14.13 / +14.97 |
| Atari 7800 (+2600) | Atari7800_MiSTer `8c96e1f` | 37,219 (4.3 %) | 37,219 (8.5 %) | 22,316 | 90.5 | 0 | 42 | +7.19 / +6.45 |
| Atari 2600 (standalone, 2022) | Atari2600_MiSTer `59411dc` | not fitted — its 2020-framework `sys/hps_io.v` declares after use in a dozen places (Vivado stops at each); superseded by the 7800 core's built-in 2600 above, so it was not pursued further | | | | | | |
| Commodore 64 | MiSTeX C64 over C64_MiSTer `8a5b899` | 12,293 (1.4 %) | 12,293 (2.8 %) | 10,214 | 22.5 | 0 | 7 | +10.94 / +11.66 |
| Amstrad CPC | MiSTeX Amstrad over Amstrad_MiSTer `53943a6` | 9,011 (1.0 %) | 9,011 (2.1 %) | 6,976 | 12.5 | 0 | 0 | +12.53 / +11.52 |
| Commodore Amiga (Minimig-AGA) | MiSTeX Minimig-AGA over `99ac3ce` | 18,054 (2.1 %) | 18,054 (4.1 %) | 14,341 | 9.5 | 2 | 32 | +2.79 / +2.32 |

Every one that synthesised closes timing at its own clocks on both dies,
with margin; the tightest is the Amiga's 113.5 MHz RAM clock at +2.3 ns.
The Atari 7800 row is the 2600 result too: that core carries the maintained
2600 (`cart2600.sv`, `banks2600.sv`, `detect2600.sv`). Together with the
first pass (GB 12k, SNES ~30k, GBA 38k, PSX 46k, N64 ~60k) the whole library
of fitted systems is under 400k LUTs — less than half of the C1100. Logic is
not the constraint on these cards for anything before the PS2.

Clocks come from `-xilinxusp` MMCM shims in each core's overlay, with the
integer-ratio nearest to the Altera fractional PLL: within 0.04 % everywhere
except the Saturn (−0.012 %) and Neo Geo (−0.005 %), which happen to land
closer. Exact console rates that are not integer-reachable from 50 MHz
(WonderSwan's 36.864, the Ataris' 3.579545 multiples) are marked in the shims.

## What each holds in external memory

This is what the memory bridge ([retro-cores.md](retro-cores.md) item 1) has
to provide per system, read from each top's `SDRAM_*`, `SDRAM2_*` and
`DDRAM_*` use and the core's own documentation. Sizes are MiSTer's documented
limits, not measured here.

| system | SDRAM | second SDRAM | DDRAM |
|---|---|---|---|
| Saturn | work RAM, VDP RAM, sound RAM, cart; MiSTer requires the 128 MB module | used | CD sectors, VDP1/VDP2 buffers (`DDRAM_*` ×10 in the top) — the heaviest DDRAM user of the consoles |
| Mega Drive | cart ROM (up to 10 MB with mappers), SRAM | optional (Mega CD / MSU-MD) | framebuffer, Mega CD RAM, MSU audio |
| TurboGrafx-16 | none — the top uses no SDRAM port | — | HuCard ROM and CD data both in DDRAM |
| Master System | cart ROM, RAM | optional | framebuffer |
| Neo Geo | cartridge P/C/S/M/V ROMs (the large `SDRAM_*` ×57 use) | used for bigger C ROMs | CD, big carts (`DDRAM_*` ×13) |
| Lynx, WonderSwan | cart ROM (Peip `sdram.sv`, same as GBA) | — | savestates, rewind |
| Atari 7800 / 2600 | 7800: none; 2600: cart in SDRAM | — | 7800: cart ROM and BIOS in DDRAM |
| C64 | machine RAM, REU (512 KB–16 MB), GeoRAM (4 MB) | — | framebuffer |
| Amstrad | RAM and ROM slots | — | unused |
| Amiga | chip ≤ 2 MB, slow ≤ 1.5 MB, 24-bit fast ≤ 8 MB | — | 32-bit fast RAM up to 384 MB, framebuffer with palette — depends on the HBM bridge more than any console |

On these cards every SDRAM footprint above fits in URAM (the largest, the
Saturn's 128 MB requirement, is a MiSTer sizing convention for the module,
not what the core touches; what it touches is a few MB, which is
unverified here) and everything DDRAM-side goes to HBM behind the shared
`DDRAM_*` bridge. Nothing in this table needs a design that does not already
exist in plan; the Amiga's 384 MB fast RAM is the one that makes the HBM
bridge mandatory rather than convenient.

## Playable through the GUI: what each system's loader needs

Main_MiSTeX loads a game one of three ways, and which one a system uses
decides whether it works over the transport built this week or waits for the
DMA-backed `shmem`:

1. **File upload through `hps_io`** (`user_io_file_tx`: the file is streamed
   as `ioctl_*` words over the HPS bus). Works today over `hps_pcie`; a 4 MB
   ROM is a few seconds of register writes and will move to the DMA path
   later for speed.
2. **Block-device mounts through `hps_io`** (`user_io_file_mount`: the core
   requests sectors, Main serves them from the image over the same bus).
   Also works today. CD images (CHD/CUE) for the PC Engine CD and Mega CD
   go this way through `support/pcecd` and `support/megacd`, which use no
   shared memory.
3. **Direct writes into the FPGA's DDR** (`shmem_map` / `shmem_put` onto a
   fixed address such as `0x31000000`). Stubbed in the port until the HBM
   bridge exposes a host-mappable window; five Main modules use it.

| system | loader path | works over the bridge now? | notes |
|---|---|---|---|
| Mega Drive | 1 (ROM); Mega CD: 2 | yes | `support/megacd` streams sectors over the bus |
| PC Engine / TG-16 | 1 (HuCard); CD: 2 | yes | `support/pcecd` likewise |
| Master System / Game Gear | 1 | yes | |
| Lynx, WonderSwan, 7800, 2600 | 1 | yes | the standalone 2600 core is on the 2020 framework (old `hps_io`); use the 7800 core's built-in 2600 instead |
| C64 | 1 and 2 (D64/G64 images, tape, cart) | yes | tape ADC input is a stubbed `ltc2308` — no cassette audio on these cards |
| Amstrad | 1 and 2 (DSK, tape) | yes | same tape note |
| **Saturn** | 2 for the disc mount and backup RAM, **but** `support/saturn/saturncdd.cpp` moves CD sectors through `shmem_map(0x31000000)` | **no — waits for DMA-backed shmem** | the first system that needs the HBM bridge's host window |
| **Neo Geo** | `support/neogeo/neogeo_loader.cpp` writes cartridge ROMs with `shmem_map(fpga_mem(addr))`; CD via 2 | **no for cartridges** (CD games would load) | same dependency |
| Amiga | 2 (HDF/ADF); the optional host file share uses `shmem_map` | yes for disks; share waits | |

So of the twelve, ten load and play the moment a `sys_top` build exists, and
the two the user named first — Saturn and Neo Geo cartridges — are exactly
the two that also need the memory bridge's host-mappable window, which the
Amiga's fast RAM needs anyway. That window is a single piece of work
(a PCIe BAR or DMA target onto the HBM region behind `DDRAM_*`, and
`shmem.cpp` implemented over it) and it unblocks all three.

Beyond loading, every system in the table talks to Main through the same
`hps_io` commands the bridge was verified against (config string, status,
joysticks, keyboard/mouse for the computers, file and block I/O), and its
picture leaves through the same `video_sink`. The computers add keyboard and
mouse, which Main sends as PS/2 scan codes over the same bus (`UIO_KEYBOARD`,
`UIO_MOUSE`) — no new gateware. None of them needs anything Windows-specific
beyond the driver question already recorded.

## What it took this time

Shared fixes that every later core benefits from, all in the overlay:

- `rtl/altera_compat/scfifo.v` no longer puts its storage under the
  asynchronous clear: Vivado refuses to infer a RAM that is "sensitive to
  asynchronous reset" and dissolves it into registers — the Saturn's 128 Kbit
  CD-audio FIFO failed synthesis that way. Pointers take the clear, storage
  does not.
- `rtl/altera_compat/altdpram.v` accepts `rdaddressstall` / `wraddressstall`
  / `sclr` / `power_up_uninitialized` / `byte_size` (Saturn's MLAB wrappers
  connect them; never asserted by any core here).
- `tools/core-fit.py` reads SystemVerilog `*_pkg.sv` files before the files
  that import them (Saturn's `SCU/DSP.sv` sorts before `SCU/DSP_PKG.sv`).
- `tools/patch-regs.py`: the same declaration fix `patch-top.py` does for the
  top, for any file Vivado names (`procedural assignment to a non-register`).
- Board-side blocks that cores instantiate from inside `emu` although
  `core-fit.py` excludes them as `sys_top`'s business: `ltc2308_tape`
  (cassette ADC: C64, Amstrad, 7800) and `mt32pi` (Amiga) as stubs, and
  `iir_filter` (Amiga) as a copy. "Not available" is the right answer for a
  tape ADC on a PCIe card.

Per-core patches are in each `overlay/cores/<system>/MiSTeX.yaml` with the
reason beside every entry. The standalone Atari 2600 is on the 2020 MiSTer
framework with its own `sys/`; five of its files were patched or excluded in
the overlay before its `hps_io.v` (the old one, which declares `kbd_*` and
friends after using them) stopped the fit. The 7800 core, on the current
framework, carries the maintained 2600 and is the one to build; the 2600
overlay is left in place with the patches recorded for anyone who wants the
old core specifically. The 7800's own blocker was one SystemVerilog array
method (`header_array.sum()`) Vivado does not implement, spelled out in a
patched copy of `banks2600.sv`.

## Not fitted, and why

- **Mega CD, Sega 32X, PC Engine CD** are inside the Mega Drive and
  TurboGrafx-16 cores above, not separate.
- **Arcade** (`Arcade-jtcores` and the other `Arcade-*` MiSTeX ports) are
  a different, larger survey; they load through `support/arcade` MRA files,
  two of whose paths use `shmem_put`.
- **PS2 and GameCube**: [ps2-hardware-study.md](ps2-hardware-study.md); the
  IOP is built, the rest is the long road.
