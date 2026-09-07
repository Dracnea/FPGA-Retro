# PS2 IOP bring-up: simulation, fit and the C1100 bitstream

The first step of the order [ps2-hardware-study.md](ps2-hardware-study.md) §7
gives — the I/O processor subsystem, built from PSX_MiSTer's R3000A — taken
through xsim, out-of-context synthesis on both dies, and a C1100 bitstream.
What the block contains and what simulation found is in
[overlay/cores/PS2/README.md](../overlay/cores/PS2/README.md). This page holds
the measurements.

Everything under "measured" was produced on 2026-09-06 with Vivado/xsim
2026.1. The bitstream was loaded on the C1100 on 2026-09-07 (last section);
the POST run on hardware is the next step.

## Simulation — verified

`overlay/cores/PS2/sim/run_sim.sh`, the boot ROM `boot_test.s` on `iop_top`
at 36.864 MHz with the PSX core's phase-aligned 2x/3x clocks:

```
[111339000] reset released
[122298000] POST 01        alive
[3712451000] POST 02       RAM word test (256 words, uncached)
[3757697000] POST 03       byte / halfword access, both endian orders of lb/lbu/lh/lhu/sb/sh
[3841598000] POST 04       routine copied to RAM, executed cached (KSEG0), result checked
[3858307000] POST 05       timer 3 polled to target with reset-on-target
[3977689000] POST 5a       timer 3 interrupt taken through the BEV vector, acknowledged in I_STAT
[3993368000] POST 06
[3995239000] POST aa
PASS
```

