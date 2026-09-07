#!/usr/bin/env python3
"""Reg-ify declarations Vivado rejects, in ANY of a core's files, from the fit log.

    tools/patch-regs.py <MiSTeX-ports dir> <core> <fit.log>

For every `[Synth 8-2577] procedural assignment to a non-register NAME ...
[<file>:<line>]` the file is copied into overlay/cores/<core>/<path under
upstream/>, the declaration of NAME (`output [..] NAME`, `wire [..] NAME`,
`wire a, NAME;`) becomes `output reg` / `reg`, and MiSTeX.yaml gets the
upstream file under quartus: (excluded) and the copy under vivado:. Same idea
as patch-top.py, which only handles the top. Prints what it did; exit 1 if it
found nothing to patch (the loop should stop and a human look).
"""
import re, sys, os, shutil
from os.path import join, exists, dirname, abspath, relpath

ports, core, log = sys.argv[1:4]
ovl = abspath(join(dirname(abspath(__file__)), "..", "overlay", "cores", core))
coredir = join(abspath(ports), "cores", core)
hits = {}
for m in re.finditer(r"non-register (\w+) is not permitted.*?\[([^\]:]+):(\d+)\]", open(log).read()):
    hits.setdefault(m.group(2), set()).add(m.group(1))
if not hits:
    print("nothing to patch"); sys.exit(1)
yaml_p = join(ovl, "MiSTeX.yaml"); y = open(yaml_p).read()
for path, names in hits.items():
    # fit.log paths are absolute: under the core dir (upstream or MiSTeX copy) or the overlay
    path = abspath(path)
    if path.startswith(ovl + "/"):
        rel_in_core = relpath(path, ovl)
    elif path.startswith(coredir + "/"):
        rel_in_core = relpath(path, coredir)
    else:
        print(f"{path}: outside the core, not patched"); continue
    if not rel_in_core.startswith("upstream/"):
        # already a patched copy (in the core dir or overlay): patch it in place
        src = join(ovl, rel_in_core) if exists(join(ovl, rel_in_core)) else join(coredir, rel_in_core)
        dst = src
    else:
        src = join(coredir, rel_in_core)
        rel_out = rel_in_core[len("upstream/"):]
        dst = join(ovl, rel_out)
        if not exists(dst):
            os.makedirs(dirname(dst), exist_ok=True); shutil.copy(src, dst)
        # the top (no directory part) is found by mainfile resolution; listing it under
        # vivado: would exclude every file with the same basename by suffix match
        if "/" in rel_out and f"- {rel_out}\n" not in y:
            y = y.replace("quartus:\n  sourcefiles:\n", f"quartus:\n  sourcefiles:\n    - {rel_in_core}\n", 1)
            y = y.replace("vivado:\n  sourcefiles:\n",  f"vivado:\n  sourcefiles:\n    - {rel_out}\n", 1)
    text = open(dst).read(); done = []
    for n in sorted(names):
        t, c = re.subn(r"^(\s*output\s+)(?!reg\b)((?:\[[^\]]+\]\s*)?)(%s\b)" % n, r"\1reg \2\3", text, count=1, flags=re.M)
        if not c: t, c = re.subn(r"^(\s*)wire(\s+(?:\[[^\]]+\]\s*)?)(%s\b)" % n, r"\1reg\2\3", text, count=1, flags=re.M)
        if not c: t, c = re.subn(r"^(\s*)wire(\s+(?:\[[^\]]+\]\s*)?)([\w\s,]*\b%s\b)" % n, r"\1reg\2\3", text, count=1, flags=re.M)
        if c: text = t; done.append(n)
    if done:
        if not text.startswith("// Patched copy"):
            text = "// Patched copy for Vivado (tools/patch-regs.py): declarations written from always blocks\n// made reg; no functional change. Upstream: %s\n" % rel_in_core + text
        open(dst, "w").write(text)
    print(f"{relpath(dst, ovl)}: reg-ified {done}; unresolved {sorted(names - set(done))}")
open(yaml_p, "w").write(y)
