#!/usr/bin/env python3
"""Make a core's top synthesise under Vivado without changing what it does.

    tools/patch-top.py <MiSTeX-ports dir> <core> <fit.log> [--defines A,B]

Quartus accepts procedural assignments to nets that were declared without
`reg` (`output [7:0] USER_OUT` written from an always block, `wire px_addr`
likewise). Vivado does not. MiSTeX's convention is a patched copy of the top,
cores/<core>/<core>.sv, with those declarations fixed -- that is what this
does, driven by the errors Vivado actually reported, into the overlay at
overlay/cores/<core>/<core>.sv. Re-run after each fit until the log is clean.
"""
import re, sys, os
from os.path import join, exists, dirname, abspath

ports, core, log = sys.argv[1:4]
defs = []
if "--defines" in sys.argv:
    defs = sys.argv[sys.argv.index("--defines") + 1].split(",")
ovl = join(dirname(abspath(__file__)), "..", "overlay", "cores", core)
dst = join(ovl, f"{core}.sv")
src = dst if exists(dst) else join(ports, "cores", core, "upstream", f"{core}.sv")
text = open(src).read()
names = set(re.findall(r"non-register (\w+) is not permitted", open(log).read()))
if not names:
    print("nothing to patch"); sys.exit(0)
fixed, missed = [], []
for n in sorted(names):
    # port declarations: output [w] NAME / output NAME
    pat_port = re.compile(r"^(\s*output)(\s+)(?!reg\b)((?:\[[^\]]+\]\s*)?)(%s)\b" % re.escape(n), re.M)
    # net declarations: wire [w] NAME ; (no initialiser)
    pat_wire = re.compile(r"^(\s*)wire(\s+)((?:\[[^\]]+\]\s*)?)(%s)\s*(,|;)" % re.escape(n), re.M)
    # comma lists: wire [w] a, NAME, c;  -> the whole list becomes reg (all of them are
    # written procedurally in every case seen so far; a mixed list would fail loudly).
    pat_list = re.compile(r"^(\s*)wire(\s+(?:\[[^\]]+\]\s*)?)([^;=]*\b%s\b[^;=]*);" % re.escape(n), re.M)
    t2, k = pat_port.subn(lambda m: f"{m.group(1)} reg{m.group(2)}{m.group(3)}{m.group(4)}", text)
    if k == 0:
        t2, k = pat_wire.subn(lambda m: f"{m.group(1)}reg{m.group(2)}{m.group(3)}{m.group(4)}{m.group(5)}", text)
    if k == 0:
        t2, k = pat_list.subn(lambda m: f"{m.group(1)}reg{m.group(2)}{m.group(3)};", text)
    (fixed if k else missed).append(n)
    text = t2
# Ports declared through sys/emu_ports.vh (newer MiSTer framework): patch a copy of that too.
if missed and 'include "sys/emu_ports.vh"' in text:
    up = join(ports, "cores", core, "upstream", "sys", "emu_ports.vh")
    inc_dst = join(ovl, "sys", "emu_ports.vh")
    inc = open(inc_dst if exists(inc_dst) else up).read()
    still = []
    for n in missed:
        pat = re.compile(r"^(\s*output)(\s+)(?!reg\b)((?:\[[^\]]+\]\s*)?)(%s)\b" % re.escape(n), re.M)
        inc, k = pat.subn(lambda m: f"{m.group(1)} reg{m.group(2)}{m.group(3)}{m.group(4)}", inc)
        (fixed if k else still).append(n)
    missed = still
    os.makedirs(dirname(inc_dst), exist_ok=True)
    open(inc_dst, "w").write(inc)
os.makedirs(ovl, exist_ok=True)
open(dst, "w").write(text)
print(f"{core}: reg-ified {fixed}; unresolved {missed} -> {dst}")
if missed: sys.exit(2)