That is 143,000 IOP cycles, 3.9 ms of console time, in about 3 minutes of
xsim. Instruction fetch from the ROM is uncached and costs ~33 cycles per
instruction (the PSX memctrl's BIOS delay is honoured), which is why the RAM
test dominates.

Five bugs stood between "compiles" and this output; they are listed in the
core README. The one with reach beyond the PS2 is the third: the Altera
compatibility models sized their arrays from a `numwords` parameter that the
Intel VHDL component declaration defaults to 0, so **any core simulated
through `rtl/altera_compat` had a register file that dropped every write.**
Synthesis was never affected (utilisation is identical before and after the
fix), which is why none of the fits caught it.

## Out-of-context fit — measured

`overlay/cores/PS2/fit/run_fit.sh`, `synth_design -mode out_of_context` on
`iop_top`, clocks 27.126 / 13.563 / 9.042 ns:

| | xcu55n (C1100) | xcvu33p (FK33) |
|---|---:|---:|
| CLB LUTs | 12,546 (1.44 %) | 12,635 (2.87 %) |
| CLB registers | 25,454 (1.46 %) | 25,683 (2.92 %) |
| Block RAM tiles | 20.5 (1.53 %) | 20.5 (3.05 %) |
| **URAM** | **192 of 640 (30 %)** | **192 of 320 (60 %)** |
| DSP | 8 | 8 |
| clk1x WNS | +20.957 ns | +20.657 ns |
| clk2x / clk3x | pulse-width only, met | met |
| inert-constraint signatures in log | 0 | 0 |

The URAM is the 2 MB RAM (64) and the 4 MB ROM (128) as 128-bit rows. A first
version organised them as 32-bit words and cost 384 URAM on the same die: a
URAM is 4096 x 72, and a 32-bit-wide array wastes 40 bits of every row. The
ROM is the PS2's real BIOS size; for a bring-up image it could be a fraction
of that (both depths are generics on `iop_ram`), and on the FK33 it will have
to be.

The first fit also reported WNS -4.279 on 32 paths, all clk2x → clk1x with a
**0.001 ns requirement**: the clock periods were 27.127 / 13.563, whose edges
land 1 ps apart at the end of the cycle. Periods that are exact multiples
(27.126 / 13.563 / 9.042) remove every failing path. Nothing in the design
changed.

## C1100 bitstream — built, not loaded

`overlay/mistex_boards/c1100_ps2_iop.py`: the PCIe gen3 x4 endpoint from
`c1100_pcie_video.py` unchanged, plus a second MMCM for the IOP clocks and
`iop_top` on CSRs (`iop_reset`, `iop_rom_addr`, `iop_rom_data`, `iop_status`,
`iop_post_count`, `iop_rom_count`). The IOP clocks are 36.875 / 73.75 /
110.625 MHz — 100 MHz / 2 x 22.125, then / 30, 15, 10 — 0.03 % above the
console's 36.864 MHz, which integer MMCM ratios cannot reach from 100 MHz
(11/30 gives 36.667, 0.5 % low).

Measured, Vivado 2026.1, xcu55n-fsvh2892-2LV-e:

```
WNS +0.449   TNS 0.000   WHS +0.010   THS 0.000
126,287 endpoints, 0 failing
All user specified timing constraints are met.
```

| clock | WNS (ns) |
|---|---:|
| clk100_p (reference) | +8.657 |
| sys (125 MHz) | +1.432 |
| IOP clk1x (36.875 MHz) | +1.557 |
| IOP clk2x / clk3x | pulse-width only, met |

| resource | used | of | util |
|---|---:|---:|---:|
| CLB LUTs | 17,035 | 871,680 | 1.95 % |
| CLB registers | 34,534 | 1,743,360 | 1.98 % |
| Block RAM tiles | 45 | 1,344 | 3.35 % |
| URAM | 192 | 640 | 30.0 % |
| DSP | 8 | 5,952 | 0.13 % |

`bitstreams/c1100_ps2_iop.bit`, 56,660,149 bytes, md5
`6fab44411aa52d957b86e0790d04cb40`, with its `csr.csv` beside it. The PCIe
transport alone was 4,579 LUTs; the IOP adds the 12.5k of the fit.

Three builds were needed, and none of the failures was in the IOP:

1. LiteX passes pre-synthesis and pre-placement Tcl through `str.format`,
   so Tcl braces in those strings must be doubled.
2. The sys clock is named `clkout` in `c1100_pcie_video.py`'s design and the
   transport doc's constraint refers to it by that name. With the 100 MHz
   reference buffered once for two MMCMs, the net is `crg_clkout` and the
   by-name `set_clock_groups` matched nothing: `No clocks matched 'clkout'`,
   the third time that log line has cost a build in this repo. The
   constraint now names clocks by MMCM output pin, which cannot go stale.
   The routed result confirms it took: every sys ↔ IOP crossing is in a
   `MultiReg` or `PulseSynchronizer` and the inter-clock paths are gone
   from the timing report.
3. bitgen's DRC AVAL-168 rejected `CLKFBOUT_MULT_F = 11.0625` because the
   generated Verilog prints it as `11.062`, which is off the 0.125 grid.
   `DIVCLK_DIVIDE = 2, CLKFBOUT_MULT_F = 22.125` is the same 1106.25 MHz VCO
   with a value that survives three-decimal formatting. Placement and
   routing had already met timing; only the bitstream write failed.

## Loading it — the procedure, not yet run

```sh
# program over JTAG, then restore the PCIe identity (docs/c1100-pcie-transport.md)
sudo sh -c 'echo 1 > /sys/bus/pci/devices/0000:c1:00.0/remove; sleep 1; echo 1 > /sys/bus/pci/rescan'
lspci -nn -d 10ee:                       # expect 10ee:9034, BAR0 128K, driver litepcie

cd overlay/cores/PS2/sim && python3 asm_r3000.py boot_test.s boot_test.hex --size 4096
tools/ps2iop/iop_post.py --csr bitstreams/c1100_ps2_iop.csr.csv status   # locked=1, heartbeat toggling between calls
tools/ps2iop/iop_post.py --csr bitstreams/c1100_ps2_iop.csr.csv run overlay/cores/PS2/sim/boot_test.hex
```

`run` holds reset, streams the image through `iop_rom_data` (one ioctl per
word; 4096 words is well under a second), releases reset and prints each POST
transition until AA, EE or the timeout. The expected output is the sequence
in the simulation section with wall-clock stamps instead of picoseconds.

What would make the first attempt fail, in the order to check: `locked` = 0
(the fractional feedback multiplier — fall back to DIVCLK 1 / MULT 11.0); `heartbeat` not
toggling (the IOP clock domain is not running); `post_count` staying 0 with
`cpu_error` = 0 (the ROM did not load: check `rom_count` matches the image
length); POST EE (a stage failed on silicon that passed in xsim — the
`boot_test.s` header says which stage precedes it).

## What this does and does not establish

Established: the PS1 CPU core, its memory mux and the PSX peripherals reused
here run correctly on this fabric at the IOP's clock through a real boot
sequence, with the RAM and ROM on chip; the IOP-specific additions (INTC,
32-bit timers, address map) behave as documented for the parts the test
exercises; the whole thing costs 1.4 % of the C1100's logic and 30 % of its
URAM with the full-size ROM.

Not established: anything about the EE, VUs or GS, which remain the
"nothing to port" of the retro-cores verdict; SPU2, SIO2, CDVD, SIF and DMA
behaviour, all of which are stubs; the IOP kernel booting (that needs the
DMA controller and SIF at minimum, and the real BIOS, which is not
redistributable). The verdict in [retro-cores.md](retro-cores.md) stands; this
is the first block of the long road it describes.

## Second pass, 2026-09-06: SPU2, SIO2, CDVD — simulated and fitted

The next three blocks of §7 step 1, on top of the stage above, simulation
and fit only (the C1100 stayed on its other work). What each is and is not
is in the file headers and in [overlay/cores/PS2/README.md](../overlay/cores/PS2/README.md).

- **SPU2** as two instances of PSX_MiSTer's SPU (`iop_spu2.vhd`) at
  0x1F900000 / 0x1F900400, each with 512 KB of work RAM in URAM
  (`iop_spuram.vhd`) behind `spu_ram`'s SDRAM-style port. The register
  layout is the PS1's, not the SPU2's, and there is no DMA: the cores, RAM,
  transfer FIFO and IRQ plumbing are real, the SPU2 decode in front of them
  is the next job.
- **SIO2** (`iop_sio2.vhd`): command queue, FIFOs, CTRL, RECV1-3, I_STAT,
  INTC bit 17, with a PS1-protocol digital pad on port 0 fed from a
  `pad0_buttons` port on `iop_top`. Semantics from PCSX2's Sio2 (ps2tek
  lists only the addresses); unverified against hardware.
