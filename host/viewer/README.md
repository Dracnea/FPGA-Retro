# retroview — the window on this machine

The card streams every frame a core draws into host RAM over PCIe DMA. This
package puts those frames in a window on whatever GPU the machine has, so each
machine that has the card gets its own view: this server with its RTX 4090
today, a gaming PC on Ubuntu 24 or Windows 10/11 later. It is an installable
package with the driver-specific part behind one small interface
(`retroview/transport`), so the same code moves from machine to machine and
only the transport changes.

Python 3.10+ and pygame (whose wheel bundles SDL2, so no system SDL, X11 or
GL development packages are needed — this host has none and it runs).

## Install (Ubuntu 24)

```sh
cd host/viewer
python3 -m venv .venv                 # if this host's python lacks ensurepip: python3 -m venv --without-pip .venv
.venv/bin/pip install -e .            #   and use another pip with: pip --python .venv/bin/python install -e .
.venv/bin/retroview --transport synth # colour bars from the generator: the window works
```

`/dev/litepcie0` must be readable (`tools/99-litepcie.rules`, or run as root).

## Run against the card

Once a bitstream with the video sink is loaded (see the FPGA-Retro docs for
which):

```sh
.venv/bin/retroview                                   # litepcie transport, /dev/litepcie0
.venv/bin/retroview --record session.frm1             # keep the raw stream for replay elsewhere
.venv/bin/retroview --transport file --file session.frm1 --loop
```

Keys: `F` fullscreen, `S` screenshot (PNG in the current directory), `N`
nearest/linear filter, `I` integer/aspect scaling, `Esc` quit. The overlay
shows source size and frame number, frames shown per second, frames arriving
per second, frames the card dropped (frame-number gaps), parser resyncs, and
bytes received.

Options: `--scale integer|aspect`, `--filter nearest|linear`, `--window WxH`,
`--headless --frames N --screenshot out.png` for tests, and for the synthetic
source `--size WxH --fps F --synth-drop N --synth-mode-change N`.

## Transports

| name | what | state |
|---|---|---|
| `litepcie` | Linux, the LitePCIe kernel driver's writer DMA ring, zero-copy mmap; a line-for-line mirror of liblitepcie's `litepcie_dma.c` | written, **not run** (the card was busy) |
| `file` | replay of a recorded stream, optionally looped | verified |
| `synth` | generated FRM1 frames: colour bars, moving stripe and band, optional drops and mode changes | verified |
| `windows` | placeholder that says what a Windows backend needs | — |

**Windows.** pygame and everything above the transport run on Windows
unchanged. What is missing is a driver exposing the LitePCIe endpoint the way
the Linux one does (BAR0 register access and the 256 x 8 KiB writer ring with
its hardware/software counters and a completion wake), and a
`WindowsTransport` mirroring `LitePCIeTransport.read()` over its
`DeviceIoControl` calls. The decision is Windows-specific driver files rather
than a different gateware transport; a distributable driver has to be signed.

## The FRM1 stream

32-bit little-endian words in 16-byte beats, frames back to back, no trailer:

| beat | words |
|---|---|
| header | `0x314D5246` (`F R M 1`), `(height << 16) \| width`, frame number (wraps at 2^32), flags: bit 0 interlaced field 1, bits 15:8 pixel format (0 = XRGB8888 `0x00RRGGBB`), rest 0 |
| pixels | `ceil(width*height/4)` beats, row-major `0x00RRGGBB`, zero-padded to the beat |

The parser (`retroview/stream.py`) resynchronises by scanning for a header
that passes the sanity check (magic, 1 ≤ width, height ≤ 2048, reserved flag
bits 0), drops a frame that a later header interrupts (the card gave up on it
under backpressure), counts frame-number gaps as dropped frames, and treats a
size change between frames as a normal mode change.

## Verified here (2026-09-06, headless, `SDL_VIDEODRIVER=dummy`)

- `pytest tests`: 8 passed — round trip at chunk sizes 1/7/16/8192/whole,
  beat padding, resync from garbage and from a magic with bad dimensions,
  drop counting, frame-number wrap, a truncated frame followed by a good one,
  a mode change, header layout against the spec.
- `retroview --transport synth --headless --frames 120 --fps 240`: shown 120,
  parsed 128, 0 dropped, 0 resyncs, screenshot is the 320x240 frame with the
  bars where the generator put them.
- with `--synth-drop 10 --synth-mode-change 25 --scale aspect --filter linear`:
  100 shown, 11 dropped counted (the generator skipped 11), 0 resyncs.
- record 30 frames of 256x224 to a file (7,569,936 bytes = 33 x 229,392, the
  exact FRM1 size), replay it: 33 parsed, 0 resyncs; `--loop` runs on.
- `--transport windows` and a missing device node both fail with one clear
  line and a non-zero exit.

"Shown" is lower than "parsed" when the source is faster than real time (a
replay, or `--fps 240`): the viewer drains everything available each loop and
puts only the newest frame on screen, which is the right behaviour for a live
card and means a fast replay skips frames.

Not verified: anything on the `litepcie` transport, and a real window on a
real GPU (this host has no display session; the code path is the same as the
dummy driver's).
