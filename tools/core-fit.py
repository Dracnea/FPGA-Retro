#!/usr/bin/env python3
"""Out-of-context synthesis of a MiSTer core's `emu` module on an UltraScale+ part.

    tools/core-fit.py <MiSTeX-ports dir> <core> <part> [--build-dir DIR] [--no-run]

Answers the first question about any core on these cards -- does it fit, what
does it cost, does it close timing at its own clocks -- without a board target,
a video sink or a host interface. It resolves the core's source list exactly as
MiSTeX's util.add_designfiles does (sourcedirs scanned, quartus-listed files
excluded, vivado-listed replacements added), with three changes:

  * `-xilinx7` replacements are swapped for `-xilinxusp` ones when the overlay
    has them (the MMCME4 PLL shims);
  * overlay/rtl/altera_compat is added, so files that instantiate Intel
    megafunctions synthesise as-is;
  * the `sys` directory contributes only what `emu` needs (hps_io and friends);
    sys_top and the Altera PLL/HDMI blocks are the board target's business.

Output: <build-dir>/fit.log, utilization.rpt, timing.rpt, and a one-line
summary on stdout. Nothing here touches a board.
"""
import argparse, glob, os, re, subprocess, sys
from os.path import abspath, basename, dirname, exists, join

import yaml

HERE = dirname(abspath(__file__))
OVERLAY = join(HERE, "..", "overlay")

# sys/ files that belong to sys_top (board side) or are Altera IP, never to emu.
SYS_SKIP = {
    # sys_top's own blocks and the Altera / Series-7 IP behind them. Everything
    # else in sys/ (hps_io, video_mixer, video_freak, hq2x, sd_card, ...) is
    # instantiated from inside emu and must be in the list.
    "sys_top.v", "top_crg.v", "sysmem.sv", "pll_cfg.v",
    "altera_pll_reconfig_core.v", "altera_pll_reconfig_top.v",
    "pll_hdmi_0002.v", "pll_audio_0002.v", "pll_hdmi.v", "pll_audio.v",
    "pll_hdmi_0002-xilinx7.v", "pll_audio_0002-xilinx7.v", "pll_hdmi_adj.vhd",
    "xilinx7_mmcm_reconfig.v", "xilinx_pll_reconfig_top.v",
    "hdmi_config.sv", "ascal.vhd", "alsa.sv", "i2s.v", "spdif.v", "audio_out.v",
    "hdmi_lite.sv", "osd.v", "ltc2308.sv", "mcp23009.sv",
    "mt32pi.sv", "iir_filter.v",     "vip_config.sv", "f2sdram_safe_terminator.sv", "ddr_svc.sv", "yc_out.sv",
    "vga_out.sv", "i2c.v", "hps_interface.v",
}
HDL = (".v", ".sv", ".vhd")
# .v files that only parse under SystemVerilog rules (declarations in unnamed blocks).
SV_AS_V = {"hps_ext.v"}

