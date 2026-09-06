#!/usr/bin/env python3
"""Make hps_io.sv acceptable to xvlog, which insists on declaration before use
(Vivado synthesis does not).  For the hps_io module only: hoist DW/AW/VD into
the parameter list, and move every module-scope `reg`/`wire` declaration up to
just after the header; a `wire x = expr;` becomes a declaration up top and an
`assign` in place.  Simulation copy only; the synthesised file is untouched."""
import re, sys
src, dst = sys.argv[1], sys.argv[2]
lines = open(src).read().split("\n")
out, decls, params, in_hps, hoisted = [], [], [], False, False
decl = re.compile(r"^(wire|reg)\b([^=;]*?)(\s*=\s*(.*))?;\s*$")
for ln in lines:
    if ln.startswith("module "):          # every module in the file gets the treatment
        in_hps, hoisted, decls, params = True, False, [], []
        if ln.startswith("module hps_io"):
            ln = ln.replace("PS2WE=0)", "PS2WE=0, DW=(WIDE)?15:7, AW=(WIDE)?12:13, VD=VDNUM-1)")
    if in_hps and ln.startswith("endmodule"):
        in_hps = False
        out = [("\n".join(params + decls) if x == "__DECLS__" else x) for x in out]
    if in_hps:
        if re.match(r"^localparam (DW|AW|VD) = ", ln):
            continue
        if ln.startswith("localparam ") and ln.rstrip().endswith(";") and "NOT_XILINX" not in ln:
            params.append(ln)            # localparams first, in their own order
            continue
        m = decl.match(ln)
        if m:
            kind, body, init = m.group(1), m.group(2), m.group(4)
            if init is not None and kind == "wire":
                name = body.split()[-1]
                decls.append(f"{kind}{body};")
                out.append(f"assign {name} = {init};")
            else:
                decls.append(ln)
            continue
        if not hoisted and ln.startswith(");"):      # end of the port list
            out.append(ln); out.append("/* declarations hoisted by hoist.py */"); out.append("__DECLS__"); hoisted = True
            continue
    out.append(ln)
text = "\n".join(out)
open(dst, "w").write(text)
print("hoisted declarations in every module")
