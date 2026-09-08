# Running this on your own C1100

This is the page for someone who owns a Varium C1100 (Alveo U55N) and wants to
run what is in this repository today, without the rest of the docs. It says
what the card can do right now, what it cannot, and gives the exact steps for
each thing it can. Everything here was run on real hardware on 2026-09-07;
the measurements behind each claim are in the linked pages.

## What you get today, honestly

| you can | you cannot yet |
|---|---|
| Load a bitstream over the card's USB JTAG and talk to it over PCIe from Linux | Play a game. No retro core has a board target with `sys_top` and the memory bridge yet |
| Stream video from the card to a window on your GPU at 60 fps, record it, take screenshots | See anything but the test pattern generator's colour bars |
| Run the PlayStation 2 I/O processor (R3000, RAM/ROM, timers, INTC, SPU2 stand-in, SIO2, CDVD stub) and load your own BIOS image into its ROM | Run a PS2 game. There is no Emotion Engine, no VU, no Graphics Synthesizer, no DMA controller, no SIF |
| Build every image yourself from the sources with Vivado | Use Windows. The transport driver is Linux only ([docs/host-video-path.md](host-video-path.md) says what a Windows driver needs) |

The PS2 is the honest headline: the part that exists is the small processor
that runs the controller, sound and disc I/O. It boots a test ROM on the card
exactly as it does in simulation. A game needs the rest of the console, which
is the long road described in [docs/ps2-hardware-study.md](ps2-hardware-study.md).

## What you need

- **Card:** a Varium C1100 in a PCIe slot (x4 or wider; it trains at gen3 x4),
  with its USB cable connected to the host — that is the on-board FT4232H
  that carries JTAG. Forced airflow over the heatsink: these are passively
  cooled datacenter cards and a desktop chassis gives them none.
- **Host:** x86-64 Linux. Ubuntu 24.04 is what this was done on. Kernel
  headers for your running kernel (`linux-headers-$(uname -r)`), `gcc`,
  `make`, `python3` (3.10+), `pciutils`, `usbutils`.
- **To load bitstreams:** Vivado, or the free **Vivado Lab Edition**, on PATH
  (`vivado` or `vivado_lab`). Its hardware manager drives the Alveo's USB JTAG
  directly. Nothing else is needed to use the prebuilt images.
