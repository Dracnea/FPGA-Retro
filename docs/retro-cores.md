# Retro cores on the C1100 and FK33: GB/GBC, SNES, GBA, PSX, N64 (and why not PS2 or GameCube)

What exists upstream for each console, what it needs from a board, what these
cards can give it, and what the out-of-context synthesis of each core on the
C1100's die actually measured. The FK33 has no display output either, so it
follows the C1100 flow exactly (PCIe video, PCIe host); the numbers below are
for the `xcu55n` unless a `xcvu33p` column says otherwise.

Everything under "measured" was produced by `tools/core-fit.py` on 2026-09-05
with Vivado 2026.1; everything else is read from the upstream sources named.
**Second pass (2026-09-07):** Saturn, Mega Drive, PC Engine, Master System,
Neo Geo, Lynx, WonderSwan, Atari 7800/2600, C64, Amstrad and Amiga fitted the
same way, with what each needs to load and play through the GUI —
[retro-cores-second-pass.md](retro-cores-second-pass.md).

## The three things every core needs from these cards

None of the five cores can run until three board-side pieces exist, and they
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
   **Done for the transport half (2026-09-06):** `overlay/rtl/hps_pcie` is
   that register block, simulated against the real `hps_io.sv`, and
   `host/main_mistex_pcie` is Main_MiSTeX driving it —
   [host-gui-compatibility.md](host-gui-compatibility.md). `shmem_*` waits
   for item 2.

## Per console

| | GB/GBC | SNES | GBA | PSX | N64 | PS2 | GameCube |
|---|---|---|---|---|---|---|---|
| upstream | [Gameboy_MiSTer](https://github.com/MiSTer-devel/Gameboy_MiSTer) (no MiSTeX port; cloned as `cores/Gameboy/upstream`) | [SNES_MiSTer](https://github.com/MiSTer-devel/SNES_MiSTer) (MiSTeX has a Vivado port) | [GBA_MiSTer](https://github.com/MiSTer-devel/GBA_MiSTer) | [PSX_MiSTer](https://github.com/MiSTer-devel/PSX_MiSTer) | [N64_MiSTer](https://github.com/MiSTer-devel/N64_MiSTer) | **none exists** | **none exists** |
| author lineage | Till Harbaum's MiST core → MiSTer (paulb-nl, Robert Peip's savestates/rewind) | srg320 | Robert Peip | Robert Peip | Robert Peip (dev ended; community-maintained, last commit 2026-08) | — |
| core clocks (MHz) | 67.109 (SDRAM) / 33.554 (sys) | 85.909 / 42.955 (SDRAM/sys) / 21.477 | 100.663 / 50.332 | 33.869 / 67.738 / 101.606 + 53.693 | 62.5 / 93.75 / 125 / 62.5 + 48.68 | — |
| SDRAM use | cart ROM ≤ 8 MB (MBC5), cart RAM | ROM ≤ 8 MB, WRAM, SRAM (32 MB module) | cart ROM ≤ 32 MB (64 MB carts and ≥ 32 MB on small modules go to DDR3) | main RAM / BIOS; optional second module | cart ROM (up to 64 MB) + SRAM/FLASH; second module for larger carts | — |
| DDRAM use | savestates, rewind buffer | framebuffer only | ROM staging (copied to SDRAM), savestates | VRAM (1 MB) and CD data, savestates | **RDRAM (4/8 MB) — "the SDRAM has no chance" (Peip)**, framebuffer | — |
| on-chip-only feasible? | yes on both cards (≤ 8 MB ROM + 128 KB) | yes on both cards (≤ 9 MB) | C1100 yes for ≤ 16 MB carts, FK33 marginal; 32/64 MB carts need HBM | RAM/VRAM/BIOS ~4 MB yes; CD image streams from host | RDRAM 8 MB yes; cart ROM needs HBM on FK33, marginal on C1100 | — |
| Altera cells used | altsyncram, altddio_out | altsyncram, lpm_mult/divide, scfifo, dcfifo, altddio_out | altsyncram, altddio_out | altsyncram, altdpram, altddio_out | altsyncram, altdpram, altshift_taps, altera_mult_add (64×64), altddio_out, `cyclonev_lcell_comb` in the PLL reconfig | — |

