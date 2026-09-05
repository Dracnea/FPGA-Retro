# Retro cores on the C1100 and FK33: SNES, GBA, PSX, N64 (and why not PS2)

What exists upstream for each console, what it needs from a board, what these
cards can give it, and what the out-of-context synthesis of each core on the
C1100's die actually measured. The FK33 has no display output either, so it
follows the C1100 flow exactly (PCIe video, PCIe host); the numbers below are
for the `xcu55n` unless a `xcvu33p` column says otherwise.

Everything under "measured" was produced by `tools/core-fit.py` on 2026-09-05
with Vivado 2026.1; everything else is read from the upstream sources named.

## The three things every core needs from these cards

None of the four cores can run until three board-side pieces exist, and they
are the same three for all of them — which is why they are worth building
once, before any core, rather than per core:

1. **Memory.** MiSTer cores assume a 16-bit SDRAM (32–128 MB) behind their own
   `sdram.sv` controller, and a 64-bit "DDRAM" burst interface (MiSTer's HPS
   DDR3, `DDRAM_*` ports) for the framebuffer, savestates and, in the Peip
   cores, the emulated console RAM itself. These cards have neither. They
   have ~28 MB (C1100) / ~14 MB (FK33) of on-chip BRAM+URAM and 8 GB of HBM2
   that LiteX already wraps (`litex.soc.cores.ram.xilinx_usp_hbm2.USPHBM2`:
   32 pseudo-channels, each a 256-bit AXI port at up to 450 MHz).
   The plan is a per-core `sdram.sv` replacement with the *same core-side
   ports* backed by URAM where the footprint allows and by one HBM channel
   where it does not, plus one shared `DDRAM_*` → HBM bridge. The
   controllers' SDRAM pad side is discarded.
2. **Video sink.** `VGA_R/G/B/HS/VS/DE` + `CE_PIXEL` at the core's pixel clock
   → line/frame buffer → the LitePCIe DMA that is already built and verified
   on hardware (`docs/c1100-pcie-transport.md`). The synthetic frame source in
   `c1100_pcie_video.py` is the slot this drops into.
3. **Host.** `hps_io` inside every core talks to the ARM over a 49-bit
   `HPS_BUS` (16-bit `io_din/io_dout`, `io_strobe`, `io_wide`, plus video and
   framebuffer status lines). MiSTeX replaced the ARM with an SPI bridge; here
   it becomes a register block on the PCIe BAR (the LitePCIe Wishbone bridge
   is in the transport already) and `Main_MiSTeX`'s `shmem_*` become DMA.

## Per console

