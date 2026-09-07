import argparse, sys
from .transport import open_transport, Recorder
from .viewer import Viewer
from .capture import ShotSink, MjpegAvi


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
    ap.add_argument("--timeout", type=float, default=0, metavar="SEC", help="exit 1 if no frame arrives for this long (0 = wait forever)")
    cap = ap.add_argument_group("capture (every parsed frame, window or headless)")
    cap.add_argument("--shots", metavar="DIR", help="save every Nth frame as DIR/frame-<number>.png")
    cap.add_argument("--shot-every", type=int, default=60, metavar="N", help="with --shots: interval in frames (default 60)")
    cap.add_argument("--contact", metavar="PNG", help="with --shots: tile the saved frames into one PNG on exit")
    cap.add_argument("--contact-cols", type=int, default=6)
    cap.add_argument("--video", metavar="AVI", help="record every frame as an MJPEG AVI (opens in any player)")
    cap.add_argument("--video-fps", type=float, default=0, help="frame rate written in the AVI header (default: --fps for synth, else 60)")
    cap.add_argument("--video-every", type=int, default=1, metavar="N", help="with --video: keep every Nth frame")
    cap.add_argument("--video-quality", type=int, default=90)
    a = ap.parse_args(argv)

    if a.transport == "file" and not a.file:
        ap.error("--transport file needs --file")
    t = open_transport(a.transport, device=a.device, path=a.file, loop=a.loop,
                       width=a.size[0], height=a.size[1], fps=a.fps,
                       mode_change_every=a.synth_mode_change, drop_every=a.synth_drop)
    if a.record:
        t = Recorder(t, a.record)
    sinks = []
    if a.shots:
        sinks.append(ShotSink(a.shots, every=a.shot_every, contact=a.contact, contact_cols=a.contact_cols))
    elif a.contact:
        ap.error("--contact needs --shots")
    if a.video:
        fps = a.video_fps or (a.fps if a.transport == "synth" else 60.0)
        sinks.append(MjpegAvi(a.video, fps=fps, quality=a.video_quality, every=a.video_every))
    v = Viewer(t, window=a.window, scale=a.scale, filt=a.filter, headless=a.headless,
               max_frames=a.frames, screenshot=a.screenshot, sinks=sinks, timeout=a.timeout)
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
