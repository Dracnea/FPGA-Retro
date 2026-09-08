#!/usr/bin/env python3
"""Boot a real PS2 BIOS on the C1100's IOP and report where it gets to.

    tools/ps2iop/bios_run.py /path/to/rom0.bin [--seconds 5] [--build ~/MiSTeX-ports/build/c1100_ps2_diag]
                                              [--no-scope] [--out build/ps2_bios/<name>]

Needs the diagnostic PS2 image (c1100_ps2_diag: POST ring, stall detector,
bus analyzer) loaded and its driver bound, and litex_server on the UART for
the analyzer (tools/uart-probe.sh finds the tty; --no-scope skips it).

Sequence: arm the analyzer (trigger = stall flag, almost all samples before
the trigger), hold reset, stream the 4 MB image into the ROM, release reset,
poll the POST register for --seconds printing every change, then read the
POST ring (last 64 writes with IOP cycle stamps), the stall detector, and
if the analyzer triggered, the last bus transactions before the hang,
decoded as fetches / loads / stores with addresses and data.
"""
import argparse, os, sys, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.expanduser("~/MiSTeX-ports/venv/lib/python3.12/site-packages"))
import iop_post


def region(a):
    a &= 0x1FFFFFFF
    if a < 0x00200000: return "RAM"
    if 0x1FC00000 <= a < 0x20000000: return "ROM"
    if 0x1F801000 <= a < 0x1F801040: return "SSBUS"
    if 0x1F801040 <= a < 0x1F801060: return "SIO"
    if 0x1F801060 <= a < 0x1F801070: return "RAMSIZE"
    if 0x1F801070 <= a < 0x1F801080: return "INTC"
    if 0x1F801080 <= a < 0x1F801100: return "DMA"
    if 0x1F801100 <= a < 0x1F801140: return "TIMER"
    if 0x1F801400 <= a < 0x1F801480: return "SSBUS2"
    if 0x1F801480 <= a < 0x1F8014B0: return "TIMER32"
    if 0x1F801500 <= a < 0x1F801580: return "DMA2"
    if 0x1F801800 <= a < 0x1F801830: return "CDROM/SPU?"
    if 0x1F802000 <= a < 0x1F802080: return "EXP2/POST"
    if 0x1F808200 <= a < 0x1F808300: return "SIO2"
    if 0x1F900000 <= a < 0x1F900800: return "SPU2"
    if 0x1F402000 <= a < 0x1F402020: return "CDVD"
    if 0x1D000000 <= a < 0x1D000070: return "SIF"
    if a >= 0x1FFE0000: return "CACHECTL"
    return "UNMAPPED"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom")
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--build", default=os.path.expanduser("~/MiSTeX-ports/build/c1100_ps2_diag"))
    ap.add_argument("--dev", default="/dev/litepcie0")
    ap.add_argument("--port", type=int, default=1234)
    ap.add_argument("--no-scope", action="store_true")
    ap.add_argument("--pad0", type=lambda x: int(x, 0), default=0xFFFF)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    name = os.path.basename(a.rom).rsplit(".", 1)[0]
    out = a.out or os.path.join("build", "ps2_bios", f"{datetime.now():%Y%m%d-%H%M%S}-{name}")
    os.makedirs(out, exist_ok=True)
    log = open(os.path.join(out, "run.log"), "w")
    def say(*s):
        print(*s); print(*s, file=log); log.flush()

    csr = os.path.join(a.build, "csr.csv")
    dev = iop_post.Dev(a.dev, csr)
    say(f"== {datetime.now():%Y-%m-%d %H:%M:%S}  {a.rom}  ({os.path.getsize(a.rom)} bytes)  -> {out}")

    an = None
    if not a.no_scope:
        try:
            from litex import RemoteClient
            from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver
            wb = RemoteClient(csr_csv=csr, port=a.port); wb.open()
            an = LiteScopeAnalyzerDriver(wb.regs, "zanalyzer_iop", config_csv=os.path.join(a.build, "zanalyzer_iop.csv"), debug=False)
            an.configure_group(0); an.configure_subsampler(1)
            an.add_rising_edge_trigger([n for n, w in an.layouts[0] if "stall" in n][0])
            an.run(offset=an.depth - 64, length=an.depth)
            say("analyzer armed: trigger on the stall flag, pre-trigger history")
        except Exception as e:
            say(f"analyzer not armed ({e}); continuing without it")
            an = None

    # hold reset, load, release
    dev.wr("iop_reset", 1)
    dev.wr("iop_pad0", a.pad0)
    t0 = time.time()
    n = iop_post.load(dev, a.rom)
    say(f"ROM: {n} words in {time.time() - t0:.1f} s; rom_count {dev.rd('iop_rom_count')}")
    dev.wr("iop_reset", 0)
    t0 = time.time(); seen = None; last_count = -1
    while time.time() - t0 < a.seconds:
        s = iop_post.status(dev)
        if s["post"] != seen or s["post_count"] != last_count:
            seen = s["post"]; last_count = s["post_count"]
            say(f"[{time.time() - t0:7.3f}s] POST {seen:02X}  (count {s['post_count']}, cpu_error {s['cpu_error']})")
        time.sleep(0.002)
    s = iop_post.status(dev)
    say(f"after {a.seconds:g} s: POST {s['post']:02X} post_count {s['post_count']} cpu_error {s['cpu_error']} mem_idle {s['mem_idle']}")

    # POST ring
    cnt = dev.rd("zpost_count"); cyc = dev.rd("zpost_cycles")
    say(f"POST ring: {cnt} writes since reset; IOP cycles since reset {cyc} ({cyc / 36.875e6:.3f} s)")
    n_show = min(cnt, 64)
    for i in range(n_show):
        dev.wr("zpost_addr", i)
        c = dev.rd("zpost_code"); t = dev.rd("zpost_time")
        say(f"   #{i:2d}  POST {c:02X}  at cycle {t:10d}  ({t / 36.875e6 * 1e3:9.3f} ms)")
    say(f"stall: idle_cycles {dev.rd('zstall_idle_cycles')}  stalled {dev.rd('zstall_stalled')}")

    # the IOP's serial console (Kprintf), captured in hardware
    text = bytearray()
    while dev.rd("zcon_level") and len(text) < 65536:
        text.append(dev.rd("zcon_data") & 0xFF)
        dev.wr("zcon_pop", 1)
    say(f"console: {len(text)} bytes" + ("  (FIFO overflowed, bytes lost)" if dev.rd("zcon_overflow") else ""))
    if text:
        say("---- console ----")
        for line in text.decode("latin-1").splitlines():
            say("  | " + line)
        say("---- end ----")
        open(os.path.join(out, "console.txt"), "wb").write(bytes(text))

    if an is not None:
        t1 = time.time()
        while not an.done() and time.time() - t1 < 3:
            time.sleep(0.05)
        if not an.done():
            say("analyzer: not triggered (the CPU kept issuing bus requests); forcing a capture of the current activity")
            wb2 = an  # re-arm with an immediate trigger
            an.add_trigger(cond={[n for n, w in an.layouts[0] if "reset" in n][0]: "0b0"})
            an.run(offset=8, length=an.depth); time.sleep(0.5)
        if an.done():
            an.upload()
            an.save(os.path.join(out, "trace.csv")); an.save(os.path.join(out, "trace.vcd"))
            sys.path.insert(0, os.path.join(HERE, ".."))
            names, data = load_csv(os.path.join(out, "trace.csv"))
            decode(names, data, say)
        wb.close()
    say(f"done; files in {out}")


