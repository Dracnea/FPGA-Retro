# The video path: core VGA output → FRM1 stream → PCIe DMA → a window on the host GPU

Written 2026-09-06. This is item 2 of "the three things every core needs"
([retro-cores.md](retro-cores.md)) and the "GPU → HDMI/DP" row of the README:
the picture leaves the card over PCIe and is shown by software on whatever GPU
the host has. The platform decision behind it: the PC is the host of
everything — it loads the card, shows the picture, runs the menu — and the
card is a pass-through, so the same viewer runs on this server's 4090 today
and on a gaming PC under Ubuntu 24 or Windows later.

## Gateware: `overlay/rtl/video_sink` — simulated

`video_sink.py` takes what every MiSTer `emu` produces (`VGA_R/G/B`,
`VGA_HS/VS/DE`, `CE_PIXEL` in the `CLK_VIDEO` domain) and emits the FRM1
stream into the LitePCIe DMA writer's 128-bit sink in the sys domain.

FRM1, all 32-bit little-endian words in 16-byte beats:

| beat | words |
|---|---|
| header | `0x314D5246` ("FRM1"), `(height << 16) \| width`, frame number, flags (bit 0 field 1, bits 15:8 pixel format, 0 = XRGB8888) |
| pixels | `ceil(width × height / 4)` beats of `0x00RRGGBB`, row-major, zero padded |

Frames follow each other with no trailer; the viewer resynchronises on the
magic if a frame is cut short.

Design choices, and why:

- **No framebuffer in the FPGA.** Pixels are packed four to a beat as they
  arrive and go through a 1,024-beat async FIFO straight to the DMA; the DMA
  ring in host RAM (2 MB, about 1.7 frames of 640×480) is the frame store.
  Cost is a few BRAMs and latency under a line. The header therefore carries
  the dimensions of the *previous* frame — cores have fixed timing, so this is
  wrong only for the one frame after a mode change, which the viewer drops.
- **Video is real time; the host is not.** When the FIFO is full the sink
  drops the rest of the frame and every frame until one starts with room for
  its header, counts the drops, and never back-pressures the core.
- Frame start is the first DE after *any* VSYNC edge, so VS polarity (which
  differs between cores) does not matter; line end is DE falling.

**Verified in xsim** (`overlay/rtl/video_sink/sim/run_sim.sh`): a 64×32
generator at 50 MHz pixel clock into the sink with a 64-beat FIFO, read at
125 MHz:

```
info: frame 3 truncated with 449 beats left
beats 1781 complete 3 truncated 1 bad 0  width 64 height 32 frames 3 drops 2
  complete frame #1 = frame number 1 / #2 = 2 / #3 = 5
PASS
```

Every pixel of every complete frame is checked word for word against the
generator. Stalling the reader for a frame truncates that frame after the
FIFO fills (the 63 beats already in the FIFO reach the host, as they would in
hardware), the next frame is dropped whole because its header has no room,
and the following frame streams correctly. One bug found on the way: the
first pixel of every frame was lost because the in-frame flag is registered a
cycle after DE rises; the capture now includes the frame-start cycle.

`VGAPattern` in the same file is a stand-in core: 640×480 colour bars with a
moving bar at 25 MHz (800×525 timing, ~59.5 Hz), used by the test bitstream.

## Host: `host/viewer` — verified headless

`retroview`, a Python package (pygame, whose wheel bundles SDL2, so no system
video libraries are needed and the same code runs on Windows): a FRM1 parser
with resync, drop and wrap accounting; a pygame window with integer or
aspect-correct scaling, nearest or linear filtering, an overlay with size,
frame number, shown and source fps, drops and resyncs; keys F (fullscreen),
S (screenshot), N (filter), I (overlay), Esc. Transports behind one
interface: `litepcie` (Linux, mirrors `litepcie_dma.c`'s zero-copy writer path
line for line), `file` (replay a recording, `--loop`), `synth` (colour bars
with optional drops and mode changes, for testing without a card), `windows`
(states what a Windows driver must expose; the user's decision is
Windows-specific files rather than a transport switch). A `Recorder` wraps any
transport so a real session can be replayed here.

Verified with `SDL_VIDEODRIVER=dummy`: 8 parser tests (chunking at every
boundary, resync from garbage and from a bad-dimension magic, drop counting,
2³² wrap, truncated frame dropped and the next recovered, mode change) pass;
120 synthetic frames render to a PNG whose bar colours are the expected
values, so the `0x00RRGGBB` → BGRA mapping is right; a 30-frame recording is
exactly the FRM1 size and replays; a missing device and the Windows transport
each fail with one clear line. Not verified: the `litepcie` transport (never
run; no sink bitstream has been loaded) and a real window on a real GPU (no
display session on this host; it is the same code path as the dummy driver).

Install on any machine: `host/viewer/README.md` (a venv and `pip install -e .`;
this host lacks ensurepip, and the README says how to work around it).

## Capture for review: `retroview --shots/--contact/--video`, `tools/video-capture.sh`

Added 2026-09-07 so that what a core draws can be judged by someone who was
not at the screen — including an agent working over ssh with no display,
which is how this repo is developed. `retroview` can save every Nth frame as
PNG, tile them into a contact sheet, and write an MJPEG AVI, all from its own
code (`host/viewer/retroview/capture.py`: pygame's JPEG/PNG encoders and a
RIFF writer; nothing else is needed on the machine). Verified headless on the
synthetic source; details and the alpha bug it found are in
`host/viewer/README.md`.

