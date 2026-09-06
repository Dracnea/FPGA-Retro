# Are the bitstreams and flows compatible with the game-running GUI? An audit, and what was changed

Written 2026-09-06. The GUI in question is **Main_MiSTeX** (the MiSTeX port of
`Main_MiSTer`: menu, OSD, ROM/disk loading, controllers, ini handling). It is
what a user sees when "running a game"; the cores only supply the machine.

## Verdict before this work: not compatible, on both sides

| side | what the GUI needs | what existed | compatible? |
|---|---|---|---|
| Gateware | an `hps_io.sv` inside the core, fed by an HPS-side master over the 49-bit `HPS_BUS` (16-bit word in, one-clock strobe, three enable levels, 16-bit word back) | `c1100_pcie_video_transport.bit`: PCIe endpoint + synthetic frame source, no core, no `hps_io`, no master. `c1100_ps2_iop.bit`: the same endpoint + the PS2 IOP, no `hps_io`. The out-of-context core fits (`build/fit_*`) contain `hps_io` but have no board target at all | **no** — nothing on the card could answer a single `UIO_*` command |
| Host software | a transport to that master | `Main_MiSTeX` reaches the FPGA only through `/dev/spidev1.0` plus libgpiod lines (`fpga_io.cpp`), and its makefiles are ARM/aarch64/riscv cross-builds against a buildroot SDK; `shmem_*` is a printed-`TODO` stub; `fpga_load_rbf` programs a Pi-attached FPGA | **no** — it neither builds on this host nor has any way to reach a PCIe device |
| Video | the OSD is drawn inside the FPGA (`osd.v`) over the core's picture and leaves the board on HDMI | these cards have no video output; the plan is a framebuffer DMA'd to host RAM and shown by a host viewer | **no** — the DMA exists (transport doc), the framebuffer and the viewer do not |

So the honest answer to "are the current bits compatible with the GUI" was
no on every axis, and the PS2 IOP bitstream, built earlier today, is no
different in that respect: it is a bring-up target driven by its own tool,
not a MiSTer core.

## What was changed

### 1. Gateware: `hps_pcie`, the HPS master as CSRs — built and simulated

`overlay/rtl/hps_pcie/hps_pcie.py` reproduces what MiSTeX's
`sys/hps_interface.v` does with an SPI slave, from five CSRs on the LitePCIe
BAR (`hps_control`, `hps_din`, `hps_din2`, `hps_dout`, `hps_status`; the
contract is in the file and in `host/main_mistex_pcie/README.md`). One
`hps_din` write is one SPI word: the core's current `io_dout` is captured, the
word is presented on `io_din`, `io_strobe` pulses once. The CSRs live in the
SoC's sys domain and the core side in the core's `clk_sys` domain, with a
toggle handshake and MultiRegs between them, so any core clock works.
`hps_io_wrap.sv` assembles the 49-bit bus the way `sys_top.v` does and
derives `io_fpga` / `io_uio` from the three enables the same way.

**Verified in xsim** (`overlay/rtl/hps_pcie/sim/run_sim.sh`), driving the
bridge exactly as `fpga_io_pcie.cpp` does into the unmodified `hps_io.sv`
from `cores/Template/sys` with a 44-byte config string, 125 MHz host side
and 50 MHz core side:

```
ok   conf string 'HPSTEST;;O1,Foo,No,Yes;O2,Bar,Off,On;V,v1.0;'   (UIO_GET_STRING, read as user_io_read_confstr does)
ok   GET_STATUS 0xA nibble = 0000000a                          (UIO_GET_STATUS)
ok   0x2B capability word = 00000007                           (UIO_SET_FLTNUM first word)
ok   joystick_0 via din = 56781234                             (UIO_JOYSTICK0, two words)
ok   joystick_0 via din2 = beefcafe                            (the same through one 32-bit write)
ok   buttons via cfg = 00000003                                (UIO_BUT_SW)
ok   fpga_enable / osd_enable levels, core_reset released, io_wide
PASS
```

Two details the bench had to learn from Main itself, and which the backend
honours: the answer to a command arrives with the *next* word (Main sends
"one null word until the result shows up" before reading the string), and
the `UIO_GET_STATUS` reply is an 8-bit `{4'hA, stflg}`. `hps_io.sv` also
declares several signals after using them, which Vivado accepts and xsim
does not; the bench simulates a rearranged copy (`sim/hoist.py`) and the
synthesised file is the original.