- **CDVD** (`iop_cdvd.vhd`): the N/S command ports, status, error, I_STAT,
  INTC bit 2; the boot-time S commands answered with PCSX2's values; no
  disc, no sector path. Unverified against a drive.

Simulation — verified (`run_sim.sh`, 2026-09-06):

```
[122298000]  POST 01 .. [3993368000] POST 06     as before
[4022203000] POST 07   SPU2 voice registers written/read on both cores (sh/lhu)
[5133148000] POST 08   SPU2 transfer FIFO -> work RAM 0x2000 (row checked by the bench: 4444 3333 2222 1111)
[5201017000] POST 09   SIO2 pad poll: FF 41 5A 3C 5A, RECV1 0x1100, I_STAT, INTC bit 17
[5265062000] POST 0a   CDVD: no disc, N ready 0x4A, S 03/00 -> 03 06 02 00, N 00 -> I_STAT, INTC bit 2
[5266933000] POST aa   PASS
```

190,000 IOP cycles, 5.2 ms of console time. Three more findings on the way,
recorded as items 6-8 of the core README: stores reach the internal buses
word-aligned with the lanes in the write mask (the mux now exports that
mask), peripheral read data is sampled exactly one cycle after the strobe,
and xsim returns junk for a VHDL array element read from a SystemVerilog
bench (the RAM now mirrors the checked row into a scalar for the bench).

Out-of-context fit — measured, clocks 27.126 / 13.563 / 9.042 ns:

| | xcu55n (C1100) | xcvu33p (FK33) |
|---|---:|---:|
| CLB LUTs | 16,349 (1.88 %) | 16,349 (3.72 %) |
| CLB registers | 13,306 (0.76 %) | 13,306 (1.51 %) |
| Block RAM tiles | 57.5 (4.28 %) | 57.5 (8.56 %) |
| **URAM** | **224 of 640 (35 %)** | **224 of 320 (70 %)** |
| DSP | 34 | 34 |
| clk1x WNS | +20.734 ns | +20.726 ns |
| inert-constraint signatures in log | 0 | 0 |

Of that, the SPU2 is 8,311 LUTs, 5,660 registers, 32 BRAM tiles and 32
URAM (the two 512 KB work RAMs), SIO2 375 LUTs and CDVD 58. The register
count *fell* from the first pass's 25,454: the SPU2 stub it replaces was a
512-entry, 32-bit read-back register file, 16k flip-flops of nothing. The
FK33 now has 70 % of its URAM in this one subsystem; the 4 MB ROM (128 of
the 224) is the lever there.