| | SNES | GBA | PSX | N64 | PS2 |
|---|---|---|---|---|---|
| upstream | [SNES_MiSTer](https://github.com/MiSTer-devel/SNES_MiSTer) (MiSTeX has a Vivado port) | [GBA_MiSTer](https://github.com/MiSTer-devel/GBA_MiSTer) | [PSX_MiSTer](https://github.com/MiSTer-devel/PSX_MiSTer) | [N64_MiSTer](https://github.com/MiSTer-devel/N64_MiSTer) | **none exists** |
| author lineage | srg320 | Robert Peip | Robert Peip | Robert Peip (dev ended; community-maintained, last commit 2026-08) | — |
| core clocks (MHz) | 85.909 / 42.955 (SDRAM/sys) / 21.477 | 100.663 / 50.332 | 33.869 / 67.738 / 101.606 + 53.693 | 62.5 / 93.75 / 125 / 62.5 + 48.68 | — |
| SDRAM use | ROM ≤ 8 MB, WRAM, SRAM (32 MB module) | cart ROM ≤ 32 MB (64 MB carts and ≥ 32 MB on small modules go to DDR3) | main RAM / BIOS; optional second module | cart ROM (up to 64 MB) + SRAM/FLASH; second module for larger carts | — |
| DDRAM use | framebuffer only | ROM staging (copied to SDRAM), savestates | VRAM (1 MB) and CD data, savestates | **RDRAM (4/8 MB) — "the SDRAM has no chance" (Peip)**, framebuffer | — |
| on-chip-only feasible? | yes on both cards (≤ 9 MB) | C1100 yes for ≤ 16 MB carts, FK33 marginal; 32/64 MB carts need HBM | RAM/VRAM/BIOS ~4 MB yes; CD image streams from host | RDRAM 8 MB yes; cart ROM needs HBM on FK33, marginal on C1100 | — |
| Altera cells used | altsyncram, lpm_mult/divide, scfifo, dcfifo, altddio_out | altsyncram, altddio_out | altsyncram, altdpram, altddio_out | altsyncram, altdpram, altshift_taps, altera_mult_add (64×64), altddio_out, `cyclonev_lcell_comb` in the PLL reconfig | — |

**PS2:** there is no PlayStation 2 core for MiSTer or any other FPGA platform,
and the MiSTer forum's assessment is that none is coming — the Emotion Engine
(MIPS III + two VU vector units) and the Graphics Synthesizer are an order of
magnitude past the Saturn, which is itself the hardest thing on MiSTer. The
one "PS2 on MiSTer" item is a hybrid: the decompiled PS2 Street Fighter III
running on the ARM with the FPGA doing audio/video. PCSX2 on the host GPU is
the honest answer for PS2; nothing here changes that.

## What it took to get the four cores through Vivado

MiSTer cores are Quartus code. Three classes of thing stopped Vivado 2026.1
cold, all fixed in the overlay without editing an upstream file:

- **Intel megafunctions.** `overlay/rtl/altera_compat/` supplies `altsyncram`,
  `altdpram`, `lpm_mult`, `lpm_divide`, `scfifo`, `dcfifo`, `altshift_taps`,
  `altera_mult_add`, `altddio_out` and a Series-7-named `ODDR` as plain
  Verilog with the same names, parameters and ports, so the thin wrappers the
  Peip cores share (`dpram.vhd`, `SyncRamDualByteEnable.vhd`, `RamMLAB.vhd`,
  `Shiftreg.vhd`, `cpu_mul.vhd`) synthesise unmodified. One semantic gap is
  documented there (same-port read-during-write returns old data).
- **Quartus-only Verilog.** `inout reg` ports (every `sdram.sv`), procedural
  writes to ports and wires declared without `reg` (every top), and PSX's
  ports arriving through `sys/emu_ports.vh`. `tools/patch-top.py` fixes the
  declarations from the errors Vivado reports and writes MiSTeX-style patched
  copies into the overlay.
- **XPM.** MiSTeX's SNES `dpram_dif.vhd` instantiates `xpm_memory_tdpram` in
  write-first mode with `WRITE_PROTECT 0`, which Vivado 2026.1 refuses;
  the overlay copy sets it to 1.
- **PLLs.** Six MMCME4_ADV shims (`overlay/cores/*/rtl/pll*_0002-xilinxusp.v`),
  generated from each Altera PLL's output table; the worst frequency error is
  0.043 % (PSX), N64's is exact. The runtime-reconfigurable ones (SNES, PSX
  pll2, N64 pll2) pass the DRP bus through but need an UltraScale+-aware
  sequencer before any core retunes at runtime.

`tools/core-fit.py <MiSTeX-ports> <core> <part>` resolves the source list the
way MiSTeX does, applies the above, and synthesises `emu` out of context with
`CLK_50M` constrained at 50 MHz, so the MMCM-derived clocks are timed at the
core's real rates.

## Measured: out-of-context synthesis of `emu`

| core | part | CLB LUTs | registers | BRAM tiles | URAM | DSPs | slowest clock (post-synth) | result | black boxes |
|---|---|---|---|---|---|---|---|---|---|
| GBA | xcu55n | — | — | — | — | — | — | FAILED | 0 |
| N64 | xcu55n | — | — | — | — | — | — | FAILED | 0 |
| PSX | xcu55n | — | — | — | — | — | — | FAILED | 0 |
| SNES | xcu55n | 13846 (1.59 %) | 10175 (0.58 %) | 20.5 (1.53 %) | 0 (0.00 %) | 23 (0.39 %) | 21.5 MHz clock: WNS +20.61 ns (fmax ≈ 39 MHz) | clean | 1 |
| SNES | xcvu33p | 13846 (3.15 %) | 10175 (1.16 %) | 20.5 (3.05 %) | 0 (0.00 %) | 23 (0.80 %) | 21.5 MHz clock: WNS +19.50 ns (fmax ≈ 37 MHz) | clean | 1 |

GBA, PSX and N64 rows marked FAILED are still being carried through the
Quartus-to-Vivado port at the time of writing (each round removes one class of
construct; the SNES needed three). The table is regenerated by
`tools/fit-summary.py build`.

Read these as *fit and post-synthesis timing*, not as a bitstream: place and
route on a full board design will move WNS, and a core that closes at
synthesis with margin is the one to take forward first.

## Order of work

1. **SNES first.** Smallest memory footprint, MiSTeX has already ported its
   RAMs, everything fits on-chip on both cards, and it is the one console
   whose SDRAM traffic (ROM reads) is trivially served from URAM.
2. **GBA second** — the same on-chip story for the common ≤ 16 MB carts; its
   `ddram.sv` ROM-staging path is the first user of the HBM bridge.
3. **PSX and N64** wait on the HBM bridge and the DDRAM emulation, because
   both put the console's own RAM behind `DDRAM_*` (N64 by necessity).
4. In parallel, the three shared pieces above, on the SNES.
