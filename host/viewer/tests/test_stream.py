import os, struct
from retroview.stream import Frm1Parser, pack_frame, pack_header, payload_bytes, MAGIC


def px(w, h, seed=0):
    return bytes(((i * 7 + seed) & 0xFF) for i in range(w * h * 4))


def frames(p, data, chunk):
    out = []
    for i in range(0, len(data), chunk):
        p.feed(data[i:i + chunk])
        out += list(p.frames())
    return out


def test_roundtrip_any_chunking():
    data = b"".join(pack_frame(320, 240, n, px(320, 240, n)) for n in range(5))
    for chunk in (1, 7, 16, 8192, len(data)):
        p = Frm1Parser()
        got = frames(p, data, chunk)
        assert [f.number for f in got] == [0, 1, 2, 3, 4]
        assert all(f.pixels == px(320, 240, f.number) for f in got)
        assert p.stats.dropped == 0 and p.stats.resyncs == 0


def test_padding_odd_pixel_count():
    w, h = 5, 3                      # 15 pixels -> 4 beats, 4 bytes of pad
    assert payload_bytes(w, h) == 64
    p = Frm1Parser(); p.feed(pack_frame(w, h, 9, px(w, h)))
    f = list(p.frames())[0]
    assert (f.width, f.height, f.number) == (5, 3, 9) and len(f.pixels) == 60


def test_resync_from_garbage_and_junk_magic():
    junk = b"\x11" * 100 + b"FRM1" + struct.pack("<III", 0, 5, 0) + b"\x22" * 33   # magic with width 0: rejected
    good = pack_frame(64, 64, 3, px(64, 64))
    p = Frm1Parser(); p.feed(junk + good)
    got = list(p.frames())
    assert len(got) == 1 and got[0].number == 3
    assert p.stats.bad_headers == 1 and p.stats.discarded > 0


def test_dropped_frames_counted():
    data = pack_frame(32, 32, 10, px(32, 32)) + pack_frame(32, 32, 14, px(32, 32))
    p = Frm1Parser(); p.feed(data)
    assert [f.number for f in p.frames()] == [10, 14]
    assert p.stats.dropped == 3


def test_frame_number_wrap_is_not_a_drop():
    data = pack_frame(8, 8, 0xFFFFFFFF, px(8, 8)) + pack_frame(8, 8, 0, px(8, 8))
    p = Frm1Parser(); p.feed(data)
    assert [f.number for f in p.frames()] == [0xFFFFFFFF, 0]
    assert p.stats.dropped == 0


def test_truncated_frame_is_dropped_and_next_recovers():
    full = pack_frame(64, 48, 1, px(64, 48))
    cut = full[:16 + 1000]                        # the card gave up mid-frame
    nxt = pack_frame(64, 48, 2, px(64, 48, 2))
    p = Frm1Parser(); p.feed(cut + nxt)
    got = list(p.frames())
    assert [f.number for f in got] == [2] and got[0].pixels == px(64, 48, 2)
    assert p.stats.resyncs == 1


def test_mode_change():
    data = pack_frame(320, 240, 0, px(320, 240)) + pack_frame(256, 224, 1, px(256, 224)) + pack_frame(320, 240, 2, px(320, 240))
    p = Frm1Parser()
    got = frames(p, data, 4096)
    assert [(f.width, f.height, f.number) for f in got] == [(320, 240, 0), (256, 224, 1), (320, 240, 2)]
    assert p.stats.resyncs == 0


def test_header_layout_matches_spec():
    h = pack_header(320, 240, 7, 0x0001)
    w0, w1, w2, w3 = struct.unpack("<IIII", h)
    assert w0 == MAGIC == 0x314D5246 and h[:4] == b"FRM1"
    assert w1 == (240 << 16) | 320 and w2 == 7 and w3 == 1
