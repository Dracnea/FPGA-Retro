#
# video_sink -- a MiSTer core's video output as a FRM1 stream for the PCIe DMA.
#
# The core side is what every MiSTer `emu` produces: VGA_R/G/B (8 bits each),
# VGA_HS, VGA_VS, VGA_DE and CE_PIXEL in the CLK_VIDEO domain.  The host side
# is the LitePCIe DMA writer's sink (128-bit beats) in the sys domain; the
# host viewer (host/viewer) reads the ring buffers the DMA fills.
#
# Stream format "FRM1", all 32-bit little-endian words in 16-byte beats:
#   header beat  word0 0x314D5246 ('F','R','M','1')
#                word1 (height << 16) | width
#                word2 frame number
#                word3 flags: bit0 field 1 (interlaced), bits 15:8 pixel format (0 = XRGB8888)
#   pixel beats  ceil(width*height/4) beats of 0x00RRGGBB, row-major, zero padded
# Frames follow each other with no trailer.
#
# Two things about the design that are not obvious:
#
# * There is no framebuffer.  Pixels are packed as they arrive and go through
#   a FIFO of a few lines straight to the DMA, which is what keeps the cost to
#   a few BRAMs and the latency to under a line.  The DMA ring in host RAM is
#   the frame store.  The price is that the header carries the dimensions of
#   the PREVIOUS frame (the current one has not been measured yet); cores have
#   fixed timing, so this is only wrong for one frame after a mode change,
#   which the viewer detects and drops.
# * Video is real time and the host is not.  When the FIFO is full the sink
#   drops the rest of the current frame and every frame until one starts with
#   room for its header, and counts the drops.  It never back-pressures the
#   core.
#
# Frame start is the first DE after any VSYNC edge, so the polarity of VS
# (which differs between cores) does not matter.  Line end is DE falling.
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.fifo import AsyncFIFO

from litex.gen.fhdl.module import LiteXModule
from litex.soc.interconnect.csr import CSRStorage, CSRStatus, CSRField, AutoCSR

FRM1_MAGIC = 0x314D5246