def convert_mif(mif, dest):
    """MIF -> one hex word per line, the layout MiSTeX's dpram/spram replacements read."""
    width, depth, radix, out = 8, 0, 16, []
    with open(mif) as f:
        lines = [l for l in f if not l.startswith("--")]
    content = False
    for line in lines:
        s = line.strip()
        if s.startswith("WIDTH"): width = int(re.sub(r"[^0-9]", "", s.split("=")[1]))
        elif s.startswith("DEPTH"): depth = int(re.sub(r"[^0-9]", "", s.split("=")[1]))
        elif s.startswith("DATA_RADIX"): radix = 2 if "BIN" in s else 16
        elif s.startswith("CONTENT BEGIN"): content = True
        elif s.startswith("END") or not content or not s: continue
        else:
            parts = [p for p in s.replace(";", "").replace(":", " ").split() if p]
            addr, vals = parts[0], parts[1:]
            fmt = "{:0%dX}" % ((width + 3) // 4)
            if addr.startswith("["):
                a, b = [int(x, 16) for x in addr[1:-1].split("..")]
                out += [fmt.format(int(vals[0], radix))] * (b - a + 1)
            else:
                out += [fmt.format(int(v, radix)) for v in vals]
    assert len(out) == depth, f"{mif}: {len(out)} words, DEPTH {depth}"
    os.makedirs(dirname(dest), exist_ok=True)
    with open(dest, "w") as f:
        f.write("\n".join(out) + "\n")
    with open(dest[:-4] + ".mem", "w") as f:
        f.write("\n".join(out) + "\n")

def resolve(ports, core, build_dir):
    coredir = join(ports, "cores", core)
    ovl = join(OVERLAY, "cores", core)
    y = None
    for cand in (join(ovl, "MiSTeX.yaml"), join(coredir, "MiSTeX.yaml")):
        if exists(cand):
            y = yaml.safe_load(open(cand)); break
    if y is None:
        sys.exit(f"no MiSTeX.yaml for {core} in the overlay or in {coredir}")
    use_tmpl = y.get("use-template-sys", False)
    excludes = set(y["quartus"]["sourcefiles"]) | set(y["vivado"]["sourcefiles"])
    files, mifs = [], []

    def add(p):
        if p.endswith(".mif"): mifs.append(p)
        elif p.endswith(HDL): files.append(p)

    for sd in y["sourcedirs"]:
        if sd == "sys":
            base = join(ports, "cores", "Template", "sys") if use_tmpl else join(coredir, "sys")
            for fn in sorted(os.listdir(base)):
                if fn in SYS_SKIP or not fn.endswith(HDL): continue
                files.append(join(base, fn))
            continue
        base = join(coredir, sd)
        for fn in sorted(os.listdir(base)):
            p = join(base, fn)
            if any(p.endswith(e) for e in excludes): continue
            add(p)
    for s in y.get("sourcefiles", []): add(join(coredir, s))
    for s in y["vivado"]["sourcefiles"]:
        if s.startswith("sys/"): continue
        # Prefer an UltraScale+ shim from the overlay over the Series-7 one.
        cand = s.replace("-xilinx7", "-xilinxusp")
        for root in (ovl, coredir):
            if exists(join(root, cand)): files.append(join(root, cand)); break
            if exists(join(root, s)):    files.append(join(root, s));    break
        else:
            print(f"warning: {s} not found in overlay or core", file=sys.stderr)
    # Compat cells last: user modules named like Intel megafunctions.
    cdir = join(OVERLAY, "rtl", "altera_compat")
    files += [join(cdir, f) for f in sorted(os.listdir(cdir)) if f.endswith(HDL)]
    # The top, in order of preference: the overlay's patched copy (tools/patch-top.py
    # writes it there), MiSTeX's patched copy in the core dir, else upstream's own.
    main = y["mainfile"]
    for top in (join(ovl, main), join(coredir, main), join(coredir, "upstream", main)):
        if exists(top): break
    files.append(top)
    # MIF init files land where the VHDL replacements expect them: relative to cwd.
    for m in mifs:
        rel = m.replace(coredir + "/", "").replace("upstream/", "")
        convert_mif(m, join(build_dir, rel))
    defines = y.get("defines", {}) or {}
    # .v files a core writes in SystemVerilog (per-core `sv-as-v:` list in the yaml).
    sv_as_v = SV_AS_V | set(y.get("sv-as-v", []) or [])
    # Quartus projects compile some VHDL into named libraries (`entity mem.dpram`):
    # read the same assignments from the .qsf so Vivado sees the same libraries.
    libs = {}
    for qsf in glob.glob(join(coredir, "upstream", "*.qsf")) + glob.glob(join(coredir, "upstream", "*.qip")):
        for m in re.finditer(r"VHDL_FILE\s+(\S+)\s+-library\s+(\w+)", open(qsf).read()):
            libs[basename(m.group(1))] = m.group(2)
    # The Peip cores reference `entity mem.X`: everything rtl/mem.qip lists is library mem.
    memqip = join(coredir, "upstream", "rtl", "mem.qip")
    if exists(memqip):
        for m in re.finditer(r"VHDL_FILE\s+\[file join \$::quartus\(qip_path\)\s+\"?([\w.]+)\"?\s*\]", open(memqip).read()):
            libs.setdefault(m.group(1), "mem")
    vhdl_std = str(y.get("vhdl", "2008"))
    # Quartus folds every design library into `work`, so `entity mem.dpram` works there
    # for a file with no library assignment at all. Vivado does not: a core whose
    # yaml says `vhdl-library: mem` gets ALL its VHDL compiled into that library
    # (where `work` then means the same thing), which reproduces Quartus's behaviour.
    if y.get("vhdl-library"):
        for f in files:
            if f.endswith(".vhd") and "altera_compat" not in f:
                libs[basename(f)] = y["vhdl-library"]
    return files, defines, main, libs, vhdl_std, sv_as_v

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ports"); ap.add_argument("core"); ap.add_argument("part")
    ap.add_argument("--build-dir"); ap.add_argument("--no-run", action="store_true")
    ap.add_argument("--clk50-port", default="CLK_50M")
    ap.add_argument("--threads", type=int, default=16)
    a = ap.parse_args()
    ports = abspath(a.ports)
    part_short = a.part.split("-")[0]
    bdir = abspath(a.build_dir or join("build", f"fit_{a.core}_{part_short}"))
    os.makedirs(bdir, exist_ok=True)
    files, defines, main, libs, vhdl_std, sv_as_v = resolve(ports, a.core, bdir)
    # build_id stubs -- the tops `include one of these two names.
    for n in ("build_id.v", "build_id.vh"):
        with open(join(bdir, n), "w") as f:
            f.write('`define BUILD_DATE "260905"\n`define BUILD_TIME "000000"\n')
    # Include search: the overlay core dir first (a patched sys/emu_ports.vh lives
    # there), then the core's upstream dir (its own sys/), then every source dir.
    ovl_core = join(OVERLAY, "cores", a.core)
    incs = [ovl_core, join(ports, "cores", a.core, "upstream"), bdir] + sorted({dirname(f) for f in files})
    with open(join(bdir, "fit.tcl"), "w") as t:
        t.write(f"set_param general.maxThreads {a.threads}\n")
        t.write("create_project -in_memory -part %s\n" % a.part)
        t.write("set_property target_language Verilog [current_project]\n")
        for f in files:
            # The two component packages go into the libraries the cores name.
            if f.endswith("altera_mf_components.vhd"): t.write(f"read_vhdl -library altera_mf {{{f}}}\n")
            elif f.endswith("lpm_components.vhd"):     t.write(f"read_vhdl -library lpm {{{f}}}\n")
            # VHDL-2008 by default (the N64 reads its out ports); a core whose yaml
            # says `vhdl: 93` gets 1993 rules (GBA names a record field `default`).
            # Files the .qsf compiles into a named library keep that library.
            elif f.endswith(".vhd"):
                lib = f" -library {libs[basename(f)]}" if basename(f) in libs else ""
                std = "" if vhdl_std == "93" else " -vhdl2008"
                t.write(f"read_vhdl{std}{lib} {{{f}}}\n")
            # .v is Verilog-2001 -- SNES's main.v uses `do` as a net name -- except
            # the few Quartus-era files that need SystemVerilog rules.
            elif f.endswith(".sv") or basename(f) in sv_as_v: t.write(f"read_verilog -sv {{{f}}}\n")
            else: t.write(f"read_verilog {{{f}}}\n")
        t.write("set_property include_dirs {%s} [current_fileset]\n" % " ".join(incs))
        if defines:
            t.write("set_property verilog_define {%s} [current_fileset]\n" % " ".join(f"{k}={v}" for k, v in defines.items()))
        t.write(f"synth_design -top emu -part {a.part} -mode out_of_context -flatten_hierarchy rebuilt "
                f"-include_dirs {{{' '.join(incs)}}} "
                + (" ".join(f"-verilog_define {k}={v}" for k, v in defines.items())) + "\n")
        t.write(f"create_clock -period 20.000 -name clk50 [get_ports {a.clk50_port}]\n")
        t.write("report_utilization -file utilization.rpt\n")
        t.write("report_utilization -hierarchical -hierarchical_depth 2 -file utilization_hier.rpt\n")
        t.write("report_timing_summary -max_paths 5 -file timing.rpt\n")
        t.write("report_clocks -file clocks.rpt\n")
        t.write("write_checkpoint -force synth.dcp\n")
        t.write("exit\n")
    print(f"{len(files)} sources -> {bdir}/fit.tcl")
    if a.no_run: return
    with open(join(bdir, "fit.log"), "w") as log:
        r = subprocess.run(["vivado", "-mode", "batch", "-nojournal", "-nolog", "-notrace", "-source", "fit.tcl"],
                           cwd=bdir, stdout=log, stderr=subprocess.STDOUT)
    summarize(bdir, r.returncode)

def summarize(bdir, rc):
    u = open(join(bdir, "utilization.rpt")).read() if exists(join(bdir, "utilization.rpt")) else ""
    def row(name):
        m = re.search(r"\|\s*%s\*?\s*\|\s*([0-9.]+)\s*\|\s*[0-9]+\s*\|\s*[0-9]*\s*\|\s*([0-9]+)\s*\|\s*([0-9.]+)" % re.escape(name), u)
        return f"{name} {m.group(1)}/{m.group(2)} ({m.group(3)}%)" if m else f"{name} ?"
    tim = open(join(bdir, "timing.rpt")).read() if exists(join(bdir, "timing.rpt")) else ""
    wns = re.search(r"WNS\(ns\).*?\n.*?\n\s*(-?[0-9.]+)", tim)
    log = open(join(bdir, "fit.log")).read()
    bbox = re.findall(r"black-box|Cannot find module|has not been elaborated|ERROR:", log)
    print(f"rc={rc}  {row('CLB LUTs')}  {row('CLB Registers')}  {row('Block RAM Tile')}  {row('URAM')}  {row('DSPs')}  "
          f"WNS={wns.group(1) if wns else '?'}  issues={len(bbox)}")

if __name__ == "__main__":
    main()
