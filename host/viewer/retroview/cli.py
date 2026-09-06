import argparse, sys
from .transport import open_transport, Recorder
from .viewer import Viewer


def size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="retroview", description="Show the frames an FPGA-Retro card streams to host RAM.")
    ap.add_argument("--transport", choices=["litepcie", "file", "synth", "windows"], default="litepcie")
    ap.add_argument("--device", default="/dev/litepcie0", help="litepcie: device node")
    ap.add_argument("--file", help="file: recorded stream to replay")
    ap.add_argument("--loop", action="store_true", help="file: replay forever")
    ap.add_argument("--size", type=size, default=(320, 240), help="synth: frame size WxH")
    ap.add_argument("--fps", type=float, default=60.0, help="synth: frame rate")
    ap.add_argument("--synth-mode-change", type=int, default=0, help="synth: switch size every N frames")
    ap.add_argument("--synth-drop", type=int, default=0, help="synth: drop every Nth frame")
    ap.add_argument("--window", type=size, default=(1280, 960))
    ap.add_argument("--scale", choices=["integer", "aspect"], default="integer")
    ap.add_argument("--filter", choices=["nearest", "linear"], default="nearest")
    ap.add_argument("--record", help="append the raw stream to this file for later replay")
    ap.add_argument("--headless", action="store_true", help="SDL dummy driver; with --frames and --screenshot for tests")
    ap.add_argument("--frames", type=int, default=0, help="exit after this many frames were shown")
    ap.add_argument("--screenshot", help="save the last frame here on exit")
    a = ap.parse_args(argv)

    if a.transport == "file" and not a.file:
        ap.error("--transport file needs --file")
    t = open_transport(a.transport, device=a.device, path=a.file, loop=a.loop,
                       width=a.size[0], height=a.size[1], fps=a.fps,
                       mode_change_every=a.synth_mode_change, drop_every=a.synth_drop)
    if a.record:
        t = Recorder(t, a.record)
    v = Viewer(t, window=a.window, scale=a.scale, filt=a.filter, headless=a.headless,
               max_frames=a.frames, screenshot=a.screenshot)
    try:
        rc = v.run()
    except NotImplementedError as e:
        print(f"retroview: {e}", file=sys.stderr); return 2
    except (OSError, RuntimeError) as e:
        print(f"retroview: {e}", file=sys.stderr); return 1
    st = v.parser.stats
    print(f"retroview: shown {v.rendered}, parsed {st.frames}, dropped {st.dropped}, resyncs {st.resyncs}, "
          f"discarded {st.discarded} B, bad headers {st.bad_headers}, transport {v.transport.stats.bytes} B in "
          f"{v.transport.stats.chunks} chunks")
    return rc


if __name__ == "__main__":
    sys.exit(main())