class VideoSink(Module):
    """Pure migen.  Video in `vid_cd`, stream out in `sys`.

    Video side (vid_cd): r, g, b, hs, vs, de, ce_pix, f1
    Host side (sys):     data (128), valid, ready; stats width, height, frames, drops, level_max
    Control (sys):       enable
    """
    def __init__(self, vid_cd="vid", fifo_depth=1024):
        # video side
        self.r  = Signal(8); self.g = Signal(8); self.b = Signal(8)
        self.hs = Signal(); self.vs = Signal(); self.de = Signal(); self.ce_pix = Signal(); self.f1 = Signal()
        # host side
        self.data   = Signal(128)
        self.valid  = Signal()
        self.ready  = Signal()
        self.enable = Signal()
        self.width  = Signal(12); self.height = Signal(12)
        self.frames = Signal(32); self.drops  = Signal(32)

        # --- FIFO: 128-bit beats, written in vid, read in sys --------------------
        fifo = ClockDomainsRenamer({"write": vid_cd, "read": "sys"})(AsyncFIFO(128, fifo_depth))
        self.submodules.fifo = fifo
        self.comb += [
            self.data.eq(fifo.dout),
            self.valid.eq(fifo.readable),
            fifo.re.eq(fifo.readable & self.ready),
        ]

        # --- vid side ---------------------------------------------------------
        enable_v = Signal()
        self.specials += MultiReg(self.enable, enable_v, vid_cd)
        sync_v = getattr(self.sync, vid_cd)

        vs_prev  = Signal(); de_prev = Signal(); vs_seen = Signal()
        x        = Signal(12); y = Signal(12)
        w_meas   = Signal(12); h_meas = Signal(12)   # measured in the frame just finished
        measured = Signal()                           # at least one full frame measured
        frame_no = Signal(32)
        drops_v  = Signal(32); frames_v = Signal(32)
        dropping = Signal()
        in_frame = Signal()
        pack     = Signal(128); npack = Signal(2)     # pixels packed into the pending beat
        push     = Signal(); push_data = Signal(128)  # request to write one beat this cycle

        frame_start = Signal(); line_end = Signal(); frame_end = Signal(); pixel = Signal(); active = Signal()
        self.comb += [
            frame_start.eq(self.de & ~de_prev & vs_seen),
            line_end.eq(~self.de & de_prev),
            frame_end.eq((self.vs != vs_prev) & in_frame),      # any VS edge ends the frame
            active.eq(self.de & self.ce_pix & (in_frame | (frame_start & enable_v))),  # incl. the frame's first pixel
            pixel.eq(active & ~dropping),                       # streamed
        ]

        # FIFO write: one beat per cycle at most.  A header and a flushed partial
        # beat never coincide with a pixel beat because they happen on frame
        # boundaries where DE is low.
        self.comb += [fifo.din.eq(push_data), fifo.we.eq(push & fifo.writable)]

        sync_v += [
            vs_prev.eq(self.vs), de_prev.eq(self.de),
            push.eq(0),
            If(self.vs != vs_prev, vs_seen.eq(1)),
            If(self.de, vs_seen.eq(0)),

            # frame end: flush a partial beat, record the dimensions
            If(frame_end,
                in_frame.eq(0),
                If(y != 0, h_meas.eq(y), measured.eq(1)),
                If(npack != 0,
                    push.eq(~dropping), push_data.eq(pack), npack.eq(0), pack.eq(0)),
                If(~dropping, frames_v.eq(frames_v + 1)),
                dropping.eq(0),
                x.eq(0), y.eq(0),
            ),

            # frame start: header beat with the previous frame's dimensions
            If(frame_start & enable_v,
                in_frame.eq(1), x.eq(0), y.eq(0), npack.eq(0), pack.eq(0),
                frame_no.eq(frame_no + 1),
                If(measured & fifo.writable,
                    push.eq(1),
                    push_data.eq(Cat(Constant(FRM1_MAGIC, 32), w_meas, Constant(0, 4), h_meas, Constant(0, 4),
                                     frame_no, self.f1, Constant(0, 31))),
                    dropping.eq(0),
                ).Else(
                    dropping.eq(1),                         # nothing to say yet, or no room: skip this frame
                    If(measured, drops_v.eq(drops_v + 1)),
                ),
            ),

            # pixels
            If(active, x.eq(x + 1)),
            If(pixel,
                Case(npack, {
                    0: pack[0:32].eq(Cat(self.b, self.g, self.r, Constant(0, 8))),
                    1: pack[32:64].eq(Cat(self.b, self.g, self.r, Constant(0, 8))),
                    2: pack[64:96].eq(Cat(self.b, self.g, self.r, Constant(0, 8))),
                    3: pack[96:128].eq(Cat(self.b, self.g, self.r, Constant(0, 8))),
                }),
                npack.eq(npack + 1),
                If(npack == 3,
                    push.eq(1),
                    push_data.eq(Cat(pack[0:96], self.b, self.g, self.r, Constant(0, 8))),
                    pack.eq(0),
                ),
            ),
            If(line_end & in_frame,
                y.eq(y + 1), x.eq(0),
                If(x != 0, w_meas.eq(x)),
            ),

            # overflow: a beat that could not be written loses the rest of the frame
            If(push & ~fifo.writable & in_frame & ~dropping,
                dropping.eq(1), drops_v.eq(drops_v + 1),
            ),
        ]

        # --- stats to sys (quasi-static counters) --------------------------------
        for src, dst in ((w_meas, self.width), (h_meas, self.height), (frames_v, self.frames),
                         (drops_v, self.drops)):
            self.specials += MultiReg(src, dst, "sys")


