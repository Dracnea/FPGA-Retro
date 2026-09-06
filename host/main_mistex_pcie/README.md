# Main_MiSTeX on an x86-64 host over PCIe

Main_MiSTeX is the MiSTeX GUI: menu, OSD, ROM loading, controllers. Upstream
it runs on a Raspberry Pi Zero and reaches the core's `hps_io` through an SPI
slave (`sys/hps_interface.v`) driven from `/dev/spidev1.0`, with four GPIO
levels beside it. The UltraScale+ cards have neither; the same bridge is a
CSR block (`hps`) on the LitePCIe BAR. This directory makes Main_MiSTeX build
natively on this host and talk to that block.

Main_MiSTeX is MiSTeX-devel's repository, so nothing is committed there: the
port is new files plus a two-file patch, applied with:

```sh
host/main_mistex_pcie/apply.sh ~/Main_MiSTeX
cd ~/Main_MiSTeX && make -f Makefile.x86_64 -j
cp <bitstream>.csr.csv ./csr.csv          # the csr.csv generated with the loaded bitstream
./MiSTer.elf                              # or ./MiSTer (stripped)
```

Written against Main_MiSTeX `f8705a5` (2026-09-06).

## What changes

| file | what |
|---|---|
| `fpga_io_pcie.cpp` (new) | the whole `fpga_io.h` API over the litepcie register ioctl, selected by `-DPCIE_HOST` |
| `Makefile.x86_64` (new) | native toolchain; libco's amd64 backend; no libgpiod / spidev at link time |
| `lib/imlib2_stub/imlib2_stub.c` (new) | the 14 Imlib2 calls Main uses, as a stand-in (no libImlib2 on this host) |
| `lib/host_stubs/bt_stub.c` (new) | `hci_get_route()` returning "no adapter" (no libbluetooth on this host) |
| `fpga_io.cpp` (patch) | wrapped in `#ifndef PCIE_HOST`; the Pi build is unchanged |
| `shmem.cpp` (patch) | comment only: where DMA goes when a framebuffer exists |

The gateware CSR contract the backend expects (LiteX module `hps`, names
`hps_*` in `csr.csv`; the file is read at start-up, addresses are never
hard-coded):

| register | | |
|---|---|---|
| `hps_control` | rw | bit0 fpga_en, bit1 osd_en, bit2 io_en (the `SSPI_*_EN` levels `fpga_spi_en()` used to drive on GPIO), bit3 core_reset, bit4 btn_osd, bit5 btn_user |
| `hps_din` | wo | 16-bit: one SPI-word transaction — the core's `io_dout` is latched into `hps_dout`, the word becomes `io_din`, `io_strobe` pulses once |
| `hps_din2` | wo | two words, low half first, transacted back to back (used by the block-write paths to halve the ioctl count) |
| `hps_dout` | ro | the `io_dout` latched by the last transaction |
| `hps_status` | ro | bit0 io_wide, bit1 busy |

`fpga_spi(word)` is therefore: write `hps_din`, poll `busy` to 0, read
`hps_dout` — the same value the SPI version clocked back during the word.
The block functions keep the SPI implementation's leading zero word.

Environment: `MISTEX_PCIE_DEV` (default `/dev/litepcie0`; needs
`tools/99-litepcie.rules` or root), `MISTEX_CSR_CSV` (default: `csr.csv`
beside the executable, then `./csr.csv`, then `/etc/mistex/csr.csv`).

## Verified

- Builds and links on this host (Ubuntu 24.04, gcc 13.3): `MiSTer.elf`
  1.36 MB, `MiSTer` stripped 1.19 MB.
- Started with a `csr.csv` carrying the five `hps_*` rows and
  `MISTEX_PCIE_DEV` pointing at a non-existent node: it reports
  `ERROR: cannot open /dev/litepcie_none: No such file or directory (is the
  litepcie driver loaded ...)`, prints the banner, then `FPGA is
  uninitialized or incompatible core loaded. Quitting.` and exits 0 — the
  normal Main path for "no FPGA", reached through `is_fpga_ready()`.
- Not run against `/dev/litepcie0`: the card is busy with other work, and no
  bitstream with the `hps` block has been loaded yet. The first real test is
  `fpga_get_fio_size()` / `fpga_spi()` against the config-string read
  (`user_io_init` → `UIO_GET_STRING`), which needs that bitstream.

## Stubbed, and what it costs

- **Imlib2**: image load/save fail cleanly; in-memory images (menu background
  layers, curtain) exist; blending is a rectangle copy without scaling or
  alpha. Affects only the menu wallpaper and screenshots, which nobody can see
  until the host video viewer exists. `Makefile.x86_64` says how to switch to
  the real library (`libimlib2-dev`, plus freetype/png/bz2/z dev packages)
  once it is installed.
- **Bluetooth**: the pairing entries are hidden. `libbluetooth-dev` restores
  them (`BT_SRC`/`BT_LIB` in the Makefile).
- **`fpga_load_rbf()`**: the card is programmed over JTAG or by the user, not
  from Main. It logs the bitstream the menu asked for, treats it as loaded,
  and restarts Main for that core's configuration. Selecting a core in the
  menu therefore does not change what is in the FPGA.
- **`reboot()`**: never reboots the host; resets the core and exits.
- **`fpga_get_buttons()`**: the card has no buttons; reads back the `btn_*`
  bits in `hps_control` so a host tool can press them. The keyboard path
  through `input.cpp` is the normal way to open the menu.
- **`shmem_*`**: still the MiSTeX stubs (they print `TODO: not implemented`).
  They become LitePCIe DMA once the framebuffer / DDRAM bridge exists in the
  gateware — `docs/retro-cores.md`, "The three things every core needs", item
  3 — and `shmem.cpp` is the only place that changes.
- **Storage**: `getRootDir()` is still `/media/fat`; create it or bind-mount a
  games tree there.
- `brightness.cpp` still opens `/dev/spidev1.0` when a battery/backlight
  device is configured; it fails quietly on this host.

## Not done here

A host-side viewer for the DMA'd frames (the "GPU → HDMI/DP" row of the
README status table) and the video/DDRAM gateware it needs. Without them Main
runs, initialises the core over the bridge and drives the OSD, but the OSD is
rendered into a frame nobody displays yet.