### 2. Gateware: `c1100_hps_test`, a bitstream Main can talk to

`overlay/mistex_boards/c1100_hps_test.py`: the proven PCIe endpoint, the
bridge, and a real `hps_io.sv` with the config string
`HPSTEST;;O1,Option one,Off,On;O2,Option two,No,Yes;V,v1.0 C1100 hps_pcie;`
in a 50 MHz core domain. What `hps_io` decodes — joystick words, OSD status
bits, buttons, file-upload strobes — is readable back through CSRs, so the
whole Main → PCIe → bridge → `hps_io` path can be checked from the host
without a core, a memory or a picture.

Built 2026-09-06, Vivado 2026.1, xcu55n-fsvh2892-2LV-e:

```
WNS +0.731   TNS 0.000   WHS +0.011   THS 0.000
28,504 endpoints, 0 failing
All user specified timing constraints are met.
```

| resource | used | util |
|---|---:|---:|
| CLB LUTs | 4,797 | 0.55 % |
| CLB registers | 9,543 | 0.55 % |
| Block RAM tiles | 23 | 1.71 % |

`bitstreams/c1100_hps_test.bit`, md5 `23a727f5aa4172cbcd58a3c20dfee886`, with
its `csr.csv`. The bridge and `hps_io` together add about 220 LUTs to the
bare transport (4,579). The sys ↔ core clock groups were declared by MMCM pin
in the pre-placement commands and the log carries no `No clocks matched`;
the only `12-4739` lines are the two from Xilinx's PCIe IP that every build
of this endpoint reports.

### 3. Host software: Main_MiSTeX on x86-64 over PCIe — builds, not yet run against a card

`host/main_mistex_pcie/` (its README has the detail): a `fpga_io_pcie.cpp`
backend implementing the whole `fpga_io.h` API on the CSR contract through
the litepcie register ioctl, selected by `-DPCIE_HOST`; a native
`Makefile.x86_64`; stand-ins for Imlib2 and libbluetooth because the dev
packages are not installed here; a two-file patch to upstream. Applied to
`Main_MiSTeX f8705a5` it produces a 1.2 MB x86-64 binary that starts, parses
`csr.csv`, and reports a missing device the way Main reports a missing FPGA.
Main_MiSTeX is MiSTeX-devel's repository, so the port lives here as files
plus a patch and nothing is pushed there.

Still stubbed there, and why it does not block the transport test:
`fpga_load_rbf` (the card is programmed over JTAG or by the user, so
choosing a core in the menu does not change the bitstream), `shmem_*` (no
framebuffer yet), Imlib2 (wallpaper and screenshots only).

## What is still missing before a game runs

In the order they block:

1. **Load `c1100_hps_test.bit` and run Main against it.** Waits for the
   card, which is busy with other work. Expected: Main prints
   `got: 'HPSTEST;;O1,...'` from `user_io_read_confstr`, the menu logic runs,
   and `hpstest_status_lo` on the card changes when an option is toggled.
2. **The video sink and a host viewer.** `VGA_*` → framebuffer → the
   existing DMA → a host window (SDL or similar). The OSD is in that picture,
   so the menu becomes visible only here. `retro-cores.md` item 2 and the
   README's "GPU → HDMI/DP" row.
3. **The memory bridge.** Per-core `sdram.sv` replacement on URAM/HBM and
   the `DDRAM_*` → HBM bridge. `retro-cores.md` item 1.
4. **A board target that instantiates `sys_top.v`** with the bridge in place
   of `hps_interface`, the sink in place of HDMI, and the memory bridge, so
   any of the fitted cores (GB/GBC, SNES, GBA, PSX, N64) becomes a bitstream.
   `xilinx_c1100_mistex.py`'s `build()` still raises `NotImplementedError`
   listing exactly these.
5. **`shmem_*` over DMA** in Main, and `fpga_load_rbf` over JTAG or the
   litepcie ICAP ioctl if switching cores from the menu is wanted.

The PS2 IOP work is unaffected by any of this: when the PS2 core exists it
will sit behind the same `hps_io` and the same bridge as every other core,
and its SIO2 pads and CDVD image will arrive through the same `UIO_*` and
file-upload commands.