`tools/video-capture.sh` (root, for the PCIe part) does the whole thing on the
card: JTAG-load a video bitstream (default the pattern generator below),
rescan PCIe, load the driver, enable the sink, run retroview headless for N
seconds, and leave `session.frm1`, `session.avi`, `shots/`, `contact.png` and
the card's `video_dims / video_frames / video_drops` before and after in
`build/video/<timestamp>/`.

**Verified on hardware, 2026-09-07 22:14** (`build/video/20260907-221426`,
the rebuilt `c1100_hps_video_test.bit`, its own driver):

```
retroview: shown 600, parsed 600, dropped 0, resyncs 0, discarded 899520 B,
           bad headers 0, transport 738197504 B in 90112 chunks
video_dims 01e00280 (640x480)   video_frames +618 over the run   video_drops 0 -> 1
```

600 frames in the 10 s the script asked for, at the generator's 59.5 Hz;
738 MB moved card→host over the DMA ring in 90,112 buffers of 8 KiB; the
parser threw away 899,520 bytes once, the tail of the frame that was in
flight when the viewer attached, and resynchronised on the next header;
the sink counted one drop, the frame it truncated while the ring was
being set up. The contact sheet shows the five bars with the bright bar
walking across; the AVI is 640x480, 59.5 fps, 600 JPEG frames of ~8.7 KB.
This is the first picture off the card. The first run of the same script
an hour earlier received nothing: the driver loaded was the transport
build's, whose DMA registers are at other addresses in this image
(`c1100-pcie-transport.md`, "the driver must match the image").

The earlier attempt on 2026-09-07 17:24 with the pattern-generator image:
the load, rescan and driver went as expected and `video_enable` was written,
but `video_dims`, `video_frames` and `video_drops` all read `0xffffffff` and
no bytes arrived on the DMA — the same all-ones BAR0 reads as every other
image on this card (see `c1100-pcie-transport.md`). The viewer waited for
frames that never came, which is why `retroview` now has `--timeout` and the
script passes 15 s. Nothing about the sink or the viewer's litepcie transport
is established either way until BAR0 reads work.

What this cannot show yet: a game. No core has been placed in a board target
with `sys_top` and the memory bridge (items 3-4 of the list in
`host-gui-compatibility.md`), so the only picture the card can produce today
is the generator's colour bars. The PS2 in particular is only its IOP
(`ps2-iop-bringup.md`): no EE, VUs or GS, so no PS2 title can run on the card
and there is nothing PS2-shaped to screenshot. The first real pictures will
be from the fitted 8/16-bit cores once the board target exists.

## Test bitstream: `overlay/mistex_boards/c1100_hps_video_test.py`

The HPS transport test (`c1100_hps_test`) plus the pattern generator and the
sink on DMA0, in a 25 MHz `vid` domain, so one card load exercises both host
paths: Main_MiSTeX over the bridge and `retroview` over the DMA.

Built 2026-09-06, Vivado 2026.1, xcu55n-fsvh2892-2LV-e:

```
WNS +0.598   TNS 0.000   WHS +0.010   THS 0.000
31,213 endpoints, 0 failing
All user specified timing constraints are met.
```

| resource | used | util |
|---|---:|---:|
| CLB LUTs | 5,214 | 0.60 % |
| CLB registers | 10,183 | 0.58 % |

`bitstreams/c1100_hps_video_test.bit`, md5 `9680c6a7693fa6fefc8929b0fb5a7b78`,
with its `csr.csv`. **Rebuilt 2026-09-07 21:05 with BAR0 64-bit
prefetchable** (see `c1100-pcie-transport.md` for why): md5
`074562fc4f493161d0710d533effa420`, WNS +0.598 ns, 0 failing endpoints,
CSR map unchanged. The pattern generator and sink add about 420 LUTs to the
HPS test image. Three MMCM outputs (sys, core, vid) are declared asynchronous
by pin in the pre-placement commands; the log has no `No clocks matched`, and
the only `12-4739` lines are the two from Xilinx's PCIe IP.

When the card is free: load it, rescan PCIe (`docs/c1100-pcie-transport.md`),
then

```sh
cd host/viewer && .venv/bin/retroview --transport litepcie --csr ../../bitstreams/c1100_hps_video_test.csr.csv
```

after `tools/csrw.py --csr bitstreams/c1100_hps_video_test.csr.csv write
video_enable 1` (`csrw.py read video_dims` / `video_drops` for the
statistics). The expected picture is five colour bars with a bright bar sweeping across at
~59.5 frames per second, `video_dims` reading 640×480, `video_drops` staying
at 0 while the viewer keeps up.

## What this does not do yet

- **Audio.** MiSTer sends audio to HDMI; here it becomes a second stream
  (a small header plus 16-bit stereo samples) on the same DMA and a pygame
  audio sink in the viewer. Not started.
- **Integer-multiple resolutions above 2048 or interlaced fields** are not
  handled specially; `f1` is carried in the flags.
- **The OSD** is drawn inside the FPGA by `osd.v` in `sys_top`, over the
  core's picture, so it arrives in the stream for free once `sys_top` is in
  the build; nothing in the viewer needs to know about it.
- **Windows** needs a driver exposing the DMA ring; the transport interface
  is the seam.