class VideoSinkCSR(LiteXModule, AutoCSR):
    """VideoSink with its control and statistics on CSRs and a stream endpoint
    for the LitePCIe DMA writer's sink."""
    def __init__(self, vid_cd="vid", fifo_depth=1024):
        from litex.soc.interconnect import stream
        from litepcie.common import dma_layout
        self.enable = CSRStorage(1, description="1 streams frames; 0 stops after the current one")
        self.dims   = CSRStatus(fields=[
            CSRField("width",  size=12, offset=0,  description="measured active pixels per line"),
            CSRField("height", size=12, offset=16, description="measured active lines per frame"),
        ])
        self.frames    = CSRStatus(32, description="frames streamed")
        self.drops     = CSRStatus(32, description="frames dropped (FIFO full)")

        self.sink   = sink = VideoSink(vid_cd, fifo_depth)
        self.submodules += sink
        self.source = source = stream.Endpoint(dma_layout(128))
        self.comb += [
            sink.enable.eq(self.enable.storage),
            source.valid.eq(sink.valid), source.data.eq(sink.data), sink.ready.eq(source.ready),
            self.dims.fields.width.eq(sink.width), self.dims.fields.height.eq(sink.height),
            self.frames.status.eq(sink.frames), self.drops.status.eq(sink.drops),
        ]
        # video inputs, for the board file to wire
        self.r, self.g, self.b = sink.r, sink.g, sink.b
        self.hs, self.vs, self.de, self.ce_pix, self.f1 = sink.hs, sink.vs, sink.de, sink.ce_pix, sink.f1


class VGAPattern(Module):
    """A stand-in core: 640x480 colour bars with a moving bar, MiSTer-style
    VGA_* outputs in the `vid` domain at one pixel per clock (25 MHz -> ~59.5 Hz
    with 800x525 timing)."""
    def __init__(self, h_active=640, h_total=800, v_active=480, v_total=525):
        self.r  = Signal(8); self.g = Signal(8); self.b = Signal(8)
        self.hs = Signal(); self.vs = Signal(); self.de = Signal(); self.ce_pix = Signal(reset=1); self.f1 = Signal()
        hcnt = Signal(12); vcnt = Signal(12); frame = Signal(8)
        self.sync.vid += [
            If(hcnt == h_total - 1,
                hcnt.eq(0),
                If(vcnt == v_total - 1, vcnt.eq(0), frame.eq(frame + 1)).Else(vcnt.eq(vcnt + 1)),
            ).Else(hcnt.eq(hcnt + 1)),
        ]
        active = Signal()
        self.comb += [
            active.eq((hcnt < h_active) & (vcnt < v_active)),
            self.de.eq(active),
            self.hs.eq((hcnt >= h_active + 16) & (hcnt < h_active + 16 + 96)),
            self.vs.eq((vcnt >= v_active + 10) & (vcnt < v_active + 12)),
        ]
        bar = Signal(3)
        self.comb += bar.eq(hcnt[7:10])          # 8 bars of 128 px... 640/128 = 5, so bars 0-4 visible
        moving = Signal()
        self.comb += moving.eq((hcnt[0:8] == frame) & (vcnt >= 32) & (vcnt < 448))
        self.comb += [
            self.r.eq(Mux(moving, 0xFF, Mux(bar[0], 0xFF, 0x20))),
            self.g.eq(Mux(moving, 0xFF, Mux(bar[1], 0xFF, 0x20))),
            self.b.eq(Mux(moving, 0xFF, Mux(bar[2], 0xFF, 0x20))),
        ]


if __name__ == "__main__":
    import sys
    from migen.fhdl.verilog import convert
    s = VideoSink("vid", fifo_depth=64)     # small FIFO so the bench can fill it
    ios = {s.r, s.g, s.b, s.hs, s.vs, s.de, s.ce_pix, s.f1, s.data, s.valid, s.ready, s.enable,
           s.width, s.height, s.frames, s.drops}
    out = sys.argv[1] if len(sys.argv) > 1 else "video_sink.v"
    convert(s, ios, name="video_sink").write(out)
    print("wrote", out)
