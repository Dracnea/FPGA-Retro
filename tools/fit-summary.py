#!/usr/bin/env python3
"""Summarise build/fit_<core>_<part>/ results from tools/core-fit.py as a Markdown table.

    tools/fit-summary.py [build-dir]

One row per (core, part): LUTs, registers, BRAM tiles, URAM, DSPs with device
percentages, the slowest post-synthesis clock and its worst setup slack, and
whether the run was clean. Reads only what Vivado wrote; prints nothing it
cannot find.
"""
import glob, os, re, sys
from os.path import basename, exists, join

bdir = sys.argv[1] if len(sys.argv) > 1 else "build"
rows = []
for d in sorted(glob.glob(join(bdir, "fit_*_*"))):
    if not os.path.isdir(d): continue
    core, part = basename(d)[4:].rsplit("_", 1)
    u = open(join(d, "utilization.rpt")).read() if exists(join(d, "utilization.rpt")) else ""
    def cell(name):
        m = re.search(r"\|\s*%s\*?\s*\|\s*([0-9.]+)\s*\|\s*[0-9]+\s*\|\s*[0-9]*\s*\|\s*([0-9]+)\s*\|\s*([0-9.]+)" % re.escape(name), u)
        return f"{float(m.group(1)):g} ({m.group(3)} %)" if m else "—"
    t = open(join(d, "timing.rpt")).read() if exists(join(d, "timing.rpt")) else ""
    # Intra-clock table: name, WNS, TNS, fail, total ...
    clocks = re.findall(r"^\s*(clkout\d|clk50)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(\d+)\s+(\d+)", t, re.M)
    c = open(join(d, "clocks.rpt")).read() if exists(join(d, "clocks.rpt")) else ""
    periods = dict(re.findall(r"^(clkout\d|clk50)\s+([0-9.]+)", c, re.M))
    # The tightest clock is the one with the least slack *relative to its period*,
    # among clocks that actually time something (clk50 reaches one register).
    real = [x for x in clocks if int(x[4]) >= 10 and x[0] in periods]
    worst = min(real, key=lambda x: float(x[1]) / float(periods[x[0]])) if real else None
    if worst:
        per = float(periods[worst[0]]); slack = float(worst[1])
        timing = f"{1000/per:.1f} MHz clock: WNS {slack:+.2f} ns (fmax ≈ {1000/(per-slack):.0f} MHz)"
    else:
        timing = "—"
    log = open(join(d, "fit.log")).read() if exists(join(d, "fit.log")) else ""
    ok = "rc=0" in (open(d + ".out").read() if exists(d + ".out") else "") and "ERROR" not in log
    bb = len(re.findall(r"Could not resolve non-primitive black box", log))
    rows.append((core, part, cell("CLB LUTs"), cell("CLB Registers"), cell("Block RAM Tile"), cell("URAM"), cell("DSPs"), timing, "clean" if ok else "FAILED", bb))
print("| core | part | CLB LUTs | registers | BRAM tiles | URAM | DSPs | slowest clock (post-synth) | result | black boxes |")
print("|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    print("| " + " | ".join(str(x) for x in r) + " |")
