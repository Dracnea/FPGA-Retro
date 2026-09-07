"""The window: frames in, pixels on this machine's GPU via pygame/SDL2."""
from __future__ import annotations
import os, time
from .stream import Frm1Parser, Frame
from .capture import ShotSink


class Viewer:
    def __init__(self, transport, window=(1280, 960), scale="integer", filt="nearest",
                 title="retroview", headless=False, max_frames=0, screenshot=None, sinks=()):
        self.transport = transport
        self.sinks = list(sinks)          # capture.ShotSink / capture.MjpegAvi: get every parsed frame
        self.window, self.scale_mode, self.filter = window, scale, filt
        self.title, self.headless, self.max_frames, self.screenshot = title, headless, max_frames, screenshot
        self.parser = Frm1Parser()
        self.fullscreen = False
        self.rendered = 0
        self._last: Frame | None = None

    # -- helpers ------------------------------------------------------------
    def _fit(self, fw, fh, ww, wh):
        if self.scale_mode == "integer":
            k = max(1, min(ww // fw, wh // fh))
            return fw * k, fh * k
        s = min(ww / fw, wh / fh)
        return max(1, int(fw * s)), max(1, int(fh * s))

    def _surface(self, pg, f: Frame):
        # little-endian 0x00RRGGBB in memory is B,G,R,X
        return pg.image.frombuffer(f.pixels, (f.width, f.height), "BGRA").convert()

    def _shot(self, pg, surf):
        if self.screenshot:
            pg.image.save(surf, self.screenshot)

    # -- main loop -----------------------------------------------------------
    def run(self) -> int:
        if self.headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame as pg
        pg.init()
        flags = pg.RESIZABLE if not self.headless else 0
        screen = pg.display.set_mode(self.window, flags)
        pg.display.set_caption(self.title)
        font = pg.font.Font(None, 22)
        clock = pg.time.Clock()
        t0 = time.monotonic(); shown_t = t0; shown_n = 0; fps_disp = 0.0; src_fps = 0.0; src_n0 = 0
        last_surf = None
        running = True
        try:
            self.transport.open()
            while running:
                for ev in pg.event.get():
                    if ev.type == pg.QUIT:
                        running = False
                    elif ev.type == pg.KEYDOWN:
                        if ev.key == pg.K_ESCAPE:
                            running = False
                        elif ev.key == pg.K_f:
                            self.fullscreen = not self.fullscreen
                            screen = pg.display.set_mode((0, 0) if self.fullscreen else self.window,
                                                         pg.FULLSCREEN if self.fullscreen else pg.RESIZABLE)
                        elif ev.key == pg.K_s and last_surf is not None:
                            pg.image.save(last_surf, time.strftime("retroview-%Y%m%d-%H%M%S.png"))
                        elif ev.key == pg.K_n:
                            self.filter = "linear" if self.filter == "nearest" else "nearest"
                        elif ev.key == pg.K_i:
                            self.scale_mode = "aspect" if self.scale_mode == "integer" else "integer"
                    elif ev.type == pg.VIDEORESIZE and not self.fullscreen:
                        self.window = (ev.w, ev.h)

                # drain what the transport has, keep only the newest complete frame
                newest = None
                for _ in range(64):
                    d = self.transport.read()
                    if not d:
                        break
                    self.parser.feed(d)
                    for f in self.parser.frames():
                        newest = f
                        for sink in self.sinks:
                            sink.add(pg, f)
                if newest is not None:
                    self._last = newest
                    last_surf = self._surface(pg, newest)
                    self.rendered += 1
                    shown_n += 1

                # draw
                screen.fill((0, 0, 0))
                if last_surf is not None:
                    ww, wh = screen.get_size()
                    tw, th = self._fit(last_surf.get_width(), last_surf.get_height(), ww, wh)
                    scaled = (pg.transform.smoothscale if self.filter == "linear" else pg.transform.scale)(last_surf, (tw, th))
                    screen.blit(scaled, ((ww - tw) // 2, (wh - th) // 2))
                now = time.monotonic()
                if now - shown_t >= 0.5:
                    fps_disp = shown_n / (now - shown_t); shown_n = 0
                    src_fps = (self.parser.stats.frames - src_n0) / (now - shown_t); src_n0 = self.parser.stats.frames
                    shown_t = now
                st, ts = self.parser.stats, self.transport.stats
                info = (f"{self._last.width}x{self._last.height} #{self._last.number}  " if self._last else "no signal  ") + \
                       f"shown {fps_disp:4.1f}/s  src {src_fps:4.1f}/s  dropped {st.dropped}  resync {st.resyncs}  " \
                       f"{ts.bytes/1e6:.1f} MB  {self.scale_mode}/{self.filter}"
                screen.blit(font.render(info, True, (255, 255, 0), (0, 0, 0)), (4, 4))
                pg.display.flip()
                clock.tick(240)
                if self.max_frames and self.rendered >= self.max_frames:
                    running = False
                if newest is None and self.transport.eof:
                    running = False                  # a replay ran out
        finally:
            if last_surf is not None:
                self._shot(pg, last_surf)
            for sink in self.sinks:
                out = sink.close(pg) if isinstance(sink, ShotSink) else sink.close()
                if out:
                    print(f"retroview: wrote {out}")
            self.transport.close()
            pg.quit()
        return 0 if self.rendered or not self.max_frames else 1