def load_csv(path):
    with open(path) as f:
        lines = [l.rstrip("\n") for l in f]
    names = [n for n in lines[0].split(",") if n]
    data = []
    for l in lines[2:]:
        vals = [v.strip() for v in l.split(",")][:len(names)]
        if len(vals) == len(names):
            data.append([int(v, 2) if v and v != "x" else 0 for v in vals])
    return names, data


def col(names, needle):
    for i, n in enumerate(names):
        if needle in n:
            return i
    return None


def decode(names, data, say):
    req = col(names, "dbg_req"); rnw = col(names, "dbg_rnw"); isd = col(names, "dbg_isdata"); done = col(names, "dbg_done")
    ai = col(names, "addr_instr"); ad = col(names, "addr_data"); wd = col(names, "dbg_wdata"); rd = col(names, "dbg_rdata")
    wm = col(names, "dbg_wmask"); pw = col(names, "post_wr"); pc = col(names, "post_code"); ce = col(names, "cpu_error"); st = col(names, "stall")
    say(f"trace: {len(data)} samples")
    events = []
    pending = None
    for i, s in enumerate(data):
        if s[req]:
            if s[isd]:
                a = s[ad]; kind = "ST" if not s[rnw] else "LD"
                pending = (i, kind, a, s[wd] if kind == "ST" else None, s[wm])
            else:
                pending = (i, "IF", s[ai], None, 0)
        if s[done] and pending:
            i0, kind, a, w, m = pending
            v = w if kind == "ST" else s[rd]
            events.append((i0, kind, a, v, m)); pending = None
        if s[pw]:
            events.append((i, "POST", s[pc], None, 0))
        if s[ce]:
            events.append((i, "CPU_ERROR", 0, None, 0)); break
    say(f"  {len(events)} bus events; last 120:")
    for i, kind, a, v, m in events[-120:]:
        if kind == "POST":
            say(f"    [{i:5d}] POST {a:02X}")
        elif kind == "CPU_ERROR":
            say(f"    [{i:5d}] CPU ERROR")
        else:
            say(f"    [{i:5d}] {kind} {a:08x} {region(a):9s} " + (f"= {v:08x}" if v is not None else "") + (f" mask {m:x}" if kind == "ST" else ""))
    last = [e for e in events if e[1] in ("IF", "LD", "ST")]
    if last:
        i, kind, a, v, m = last[-1]
        say(f"  last bus access: {kind} at 0x{a:08x} ({region(a)}); stall flag {'set' if st is not None and data[-1][st] else 'clear'}")


if __name__ == "__main__":
    main()
