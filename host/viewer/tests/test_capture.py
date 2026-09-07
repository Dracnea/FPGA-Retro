import os, subprocess, sys
import pytest
from retroview.capture import MjpegAvi, ShotSink, read_avi_index
from retroview.stream import Frm1Parser, pack_frame


def _pg():
    os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    import pygame as pg
    pg.init(); pg.display.set_mode((64, 64))
    return pg


def _frames(sizes):
    p = Frm1Parser()
    for n, (w, h) in enumerate(sizes):
        px = bytes(((x * 3 + y * 5 + n) & 0xFF) for y in range(h) for x in range(w) for _ in range(4))
        p.feed(pack_frame(w, h, n, px))
    return list(p.frames())


def test_avi_roundtrip(tmp_path):
    pg = _pg()
    out = str(tmp_path / "t.avi")
    avi = MjpegAvi(out, fps=59.5, quality=85)
    frames = _frames([(64, 48)] * 5 + [(32, 24)] + [(64, 48)] * 2)     # a mode change in the middle
    for f in frames:
        avi.add(pg, f)
    assert avi.close() == out
    w, h, fps, sizes = read_avi_index(out)
    assert (w, h) == (64, 48) and abs(fps - 59.5) < 0.01
    assert len(sizes) == 8 and all(s > 100 for s in sizes)
    hdrl = 12 + (8 + 56) + (12 + (8 + 56) + (8 + 40))          # LIST hdrl: avih, LIST strl: strh, strf
    assert os.path.getsize(out) == 12 + hdrl + 12 + sum(8 + s + (s & 1) for s in sizes) + 8 + 16 * 8


def test_avi_every_and_empty(tmp_path):
    pg = _pg()
    out = str(tmp_path / "e.avi")
    avi = MjpegAvi(out, fps=60, every=3)
    for f in _frames([(16, 16)] * 10):
        avi.add(pg, f)
    avi.close()
    assert len(read_avi_index(out)[3]) == 4                 # frames 0,3,6,9
    assert MjpegAvi(str(tmp_path / "none.avi")).close() is None
    assert not os.path.exists(tmp_path / "none.avi")


def test_shots_and_contact(tmp_path):
    pg = _pg()
    d = str(tmp_path / "shots"); sheet = str(tmp_path / "sheet.png")
    sink = ShotSink(d, every=4, contact=sheet, contact_cols=3, contact_max=4)
    for f in _frames([(40, 30)] * 20):
        sink.add(pg, f)
    assert sorted(os.listdir(d)) == [f"frame-{n:06d}.png" for n in (0, 4, 8, 12, 16)]
    assert sink.close(pg) == sheet
    shot = pg.image.load(os.path.join(d, "frame-000004.png"))
    assert shot.get_at((1, 1))[:3] == (12, 12, 12)                # (x*3 + y*5 + n) at (1,1) of frame 4: not black, not transparent
    assert shot.get_at((1, 1))[3] == 255
    img = pg.image.load(sheet)
    assert img.get_at((6, 6))[:3] != (24, 24, 24)               # a tile is drawn over the background
    assert img.get_width() == 3 * (20 + 4) + 4 and img.get_height() == 2 * (15 + 16 + 4) + 4


def test_cli_headless_capture(tmp_path):
    d = tmp_path / "shots"; sheet = tmp_path / "sheet.png"; avi = tmp_path / "s.avi"
    r = subprocess.run([sys.executable, "-m", "retroview.cli", "--transport", "synth", "--headless", "--frames", "30",
                        "--fps", "240", "--size", "64x48", "--shots", str(d), "--shot-every", "10",
                        "--contact", str(sheet), "--video", str(avi)], capture_output=True, text=True,
                       env={**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"})
    assert r.returncode == 0, r.stderr
    assert sheet.exists() and len(list(d.glob("frame-*.png"))) >= 3
    w, h, fps, sizes = read_avi_index(str(avi))
    assert (w, h) == (64, 48) and abs(fps - 240) < 0.01 and len(sizes) >= 30