**PS2:** there is no PlayStation 2 core for MiSTer or any other FPGA platform,
and a fresh search (2026-09-05) finds none in progress anywhere: the only
PS2-related FPGA work is a video-out board for a portable built from real
PS2 silicon. The MiSTer forum's standing assessment is that none is coming.
It is worth being precise about *why*, because the question on these cards is
not the one it is on a DE10-Nano:

- *Area is plausibly there.* The PSX core is 46k LUTs. The Emotion Engine
  (a two-issue 64-bit MIPS with 128-bit multimedia SIMD), its two vector
  units, the IOP (which *is* a PSX CPU at 36.8 MHz), the SPU2 and the
  Graphics Synthesizer would land somewhere in the hundreds of thousands of
  LUTs on any honest estimate — inside the C1100's 872k, past the FK33's 440k.
- *Clock is not.* The EE and VUs run at 294.9 MHz and the GS at 147.5 MHz.
  The PSX core's 33.9 MHz CPU closes at synthesis with an fmax around
  117 MHz on this fabric; a soft R5900 with its SIMD datapath will not
  reach a third of 295 MHz, so a cycle-accurate PS2 would have to be
  multi-cycle everywhere, which is a different (and larger) design.
- *Bandwidth is the one place these cards are ahead.* The GS's 4 MB of eDRAM
  on a 2560-bit bus (~48 GB/s) and the 32 MB of RDRAM (3.2 GB/s) are within
  HBM2's reach on both cards, which is not true of any MiSTer board.

