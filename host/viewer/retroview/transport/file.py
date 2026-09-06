from __future__ import annotations
import time
from .base import Transport
from ..stream import pack_frame

CHUNK = 8192     # one DMA buffer's worth, so replay looks like the ring


class FileTransport(Transport):
    """Replay a recorded stream (Recorder output, or anything in FRM1)."""
    def __init__(self, path: str, loop: bool = False, **_):
        super().__init__()
        self.path, self.loop, self._f = path, loop, None
        self._eof = False

    @property
    def eof(self) -> bool:
        return self._eof

    def open(self):
        self._f = open(self.path, "rb")

    def read(self) -> bytes:
        d = self._f.read(CHUNK)
        if not d and self.loop:
            self._f.seek(0); d = self._f.read(CHUNK)
        if not d:
            self._eof = True
        if d:
            self.stats.chunks += 1; self.stats.bytes += len(d)
        else:
            self.stats.waits += 1
        return d

    def close(self):
        if self._f:
            self._f.close(); self._f = None


def bars_row(width: int) -> bytes:
    """One row of eight SMPTE-ish colour bars as little-endian 0x00RRGGBB."""
    cols = [(0xC0, 0xC0, 0xC0), (0xC0, 0xC0, 0x00), (0x00, 0xC0, 0xC0), (0x00, 0xC0, 0x00),
            (0xC0, 0x00, 0xC0), (0xC0, 0x00, 0x00), (0x00, 0x00, 0xC0), (0x10, 0x10, 0x10)]
    row = bytearray()
    for x in range(width):
        r, g, b = cols[x * 8 // width]
        row += bytes((b, g, r, 0))
    return bytes(row)


class SynthTransport(Transport):
    """FRM1 frames of colour bars with a moving white stripe, paced at fps.

    A mode change every `mode_change_every` frames (0 = never) and a dropped
    frame every `drop_every` frames (0 = never) exercise the parser the way
    the card would.
    """
    def __init__(self, width=320, height=240, fps=60.0, mode_change_every=0, drop_every=0,
                 alt_size=(256, 224), **_):
        super().__init__()
        self.width, self.height, self.fps = width, height, fps
        self.mode_change_every, self.drop_every, self.alt_size = mode_change_every, drop_every, alt_size
        self.number = 0
        self._pending = b""
        self._t0 = None
        self._rows = {}

    def open(self):
        self._t0 = time.monotonic()

    def _frame(self, w: int, h: int, n: int) -> bytes:
        row = self._rows.get(w)
        if row is None:
            row = self._rows[w] = bars_row(w)
        pos = (n * 2) % w
        stripe = bytes((0xFF, 0xFF, 0xFF, 0)) * 8
        r = bytearray(row)
        r[pos * 4:pos * 4 + 32] = stripe[:max(0, min(32, (w - pos) * 4))]
        r = bytes(r[:w * 4])
        # a band that moves down, so vertical position is visible too
        band_y = (n * 3) % h
        rows = []
        for y in range(h):
            if band_y <= y < band_y + 4:
                rows.append(bytes((0x40, 0x40, 0x40, 0)) * w)
            else:
                rows.append(r)
        return pack_frame(w, h, n, b"".join(rows))

    def read(self) -> bytes:
        if self._pending:
            d, self._pending = self._pending[:CHUNK], self._pending[CHUNK:]
            self.stats.chunks += 1; self.stats.bytes += len(d)
            return d
        due = self._t0 + self.number / self.fps
        if time.monotonic() < due:
            self.stats.waits += 1
            time.sleep(min(0.002, due - time.monotonic()))
            return b""
        n = self.number
        self.number += 1
        if self.drop_every and n % self.drop_every == self.drop_every - 1:
            return b""                              # the card skipped this one
        w, h = self.width, self.height
        if self.mode_change_every and (n // self.mode_change_every) % 2 == 1:
            w, h = self.alt_size
        self._pending = self._frame(w, h, n)
        return self.read()

    def close(self):
        pass
