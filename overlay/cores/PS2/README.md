# PS2 — I/O processor subsystem, stage 1a

The first buildable piece of a PlayStation 2 on these cards, in the order
[docs/ps2-hardware-study.md](../../../docs/ps2-hardware-study.md) §7 lays out:
the IOP first, because it is the one block for which RTL already exists. The
PS2's I/O processor is the PS1's CPU (an R3000A at 36.864 MHz) with a
different address map, 2 MB of RAM, a 4 MB ROM, 32 interrupt sources and
three more timers. All of that is here; everything else on the IOP bus is a
register stub.

Results and the bring-up procedure are in
[docs/ps2-iop-bringup.md](../../../docs/ps2-iop-bringup.md). Nothing in this
directory has run on hardware yet.

## What is in `rtl/iop`

| file | what | origin |
|---|---|---|
| `iop_top.vhd` | the subsystem: CPU, memory mux, RAM/ROM, SSBUS config, INTC, timers 0-5, POST register, stubs; reset sequencing | new |
| `iop_memorymux.vhd` | the IOP address map on the PSX memory mux's state machine; only the decode changed, `diff` against `PSX/upstream/rtl/memorymux.vhd` shows exactly what | PSX_MiSTer, modified |
| `iop_ram.vhd` | 2 MB RAM + 4 MB ROM as 128-bit-row UltraRAM behind the PSX SDRAM-controller protocol, with the instruction-cache line fill | new |
| `iop_intc.vhd` | I_STAT / I_MASK / I_CTRL, 32 sources, PS2SDK bit numbering | new |
| `iop_timer32.vhd` | timers 3-5 (32-bit) at 0x1F801480, modelled on the PSX `timer.vhd` | new |
| `iop_regstub.vhd` | a read-back register file standing in for a peripheral that does not exist yet | new |
| (unmodified) `cpu.vhd`, `memctrl.vhd`, `timer.vhd`, `datacache.vhd`, `divider.vhd`, the RAM/FIFO wrappers | PSX_MiSTer, GPL-2.0, Robert Peip | via `cores/PSX/upstream` |

**Stubs** (programmed and read back, no behaviour): DMA (0x1F801080 and
0x1F801500), SSBUS config 2 (0x1F801400), SIF (0x1D000000), CDVD
(0x1F402000), SIO2 (0x1F808200), SPU2 (0x1F900000). Not present at all: SPU
(the PS1 one), pads/SIO, GPU, MDEC, CD-ROM; reads there return zero.

Address map differences from the PSX that are implemented: 4 MB BIOS window
at 0x1FC00000; the expansion-1 window narrowed to 0x1F000000-0x1F3FFFFF so
CDVD at 0x1F402000 reaches the internal bus; the seven new 32-bit internal
buses above. RAM is 2 MB and mirrors above that.

## Simulation

```
cd sim && ./run_sim.sh            # assemble boot_test.s, build in xsim, run, grep PASS
```

`boot_test.s` runs from the reset vector and reports through the POST register
at 0x1F802070: 01 alive, 02 RAM word test, 03 byte/halfword access, 04 code
copied to RAM and run cached, 05 timer 3 polled, 06 timer 3 interrupt through
the BEV vector (the handler writes 5A), AA all passed, EE a check failed. It
is assembled by `asm_r3000.py`, a two-pass MIPS I assembler with no
dependencies, so the test needs no cross toolchain.

`./run_sim.sh --debug` runs `tb_iop_dbg.sv` instead, which prints every CPU,
RAM and peripheral-bus transaction and takes plusargs through `XSIM_ARGS`:
`cycles=N`, `quiet=1` (hide instruction fetches), `regs=1 rfrom=A rto=B`
(register-file trace), `rf=1` (the register-file model's own view), `pfrom=A
pto=B` (every non-sequential PC change with SR/CAUSE/EPC). Each of the four
bugs below was found with one of those.

## Fit and build

```
cd fit && ./run_fit.sh [MiSTeX-ports dir] [part]      # out-of-context synthesis, build/fit_iop_<part>/
```

The C1100 bitstream target is `overlay/mistex_boards/c1100_ps2_iop.py` (the
PCIe endpoint from `c1100_pcie_video.py` with the IOP on CSRs) and the host
tool is `tools/ps2iop/iop_post.py`.

## What simulation found (2026-09-06)

Each of these produced a hang with POST stuck, and each is now either fixed in
the RTL or recorded in the file it belongs to:

1. **The CPU came up at PC 0.** PSX_MiSTer's CPU takes its reset state (PC,
   PRID, a zeroed register file) from its savestate-load port, driven in
   `psx_top` by the savestate block. `iop_top` now pulses `SS_reset` on the
   first reset cycle and holds its internal reset 64 cycles longer than the
   external one so the 32-cycle register-file load finishes first.
2. **Cache-line fills raced the CPU.** Delivering the four words of a line at
   one per clk1x cycle with `ram_done` on the second word (the SDRAM
   controller's nominal timing) makes the CPU miss and refetch the later
   words; the real controller streams them at clk3x. `iop_ram` now raises
   `ram_done` with the last word.
3. **The register file read X for every register.** Not an IOP bug:
   `rtl/altera_compat/altdpram.v` and `altsyncram.v` sized their arrays from a
   `numwords` parameter that Intel's VHDL component declaration defaults to 0
   (meaning "2**widthad"), and that 0 overrides the Verilog default when the
   model is bound from VHDL. Every write was dropped. Fixed in the models;
   this affected any core simulated through them, and synthesis was
   unaffected (identical utilisation before and after).
4. **Peripheral read data was OR'ed together.** The PSX memory mux ORs every
   bus's read data, so a block must return zero except in the cycle after its
   read strobe. `iop_intc` and `iop_regstub` drove theirs combinationally and
   corrupted memctrl reads with pending timer-IRQ flags; both now register
   like the PSX `irq.vhd`. The timers also pulsed their IRQ lines once after
   reset (mode bit 10 reset to 0); it now resets to 1.
5. **The test itself cleared BEV.** Writing SR = IM2 | IEc sent the interrupt
   to 0x80000080 in RAM, which executed zeros up to the copied test routine
   and "returned" into stage 4 forever. The ROM now keeps BEV set.

## Next

In the order the hardware study gives: SIO2 (pads, memory cards) and the
PS1 SPU as two instances toward an SPU2, both existing PSX RTL; a host-fed
CDVD; then the Graphics Synthesizer as a standalone unit fed over PCIe, which
is the first block with no RTL to start from.