Not done, and needed before the C1100 image is rebuilt with this: the
board target `c1100_ps2_iop.py` does not yet connect `iop_top`'s new
`pad0_buttons` input (a CSR) and `spu_l0/r0/l1/r1` outputs; the bitstream in
`bitstreams/` is the first-pass IOP.

### Bitstream rebuilt with the second pass (2026-09-06, later)

`c1100_ps2_iop.py` gained an `iop_pad0` CSR (SIO2 port 0 buttons, active
low, PS1 bit order) and the four SPU2 audio outputs, unconnected until there
is an audio sink. Rebuilt with SPU2, SIO2 and CDVD in:

```
WNS +0.168   TNS 0.000   WHS +0.010   THS 0.000
98,932 endpoints, 0 failing
All user specified timing constraints are met.
```

| resource | used | util |
|---|---:|---:|
| CLB LUTs | 20,791 | 2.39 % |
| CLB registers | 22,145 | 1.27 % |
| Block RAM tiles | 82 | 6.10 % |
| URAM | 224 | 35.0 % |

`bitstreams/c1100_ps2_iop.bit`, md5 `9164ab8c3f872f460f6694d0dd60f8ec`, with
its `csr.csv`. The first-pass image (md5 `6fab4441…`) is superseded.

**Rebuilt 2026-09-07 21:10 with BAR0 64-bit prefetchable** (the fix for the
all-ones reads, [c1100-pcie-transport.md](c1100-pcie-transport.md)): md5
`3ac569521c495e99049842f3307e54ef`, WNS +0.168 ns, 0 failing endpoints, no
inert-constraint signature in the log, `iop_*` CSR addresses unchanged.
That is the image to run `hw-test.sh` against.

## Loaded on the C1100, 2026-09-07

The card came free (a power cut had reverted it to its flash image, which the
host enumerates as `10ee:5058` with no driver). The second-pass image above was
loaded over JTAG:

```
[load] c1100_ps2_iop.bit (56659936 bytes of config data)
[load] STAT=0x109079fc  DONE=1 EOS=1 CRC_ERR=0
```

Configuration is verified on silicon: DONE and EOS high, no CRC error.
`sudo tools/ps2iop/hw-test.sh` (the root part — stale `5058` identity
dropped, rescan, `litepcie.ko` — then the sequence below as the invoking
user, logged to `build/ps2_hw/`) was run the same day. **Result: no IOP
result.** Every CSR read, `iop_status` included, returned `0xffffffff`, so the
log shows POST FF, `cpu_error` 1 and counts of 4294967295 — the value of a
BAR0 read that the fabric did not answer, not anything the IOP did. The
identifier and scratch registers of the transport itself read the same, and
so does the HPS video image loaded afterwards. This is a defect in the PCIe
transport that every C1100 image shares; the analysis and the root-side
diagnostic to run next are in
[c1100-pcie-transport.md](c1100-pcie-transport.md) ("BAR0 reads return
0xFFFFFFFF"). The IOP test sequence stands and reruns unchanged once a
register read works.

Two things found while preparing the run, both now handled in
`tools/ps2iop/iop_post.py`:

- **Stage 09 needs the pad set.** `iop_pad0` resets to `0xFFFF` (nothing
  pressed) and `boot_test.s` stage 09 expects the pad to answer `0x5A3C`,
  which is what `tb_iop.sv` drives. On hardware that stage would have failed
  for no fault of the design. `run` now writes `iop_pad0` (default `0x5A3C`)
  before releasing reset, and `run --pad0 0xFFFF` is a deliberate negative
  test: stage 09 must then report EE, which proves the CSR reaches SIO2.
- **`tools/frametest` must not be run against this image.** It hard-codes the
  transport image's CSR map and `0x1000` is `iop_reset` here; the DMA integrity
  test belongs to `c1100_pcie_video_transport.bit`.

Planned sequence in `hw-test.sh`, in the order the failure modes above are
checked: status (`locked` = 1, POST 00, counts 0), heartbeat read twice 0.5 s
apart (must differ), ROM load with `rom_count` = 4096, the boot test with
pad `0x5A3C` (expect 01..0A then AA), the same with pad `0xFFFF` (expect EE at
09), five repeats of the passing run, final status.