- **To build bitstreams:** Vivado 2026.1 (what the images here were built
  with) with the UltraScale+ device family, a checkout of
  [MiSTeX-ports](https://github.com/MiSTeX-devel/MiSTeX-ports) with its
  Python venv (LiteX, LitePCIe, LiteScope), and this repo's overlay installed
  into it (`tools/install-overlay.sh /path/to/MiSTeX-ports`).
- **Your own PS2 BIOS**, dumped from your own console, if you want to load one
  into the IOP ROM. And your own disc images, when there is something to play
  them on. Neither goes in this repo, and none is downloaded from anywhere.

Add your user to `plugdev` (`sudo usermod -aG plugdev $USER`, log in again):
the udev rules below give that group the JTAG and PCIe device nodes.

## One-time host setup

```sh
git clone https://github.com/Dracnea/FPGA-Retro.git
cd FPGA-Retro

# USB JTAG (the FT4232H) usable without root
sudo tee /etc/udev/rules.d/99-ftdi-fpga.rules >/dev/null <<'RULES'
ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6011", MODE="0666", GROUP="plugdev"
RULES
# /dev/litepcie0 usable without root
sudo cp tools/99-litepcie.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger

# the host viewer (pygame; the wheel bundles SDL, no system packages needed)
cd host/viewer && python3 -m venv .venv && .venv/bin/pip install -e . && cd ../..
```

`lsusb` should list `0403:6011 Future Technology Devices International, Ltd
FT4232H`, and `lspci -d 10ee:` should list the card (as whatever identity its
flash image has; that changes once you load an image).

### The driver must match the image

The LitePCIe kernel module is generated per bitstream with that image's
register addresses compiled in. **Use the driver from the build that made the
image you loaded.** The prebuilt images in `bitstreams/` correspond to these
build directories in your MiSTeX-ports checkout, and the scripts pick the
right one from the bitstream's name:

| bitstream | build directory |
|---|---|
| `c1100_pcie_video_transport.bit` | `build/c1100_pcie` |
| `c1100_hps_video_test.bit` | `build/c1100_hps_video_test` |
| `c1100_hps_test.bit` | `build/c1100_hps_test` |
| `c1100_ps2_iop.bit` | `build/c1100_ps2_iop` |
| `c1100_pcie_diag.bit` | `build/c1100_pcie_diag` |

If you only have the prebuilt bitstreams and no MiSTeX-ports build, generate
the software for an image without Vivado: from the MiSTeX-ports checkout,
`venv/bin/python mistex_boards/<target>.py` (no `--build`) writes
`build/<target>/software/` in a few seconds; then
`make -C build/<target>/software/kernel` and
`make -C build/<target>/software/user`. Point the scripts at it with
`LITEPCIE_SW=/path/to/build/<target>/software` if it is not under
`~/MiSTeX-ports`.

## Loading an image and bringing PCIe up

```sh
tools/jtag-load.sh bitstreams/c1100_hps_video_test.bit        # ~45 s over USB JTAG (Vivado hardware manager)
sudo LITEPCIE_SW=~/MiSTeX-ports/build/c1100_hps_video_test/software tools/pcie-bringup.sh
```

The second step matters on every load. The host enumerated the card at boot
with whatever was in its flash; after a JTAG load it still holds that stale
identity, so the script removes the PCI device, rescans, loads the driver and
prints what it found. Expect `10ee:9034`, `LnkSta: Speed 8GT/s, Width x4`,
and `Region 0: Memory at 1801e000000 (64-bit, prefetchable) [size=128K]` (the
address will differ on your host). A warm reboot with the image loaded does
the same thing.

**Why the BAR is 64-bit prefetchable, and what it looks like when it is not.**
The first images had a 32-bit BAR, and on this host Linux placed it at
rescan in a 32-bit window the firmware had never routed. Every register read
returned `0xffffffff`, instantly, with no error logged anywhere, while config
space worked. If you ever see that pattern — all ones, no errors, link up —
it is the host's window, not the card: [docs/c1100-pcie-transport.md](c1100-pcie-transport.md)
has the whole investigation. Every image here now declares the BAR 64-bit
prefetchable so the kernel puts it in the window the firmware routed at boot.

Quick check that the transport is alive:

```sh
~/MiSTeX-ports/build/c1100_hps_video_test/software/user/litepcie_util info    # SoC identifier string
~/MiSTeX-ports/build/c1100_hps_video_test/software/user/litepcie_util scratch_test
```

## Video: colour bars from the card to your GPU, recorded

With `c1100_hps_video_test.bit` loaded and PCIe up:

```sh
tools/csrw.py --csr bitstreams/c1100_hps_video_test.csr.csv write video_enable 1
cd host/viewer
.venv/bin/retroview --transport litepcie --csr ../../bitstreams/c1100_hps_video_test.csr.csv
```

opens a window with five colour bars and a bright bar sweeping across at
59.5 frames per second. Keys: `F` fullscreen, `S` screenshot, `N` filter,
`I` scaling, `Esc` quit. To record instead (or as well):

```sh
.venv/bin/retroview --transport litepcie --record session.frm1 --video session.avi \
                    --shots shots/ --shot-every 60 --contact contact.png
```

gives the raw stream (replayable with `--transport file --file session.frm1`),
an MJPEG AVI any player opens, a PNG every second and a contact sheet. All of
that also works headless (`--headless --frames 600 --timeout 15`), which is
how `sudo tools/video-capture.sh` does it end to end: JTAG load, PCIe
bring-up, sink on, ten seconds captured into `build/video/<timestamp>/`.
Measured: 600 frames in 10 s, 0 dropped, 738 MB over the DMA ring
([docs/host-video-path.md](host-video-path.md)).

The DMA integrity and latency test for the bare transport is
`tools/frametest` (build it with `make -C tools/frametest SW=<build>/software`
against the transport image's software; run it with
`c1100_pcie_video_transport.bit` loaded).

## The PlayStation 2 I/O processor

With `c1100_ps2_iop.bit` loaded, `sudo tools/ps2iop/hw-test.sh` does the PCIe
bring-up and the whole test in six seconds: lock and heartbeat, the 4096-word
boot ROM loaded and counted, the boot test with the pad set (POST `01`…`0A`
then `AA`), the same with nothing pressed (must fail at stage `09`), five
repeats. The log goes to `build/ps2_hw/`. Expected end of a passing run:

```
[  0.010s] POST AA  (count 12)
PASS
```

The pieces, for driving it yourself (`tools/ps2iop/iop_post.py --csr
bitstreams/c1100_ps2_iop.csr.csv ...`): `status`, `reset hold|release`,
`load <image> [--addr WORD]`, `pad [VALUE]`, `run <image> [--timeout S]
[--pad0 VALUE]`. Images are the assembler's `.hex` (one word per line,
`overlay/cores/PS2/sim/asm_r3000.py`) or raw little-endian `.bin`. Word
address 0 is the reset vector `0xBFC00000`. The POST register the tool watches
is the IOP's real one at `0x1F802070`.

