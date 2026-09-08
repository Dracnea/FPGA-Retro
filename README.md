# FPGA-Retro

MiSTer FPGA / MiSTeX on AMD (Xilinx) UltraScale+ accelerator cards.

MiSTeX ports the MiSTer ecosystem to boards other than the DE10-Nano. This repo
carries that work onto **UltraScale+ PCIe accelerator cards** — the Xilinx
Varium C1100 (Alveo U55N, `xcu55n`) and the SQRL Forest Kitten 33 (`xcvu33p`) —
which are a genuinely different kind of target: enormous fabric, no video
outputs, no HPS, and a host connection that is PCIe rather than SPI.

**Own a C1100 and want to run this?** Start with
[docs/user-guide.md](docs/user-guide.md): what works today, what does not,
and the exact steps.

## Why these cards need a different architecture

MiSTer's ARM HPS shares DDR3 with the FPGA fabric, so `Main_MiSTer`'s
`shmem_map()` / `shmem_get()` genuinely map fabric memory — that is how its
screenshot and scaler paths read frames back.

MiSTeX replaced the HPS with a Raspberry Pi Zero on SPI + GPIO. **SPI cannot map
memory**, so `Main_MiSTeX/shmem.cpp` is a stub: all four of `shmem_map`,
`shmem_unmap`, `shmem_put` and `shmem_get` print `TODO: not implemented` and
return nothing, with ~20 call sites depending on them. MiSTeX has no frame
read-back path at all; video leaves the FPGA's own HDMI pins and the host never
sees a pixel.

These cards have no HDMI pins to leave from. So the target here is:

```
Retro core -> FPGA framebuffer -> PCIe DMA -> host RAM -> host software -> GPU -> HDMI/DP
```

A BAR plus DMA is real shared access to fabric memory over a much faster link
than MiSTer's. **This design is architecturally closer to original MiSTer than
MiSTeX is**, and the software port reduces to implementing those four `shmem`
functions over PCIe plus retargeting the SPI transport.

## Status

| stage | status |
|---|---|
| Retro cores | 17 systems fitted on both dies (GB/GBC, SNES, GBA, PSX, N64; Saturn, Mega Drive, PC Engine, SMS, Neo Geo, Lynx, WonderSwan, Atari 7800/2600, C64, Amstrad, Amiga) — [docs/retro-cores.md](docs/retro-cores.md), [docs/retro-cores-second-pass.md](docs/retro-cores-second-pass.md); the first playable one waits on `sys_top` + memory bridge |
| FPGA framebuffer | **`rtl/video_sink` streams a core's VGA output as FRM1 frames into the DMA; verified on the card at 60 fps with zero drops** — [docs/host-video-path.md](docs/host-video-path.md) |
| **PCIe → host RAM** | **verified on hardware: registers, DMA, MSI** (after finding the host's unrouted 32-bit window) — see [docs/c1100-pcie-transport.md](docs/c1100-pcie-transport.md) |
| PS2 | **a real 4 MB BIOS boots on the C1100's IOP: it loads 21 of the IOP kernel's 29 modules and then waits for an Emotion Engine that is not there** — [docs/ps2-bios-boot.md](docs/ps2-bios-boot.md); the subsystem itself is [docs/ps2-iop-bringup.md](docs/ps2-iop-bringup.md), and the rest of the console is the long road in [docs/ps2-hardware-study.md](docs/ps2-hardware-study.md) |
| Host software | **`hps_pcie` bridge built and simulated against `hps_io.sv`; `Main_MiSTeX` builds natively on x86-64 with a PCIe backend** (`host/main_mistex_pcie`); `shmem_*` still stubbed — see [docs/host-gui-compatibility.md](docs/host-gui-compatibility.md) |
| GPU → HDMI/DP | **`host/viewer` (`retroview`, pygame) shows and records the stream on the host GPU**; verified against the card |

The headline number from the PCIe build: the endpoint, DMA engine,
scatter-gather and frame source together cost **0.53% of the device's LUTs and
0 DSPs**. Effectively the entire C1100 remains free for retro cores, with ~28 MB
of on-chip memory (640 URAM + 1,344 BRAM) untouched.

## Layout

```
overlay/            drop-in overlay for a MiSTeX-ports checkout; paths mirror it exactly
  platforms/        LiteX platform definitions (pinout, I/O standards, CRG constraints)
  mistex_boards/    board targets and the standalone PCIe transport build
  cores/NES/rtl/    UltraScale+ PLL shim, selected by MiSTeX.yaml, no core edits
  rtl/hps_pcie/     the HPS side of hps_io as PCIe registers, with its xsim bench
  rtl/video_sink/   core VGA output -> FRM1 stream for the PCIe DMA, with its xsim bench
  cores/PS2/        the PS2 I/O processor subsystem (simulated, fitted, C1100 bitstream)
docs/               architecture and verified build results
host/               Main_MiSTeX x86-64 port (files + patch against MiSTeX-devel's repo); retroview, the frame viewer
tools/              install-overlay.sh, jtag-load.sh, pcie-bringup.sh, pcie-diag.sh, video-capture.sh, ps2iop/ (IOP bring-up over PCIe)
```

`overlay/` is not standalone — these files must sit inside a checkout of
[MiSTeX-ports](https://github.com/MiSTeX-devel/MiSTeX-ports) to build:

```sh
tools/install-overlay.sh /path/to/MiSTeX-ports
```

## Hardware notes that will cost you a card if you miss them

- **C1100 `hbm_cattrip` (BE45) must be driven low** by any design that does not
  instantiate the HBM IP. If it floats, the satellite controller reads a
  catastrophic over-temperature event and powers the card off. This is the trap
  that silently kills a C1100 bring-up; `platforms/xilinx_c1100.py` exposes it
  as a required resource and the board files drive it low unconditionally.
- **The C1100 reference clock is 100 MHz. The FK33's is 200 MHz.** Constraint
  files in the wild often name the C1100 clock `clk200` while giving it
  `-period 10.000`. Do not copy CRG constants between the two boards.
- Both are passively cooled datacenter cards expecting forced airflow they will
  not get in a desktop chassis.

## Licence

Files carry `SPDX-License-Identifier: BSD-2-Clause`, matching LiteX and
MiSTeX-ports upstream.