So the PS2 fails on "nothing to port" and on clock, not on fabric size. PCSX2
on the host GPU remains the honest answer; nothing here changes that.
the PS2 hardware study, now in [PS2-Xilinx-UltrascalePlus](https://github.com/Dracnea/PS2-Xilinx-UltrascalePlus), has the
board, chip and documentation survey behind this paragraph, a block-by-block
sizing scaled from the PSX fit, and the order a recreation would be built in.
The first block of that order — the IOP, which *is* PSX RTL with a new
address map — has been built: it boots a test ROM in xsim, fits both dies
(12.5k LUTs, 192 URAM) and has a C1100 bitstream target;
[PS2-Xilinx-UltrascalePlus](https://github.com/Dracnea/PS2-Xilinx-UltrascalePlus), where that work now lives. The verdict on the EE and GS is
unchanged.

**GameCube:** the same, one generation later and further out of reach. No
GameCube core exists for any FPGA (the only hits are a hobby PowerPC soft
core with no relation to the 750 and a GameCube *controller* project). The
Gekko is a 486 MHz out-of-order PowerPC 750CXe with paired-single FPU; the
Flipper GPU runs at 162 MHz with 3 MB of embedded 1T-SRAM and a fixed-function
TEV pipeline; main memory is 24 MB of 1T-SRAM at 2.6 GB/s plus 16 MB ARAM.
There is no open out-of-order PowerPC core of that class to start from
(Microwatt and A2O are in-order or far slower), the clock gap is worse than
the PS2's, and the MiSTer developers' view — a full-time job for a team — is
the right one. Dolphin on the host is the answer. Neither PS2 nor GameCube
gets a row in the measured table because there is no RTL to measure.
[gamecube-hardware-study.md](gamecube-hardware-study.md) (2026-09-07) is the
board, chip and documentation survey behind this paragraph — sources
ranked, the sizing scaled from the N64 and PSX fits, the clock problem with
numbers, and the order a recreation would be built in — as
the PS2 study, now in [PS2-Xilinx-UltrascalePlus](https://github.com/Dracnea/PS2-Xilinx-UltrascalePlus), is for the PS2.

## What it took to get the four cores through Vivado

MiSTer cores are Quartus code. Every class of thing that stopped Vivado 2026.1
was fixed in the overlay without editing an upstream file:

- **Intel megafunctions.** `overlay/rtl/altera_compat/` supplies `altsyncram`,
  `altdpram`, `lpm_mult`, `lpm_divide`, `scfifo`, `dcfifo`, `altshift_taps`,
  `altera_mult_add`, `altddio_out` and a Series-7-named `ODDR` as plain
  Verilog with the same names, parameters and ports, plus the `altera_mf` and
  `lpm` component packages for VHDL `use` clauses, so the thin wrappers the
  Peip cores share (`dpram.vhd`, `SyncRamDualByteEnable.vhd`, `RamMLAB.vhd`,
  `Shiftreg.vhd`) synthesise unmodified. One semantic gap is documented there
  (same-port read-during-write returns old data).
- **RAM that Vivado will not infer as block RAM.** Two shapes cost a day:
  a per-bit write loop in the first `altsyncram` model, and Peip's own
  `SyncRamDual.vhd` (one process writing a `signal` array from two ports).
  Both came out as registers — the GBA's four 8 KB "smallram" instances were
  65,544 flip-flops and 157k LUTs *each*, and the core reported 963k LUTs,
  110 % of the die. `altsyncram` now writes per byte-enable lane with a
  banked template for asymmetric widths, and `SyncRamDual` /
  `SyncRamDualNotPow2` are replaced by the two-process shared-variable form.
  The GBA then dropped to 37.8k LUTs. Read a fit that looks too big as a
  RAM-inference failure first.
- **Quartus-only Verilog and VHDL.** `inout reg` ports (every `sdram.sv`),
  procedural writes to ports and wires declared without `reg` (every top),
  PSX's ports arriving through `sys/emu_ports.vh`, `defparam` onto an instance
  named like its module, unpacked-array `localparam`s, `do` as a net name in
  SNES's `main.v` (so `.v` is read as Verilog-2001, not SystemVerilog),
  `default` as a record field in GBA (so GBA's VHDL is read as VHDL-93 while
  N64 needs VHDL-2008 to read its own out ports), and Quartus's habit of
  folding `entity mem.X` into `work` (the Peip cores' VHDL is compiled into a
  `mem` library). `tools/patch-top.py` fixes the declaration class from the
  errors Vivado reports and writes MiSTeX-style patched copies into the
  overlay; the rest is per-core yaml (`vhdl: 93`, `vhdl-library: mem`).
  The Game Boy adds the mirror image of the SNES case: `lcd.v` and `sgb.v`
  are SystemVerilog in `.v` files (`reg [14:0] vbuffer[65536]`, declarations
  in unnamed blocks), so the yaml lists them under `sv-as-v:`; and its
  `cheatcodes.sv` / `megaswizzle.sv` write to plain `output`s and `wire`s
  from `always_comb`, which Quartus accepts and Vivado does not (patched
  copies under `overlay/cores/Gameboy/rtl/`).
- **XPM.** MiSTeX's SNES `dpram_dif.vhd` instantiates `xpm_memory_tdpram` in
  write-first mode with `WRITE_PROTECT 0`, which Vivado 2026.1 refuses; the
  overlay copy sets it to 1.
- **PLLs and their reconfiguration.** Six MMCME4_ADV shims
  (`overlay/cores/*/rtl/pll*_0002-xilinxusp.v`) generated from each Altera
  PLL's output table; worst frequency error 0.043 % (PSX), N64's exact. PSX
  and N64 retune their PLLs at runtime through Altera's reconfig IP
  (`pll_cfg`, `pll_cfg_small`); those are static stubs here, so PAL/NTSC and
  turbo clock switching is not functional until an UltraScale+ DRP sequencer
  replaces them. N64's `cpu_mul` (a 250-generic `altera_mult_add`) is
  replaced by the 64×64 multiply it configures.

`tools/core-fit.py <MiSTeX-ports> <core> <part>` resolves the source list the
way MiSTeX does, applies the above, and synthesises `emu` out of context with
`CLK_50M` constrained at 50 MHz, so the MMCM-derived clocks are timed at the
core's real rates. `tools/patch-top.py` and `tools/fit-summary.py` go with it.

## Measured: out-of-context synthesis of `emu`

| core | part | CLB LUTs | registers | BRAM tiles | URAM | DSPs | slowest clock (post-synth) | result | black boxes |
|---|---|---|---|---|---|---|---|---|---|
| GBA | xcu55n | 37786 (4.33 %) | 30785 (1.77 %) | 111.5 (8.30 %) | 0 (0.00 %) | 58 (0.97 %) | 100.6 MHz clock: WNS +4.79 ns (fmax ≈ 194 MHz) | clean | 0 |
| GBA | xcvu33p | 37786 (8.59 %) | 30785 (3.50 %) | 111.5 (16.59 %) | 0 (0.00 %) | 58 (2.01 %) | 100.6 MHz clock: WNS +4.56 ns (fmax ≈ 186 MHz) | clean | 0 |
| Gameboy | xcu55n | 16686 (1.91 %) | 14306 (0.82 %) | 75 (5.58 %) | 0 (0.00 %) | 2 (0.03 %) | 33.6 MHz clock: WNS +9.27 ns (fmax ≈ 49 MHz) | clean | 0 |
| Gameboy | xcvu33p | 16686 (3.80 %) | 14306 (1.63 %) | 75 (11.16 %) | 0 (0.00 %) | 2 (0.07 %) | 33.6 MHz clock: WNS +8.41 ns (fmax ≈ 47 MHz) | clean | 0 |
| N64 | xcu55n | 46188 (5.30 %) | 24345 (1.40 %) | 85.5 (6.36 %) | 0 (0.00 %) | 63 (1.06 %) | 93.7 MHz clock: WNS +4.24 ns (fmax ≈ 156 MHz) | clean | 0 |
| N64 | xcvu33p | 46188 (10.50 %) | 24345 (2.77 %) | 85.5 (12.72 %) | 0 (0.00 %) | 63 (2.19 %) | 93.7 MHz clock: WNS +5.47 ns (fmax ≈ 192 MHz) | clean | 0 |
| PSX | xcu55n | 46109 (5.29 %) | 30596 (1.76 %) | 117 (8.71 %) | 0 (0.00 %) | 101 (1.70 %) | 67.7 MHz clock: WNS +6.20 ns (fmax ≈ 117 MHz) | clean | 0 |
| PSX | xcvu33p | 46109 (10.49 %) | 30596 (3.48 %) | 117 (17.41 %) | 0 (0.00 %) | 101 (3.51 %) | 67.7 MHz clock: WNS +8.34 ns (fmax ≈ 156 MHz) | clean | 0 |
| SNES | xcu55n | 13846 (1.59 %) | 10175 (0.58 %) | 20.5 (1.53 %) | 0 (0.00 %) | 23 (0.39 %) | 21.5 MHz clock: WNS +20.61 ns (fmax ≈ 39 MHz) | clean | 1 |
| SNES | xcvu33p | 13846 (3.15 %) | 10175 (1.16 %) | 20.5 (3.05 %) | 0 (0.00 %) | 23 (0.80 %) | 21.5 MHz clock: WNS +19.50 ns (fmax ≈ 37 MHz) | clean | 1 |

All five consoles synthesise clean on both dies. Percentages are of the C1100
(`xcu55n`, 871,680 LUTs) and the FK33 (`xcvu33p`, 439,680 LUTs); the FK33 rows
are the same netlists at twice the share. The table is regenerated by
`tools/fit-summary.py build`.

Read these as *fit and post-synthesis timing*, not as a bitstream: place and
route on a full board design will move WNS, and a core that closes at
synthesis with margin is the one to take forward first.

## Order of work

0. **Game Boy alongside SNES.** Smaller still (16.7k LUTs, 75 BRAM tiles,
   8 MB ROM ceiling), the same on-chip memory story, and the simplest video
   (160×144 at one pixel clock), so it is the cheapest end-to-end proof of
   the three board pieces once they exist.
1. **SNES first.** Smallest memory footprint, MiSTeX has already ported its
   RAMs, everything fits on-chip on both cards, and it is the one console
   whose SDRAM traffic (ROM reads) is trivially served from URAM.
2. **GBA second** — the same on-chip story for the common ≤ 16 MB carts; its
   `ddram.sv` ROM-staging path is the first user of the HBM bridge.
3. **PSX and N64** wait on the HBM bridge and the DDRAM emulation, because
   both put the console's own RAM behind `DDRAM_*` (N64 by necessity).
4. In parallel, the three shared pieces above, on the SNES.
