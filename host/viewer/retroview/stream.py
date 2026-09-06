"""FRM1: the frame stream format the gateware video sink emits.

A continuous stream of 32-bit little-endian words in 16-byte beats:

  header beat   word0 = 0x314D5246 ('F','R','M','1' as bytes)
                word1 = (height << 16) | width
                word2 = frame number, 32-bit, wraps
                word3 = flags: bit0 interlaced field 1; bits 15:8 pixel format
                        (0 = XRGB8888, 0x00RRGGBB); the rest reserved 0
  pixel beats   ceil(width*height/4) beats, row-major 0x00RRGGBB, zero-padded
                to the beat

Frames follow each other with no trailer. The card may drop frames under
backpressure (frame numbers skip) or cut one short (the next header arrives
early); the parser resynchronises by scanning for a header that passes the
sanity check and drops what it was in the middle of.
"""
from __future__ import annotations
import struct
from dataclasses import dataclass, field

MAGIC = 0x314D5246
MAGIC_BYTES = b"FRM1"
BEAT = 16
HEADER = struct.Struct("<IIII")
MAX_DIM = 2048
FMT_XRGB8888 = 0


@dataclass
class Frame:
    width: int
    height: int
    number: int
    flags: int
    pixels: bytes            # width*height*4 bytes, each pixel little-endian 0x00RRGGBB (B,G,R,0 in memory)

    @property
    def field1(self) -> bool:
        return bool(self.flags & 1)

    @property
    def pixel_format(self) -> int:
        return (self.flags >> 8) & 0xFF

    @property
    def payload_bytes(self) -> int:
        return payload_bytes(self.width, self.height)


def payload_bytes(width: int, height: int) -> int:
    """Pixel bytes on the wire: beat-padded."""
    return ((width * height + 3) // 4) * BEAT


def header_ok(width: int, height: int, flags: int) -> bool:
    return 1 <= width <= MAX_DIM and 1 <= height <= MAX_DIM and (flags & 0xFFFF00FE) == 0


def pack_header(width: int, height: int, number: int, flags: int = 0) -> bytes:
    return HEADER.pack(MAGIC, (height << 16) | width, number & 0xFFFFFFFF, flags)


def pack_frame(width: int, height: int, number: int, pixels: bytes, flags: int = 0) -> bytes:
    """Build one on-the-wire frame from raw pixel bytes (width*height*4)."""
    assert len(pixels) == width * height * 4
    pad = payload_bytes(width, height) - len(pixels)
    return pack_header(width, height, number, flags) + pixels + bytes(pad)


@dataclass
class Stats:
    frames: int = 0          # frames delivered
    dropped: int = 0         # frame-number gaps (frames the card did not send)
    resyncs: int = 0         # times the parser had to search for a header
    discarded: int = 0       # bytes thrown away while searching
    bad_headers: int = 0     # magic found but sanity failed
    last_number: int | None = None


class Frm1Parser:
    """Feed bytes in any chunking; iterate frames out."""

    def __init__(self):
        self.buf = bytearray()
        self.stats = Stats()
        self._synced = False

    def feed(self, data: bytes):
        self.buf += data

    def frames(self):
        """Yield every complete Frame currently in the buffer."""
        while True:
            f = self._next()
            if f is None:
                return
            yield f

    # -- internals -------------------------------------------------------
    def _find_header(self, start: int) -> int:
        """Index of the next plausible header at or after start, or -1."""
        i = start
        while True:
            i = self.buf.find(MAGIC_BYTES, i)
            if i < 0 or i + BEAT > len(self.buf):
                return -1
            _, dim, _, flags = HEADER.unpack_from(self.buf, i)
            if header_ok(dim & 0xFFFF, dim >> 16, flags):
                return i
            self.stats.bad_headers += 1
            i += 4

    def _next(self):
        if not self._synced:
            i = self._find_header(0)
            if i < 0:
                # keep the last 15 bytes in case a magic straddles chunks
                keep = min(len(self.buf), BEAT - 1)
                self.stats.discarded += len(self.buf) - keep
                if keep:
                    del self.buf[:-keep]
                else:
                    self.buf.clear()
                return None
            if i:
                self.stats.discarded += i
                del self.buf[:i]
            self._synced = True

        if len(self.buf) < BEAT:
            return None
        magic, dim, number, flags = HEADER.unpack_from(self.buf, 0)
        width, height = dim & 0xFFFF, dim >> 16
        if magic != MAGIC or not header_ok(width, height, flags):
            # what should have been a header is not: a frame was cut short
            self._synced = False
            self.stats.resyncs += 1
            del self.buf[:4]
            self.stats.discarded += 4
            return self._next()
        need = BEAT + payload_bytes(width, height)
        if len(self.buf) < need:
            return None
        # a header inside the payload means this frame was cut short: drop it
        j = self._find_header(BEAT)
        if 0 <= j < need:
            self.stats.resyncs += 1
            self.stats.discarded += j
            del self.buf[:j]
            return self._next()
        pixels = bytes(self.buf[BEAT:BEAT + width * height * 4])
        del self.buf[:need]
        st = self.stats
        if st.last_number is not None:
            gap = (number - st.last_number - 1) & 0xFFFFFFFF
            if 0 < gap < 0x80000000:
                st.dropped += gap
        st.last_number = number
        st.frames += 1
        return Frame(width, height, number, flags, pixels)
