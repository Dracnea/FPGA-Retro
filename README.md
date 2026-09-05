# FPGA-Retro

MiSTer FPGA / MiSTeX on AMD (Xilinx) UltraScale+ accelerator cards.

MiSTeX ports the MiSTer ecosystem to boards other than the DE10-Nano. This repo
carries that work onto **UltraScale+ PCIe accelerator cards** — the Xilinx
Varium C1100 (Alveo U55N, `xcu55n`) and the SQRL Forest Kitten 33 (`xcvu33p`) —
which are a genuinely different kind of target: enormous fabric, no video
outputs, no HPS, and a host connection that is PCIe rather than SPI.

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
| Retro core (NES) | blocked on the video sink below; MMCME4 PLL shim done |
| FPGA framebuffer | synthetic test pattern standing in, DMA-verifiable word-for-word |
| **PCIe → host RAM** | **built, timing-clean, loaded on hardware** — see [docs/c1100-pcie-transport.md](docs/c1100-pcie-transport.md) |
| Host software | `Main_MiSTeX` exists; needs `shmem_*` over PCIe + SPI transport retargeted |
| GPU → HDMI/DP | host-side, not started |

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
docs/               architecture and verified build results
tools/              install-overlay.sh
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
