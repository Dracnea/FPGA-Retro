"""Capture sinks: screenshots, a contact sheet and a video file from the frames
the viewer receives, so a session can be reviewed afterwards (or by someone who
was not at the screen) without any tool beyond this package.

Everything here is pure Python on top of pygame's image encoders, so it runs
on the machine with the card whatever else is installed there:

  ShotSink    every Nth frame as PNG in a directory (frame-<number>.png), and
              optionally a contact sheet tiling them into one PNG at close
  MjpegAvi    an AVI file of JPEG frames (MJPEG). Every player opens it (VLC,
              mpv, ffmpeg, Windows Media Player), and no encoder library is
              needed. About 30-60 KB per 640x480 frame at quality 90.

Sinks receive every parsed frame, not only the ones the window showed, so a
replay faster than real time still yields a complete recording.
"""
from __future__ import annotations
import io, os, struct, time


def _surface(pg, frame):
    # the X byte of 0x00RRGGBB reads as alpha 0 through "BGRA": convert() to the
    # display format drops it, otherwise every blit and every PNG is transparent
    return pg.image.frombuffer(frame.pixels, (frame.width, frame.height), "BGRA").convert()


class ShotSink:
    def __init__(self, directory: str, every: int = 1, contact: str | None = None,
                 contact_cols: int = 6, contact_max: int = 36, contact_scale: float = 0.5):
        self.dir, self.every, self.contact = directory, max(1, every), contact
        self.cols, self.max, self.scale = max(1, contact_cols), max(1, contact_max), contact_scale
        self.count = 0          # frames offered
        self.saved = []         # (number, path)
        self._keep = []         # (number, surface) for the contact sheet
        os.makedirs(directory, exist_ok=True)

    def add(self, pg, frame):
        n = self.count
        self.count += 1
        if n % self.every:
            return
        surf = _surface(pg, frame)
        path = os.path.join(self.dir, f"frame-{frame.number:06d}.png")
        pg.image.save(surf, path)
        self.saved.append((frame.number, path))
        if self.contact:
            self._keep.append((frame.number, surf.copy()))
            if len(self._keep) > 2 * self.max:      # thin to stay bounded
                self._keep = self._keep[::2]

    def close(self, pg):
        if not self.contact or not self._keep:
            return None
        keep = self._keep
        if len(keep) > self.max:
            step = len(keep) / self.max
            keep = [keep[int(i * step)] for i in range(self.max)]
        tw = max(1, int(max(s.get_width() for _, s in keep) * self.scale))
        th = max(1, int(max(s.get_height() for _, s in keep) * self.scale))
        label = 16
        cols = min(self.cols, len(keep))
        rows = (len(keep) + cols - 1) // cols
        sheet = pg.Surface((cols * (tw + 4) + 4, rows * (th + label + 4) + 4))
        sheet.fill((24, 24, 24))
        font = pg.font.Font(None, 18)
        for i, (num, s) in enumerate(keep):
            x = 4 + (i % cols) * (tw + 4)
            y = 4 + (i // cols) * (th + label + 4)
            w = max(1, int(s.get_width() * self.scale)); h = max(1, int(s.get_height() * self.scale))
            sheet.blit(pg.transform.smoothscale(s, (w, h)), (x, y))
            sheet.blit(font.render(f"#{num} {s.get_width()}x{s.get_height()}", True, (255, 255, 0)), (x, y + th + 1))
        pg.image.save(sheet, self.contact)
        return self.contact


class MjpegAvi:
    """Write frames as an MJPEG AVI (RIFF 'AVI ' with hdrl/movi/idx1).

    The stream size is the first frame's; a frame of another size (a mode
    change) is scaled to it, so the file stays valid for every player.
    """
    AVIF_HASINDEX, AVIIF_KEYFRAME = 0x10, 0x10

    def __init__(self, path: str, fps: float = 60.0, quality: int = 90, every: int = 1):
        self.path, self.fps, self.quality, self.every = path, fps, quality, max(1, every)
        self._f = None
        self.size = None
        self.frames = 0
        self.count = 0
        self.max_chunk = 0
        self._index = []        # (offset within movi, size)
        self._movi_start = 0

    def _fourcc(self, s): return s.encode("ascii")

    def _open(self, w, h):
        self._f = open(self.path, "wb")
        self.size = (w, h)
        # placeholders; rewritten on close when sizes and counts are known
        self._f.write(b"RIFF" + b"\0\0\0\0" + b"AVI ")
        self._write_hdrl(0)
        self._movi_start = self._f.tell()
        self._f.write(b"LIST" + b"\0\0\0\0" + b"movi")

    def _write_hdrl(self, nframes):
        w, h = self.size
        us = int(round(1_000_000 / self.fps)) if self.fps > 0 else 0
        avih = struct.pack("<IIIIIIIIII4I", us, int(self.max_chunk * self.fps), 0, self.AVIF_HASINDEX,
                           nframes, 0, 1, self.max_chunk, w, h, 0, 0, 0, 0)
        scale, rate = 1000, int(round(self.fps * 1000))
        strh = b"vids" + b"MJPG" + struct.pack("<IHHIIIIIIIIhhhh", 0, 0, 0, 0, scale, rate, 0, nframes,
                                                 self.max_chunk, 10000, 0, 0, 0, w, h)
        strf = struct.pack("<IiiHH4sIiiII", 40, w, h, 1, 24, b"MJPG", w * h * 3, 0, 0, 0, 0)
        strl = b"LIST" + struct.pack("<I", 4 + 8 + len(strh) + 8 + len(strf)) + b"strl" + \
               b"strh" + struct.pack("<I", len(strh)) + strh + b"strf" + struct.pack("<I", len(strf)) + strf
        hdrl = b"avih" + struct.pack("<I", len(avih)) + avih + strl
        self._f.write(b"LIST" + struct.pack("<I", 4 + len(hdrl)) + b"hdrl" + hdrl)

    def add(self, pg, frame):
        n = self.count
        self.count += 1
        if n % self.every:
            return
        surf = _surface(pg, frame)
        if self._f is None:
            self._open(frame.width, frame.height)
        if (frame.width, frame.height) != self.size:
            surf = pg.transform.smoothscale(surf, self.size)
        buf = io.BytesIO()
        pg.image.save(surf, buf, "frame.jpg")      # SDL_image JPEG encoder
        data = buf.getvalue()
        off = self._f.tell() - self._movi_start - 8          # offset from the 'movi' fourcc
        self._f.write(b"00dc" + struct.pack("<I", len(data)) + data)
        if len(data) & 1:
            self._f.write(b"\0")
        self._index.append((off, len(data)))
        self.max_chunk = max(self.max_chunk, len(data))
        self.frames += 1

    def close(self):
        if self._f is None:
            return None
        movi_end = self._f.tell()
        idx = b"".join(b"00dc" + struct.pack("<III", self.AVIIF_KEYFRAME, off, size) for off, size in self._index)
        self._f.write(b"idx1" + struct.pack("<I", len(idx)) + idx)
        end = self._f.tell()
        self._f.seek(self._movi_start + 4); self._f.write(struct.pack("<I", movi_end - self._movi_start - 8))
        self._f.seek(4); self._f.write(struct.pack("<I", end - 8))
        self._f.seek(12); self._write_hdrl(self.frames)
        self._f.close(); self._f = None
        return self.path


def read_avi_index(path: str):
    """Parse the file back: (width, height, fps, [frame sizes]) — for tests and checks."""
    with open(path, "rb") as f:
        data = f.read()
    assert data[:4] == b"RIFF" and data[8:12] == b"AVI ", "not an AVI"
    assert struct.unpack("<I", data[4:8])[0] == len(data) - 8, "RIFF size"
    pos = 12
    w = h = None; fps = 0.0; sizes = []
    while pos + 8 <= len(data):
        tag = data[pos:pos + 4]; size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        if tag == b"LIST":
            kind = data[pos + 8:pos + 12]
            if kind == b"hdrl":
                a = pos + 12
                assert data[a:a + 4] == b"avih"
                fields = struct.unpack("<10I", data[a + 8:a + 48]); w, h = fields[8], fields[9]
                b = a + 8 + 56 + 12 + 8           # strh payload: after avih, the strl LIST header and 'strh'+size
                assert data[b:b + 4] == b"vids"
                scale, rate = struct.unpack("<II", data[b + 20:b + 28])
                fps = rate / scale if scale else 0.0
            elif kind == b"movi":
                p = pos + 12; end = pos + 8 + size
                while p + 8 <= end:
                    t = data[p:p + 4]; s = struct.unpack("<I", data[p + 4:p + 8])[0]
                    if t == b"00dc":
                        assert data[p + 8:p + 10] == b"\xff\xd8", "frame is not JPEG"
                        sizes.append(s)
                    p += 8 + s + (s & 1)
        pos += 8 + size + (size & 1)
    return w, h, fps, sizes