### Loading your BIOS

The ROM is the BIOS's own size, 4 MB, mapped where the console maps it. So a
BIOS dump (`.bin`, 4,194,304 bytes; the usual name is `SCPH-xxxxx.bin`) loads
as it is:

```sh
tools/ps2iop/iop_post.py --csr bitstreams/c1100_ps2_iop.csr.csv run /path/to/your/bios.bin --timeout 30
```

`run` streams the whole image through the ROM port (about a million register
writes, a few seconds), releases reset, and prints each POST value the BIOS
writes, since IOPBOOT uses that same register. That is the next experiment
this project has not yet run, and the honest expectation is that the boot
stops early: the IOP kernel needs the DMA controller and the SIF link to the
Emotion Engine, and neither exists yet. Where it stops is exactly the
information the next block needs, so please keep the log
(`build/ps2_hw/` if you run it through the script, otherwise your terminal).

A game ISO has no use on the card yet. The CDVD block answers the boot-time
status commands and has no disc path; when it gets one, the image will be
served from the host over the same PCIe link, and the guide will say how.
Keep both files out of the repository.

## Building the images yourself

Every bitstream here can be rebuilt; the md5 in `bitstreams/MANIFEST.md`
identifies the one you have.

```sh
tools/install-overlay.sh /path/to/MiSTeX-ports
cd /path/to/MiSTeX-ports
venv/bin/python mistex_boards/c1100_ps2_iop.py --build          # ~15 min
venv/bin/python mistex_boards/c1100_hps_video_test.py --build   # ~10 min
venv/bin/python mistex_boards/c1100_pcie_video.py --build       # ~9 min
make -C build/c1100_ps2_iop/software/kernel && make -C build/c1100_ps2_iop/software/user
```

Two things to check in every build log before trusting the result, because
both have silently cost builds here: `grep -E 'No clocks matched|12-4739'`
must show only the two `12-4739` lines from Xilinx's own PCIe IP constraints,
and the timing summary must say `All user specified timing constraints are
met`. The reasons are in [docs/c1100-pcie-transport.md](c1100-pcie-transport.md).

## If something does not work

- **`tools/jtag-load.sh` finds no device:** check `lsusb` for the FT4232H and
  that you are in `plugdev`; unplug and replug the card's USB.
- **The card disappears after loading:** normal until the rescan. Run
  `pcie-bringup.sh` or the test script.
- **All registers read `0xffffffff`:** see the BAR note above. Check that
  `Region 0` is 64-bit prefetchable; if it is a 32-bit BAR, the image predates
  2026-09-07 — rebuild it.
- **Identifier reads garbage, DMA never starts:** wrong driver for the image.
  Load the one from the image's own build directory.
- **The viewer opens but shows "no signal":** `video_enable` is 0, or the
  driver is the wrong one (see above). `tools/csrw.py ... read video_frames`
  twice: if it counts, the card is producing and the host side is at fault.
- **The card powers itself off during bring-up:** a design that leaves
  `hbm_cattrip` floating. Every board target here drives it low; if you write
  your own, do the same.

The engineering record behind every line of this page: the transport
([c1100-pcie-transport.md](c1100-pcie-transport.md)), the video path
([host-video-path.md](host-video-path.md)), the PS2 IOP
([ps2-iop-bringup.md](ps2-iop-bringup.md)), and the fitted cores
([retro-cores.md](retro-cores.md)).
