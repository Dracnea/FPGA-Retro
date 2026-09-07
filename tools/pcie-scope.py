#!/usr/bin/env python3
"""Capture what the C1100's PCIe endpoint does with one BAR0 read, over the UART.

Needs the diagnostic image (c1100_pcie_diag) on the card, litex_server running
on the FPGA UART (tools/uart-probe.sh finds the tty), and /dev/litepcie0 for the
read that triggers the capture.

    tools/pcie-scope.py --build ~/MiSTeX-ports/build/c1100_pcie_diag [--csr bitstreams/c1100_pcie_video_transport.csr.csv]

Arms both analyzers (pcie: trigger on the hard IP's CQ tvalid rising; sys: on
the wishbone master's cyc rising), performs one register read through the
litepcie driver, downloads both captures, and prints every valid beat with
the fields that matter: the CQ descriptor (address, type, dword count, BE,
requester/tag), the CC descriptor (status, byte count, data), and the
wishbone transaction. Dumps go to build/pcie_scope/<timestamp>/.
"""
import argparse, os, struct, subprocess, sys, time, fcntl
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/MiSTeX-ports/venv/lib/python3.12/site-packages"))
from litex import RemoteClient
from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver

LITEPCIE_IOCTL_REG = (3 << 30) | (12 << 16) | (ord("S") << 8) | 0


def pcie_read(dev, addr):
    fd = os.open(dev, os.O_RDWR)
    try:
        out = fcntl.ioctl(fd, LITEPCIE_IOCTL_REG, struct.pack("IIB3x", addr, 0, 0))
        return struct.unpack("IIB3x", out)[1]
    finally:
        os.close(fd)


def pcie_write(dev, addr, val):
    fd = os.open(dev, os.O_RDWR)
    try:
        fcntl.ioctl(fd, LITEPCIE_IOCTL_REG, struct.pack("IIB3x", addr, val & 0xFFFFFFFF, 1))
    finally:
        os.close(fd)


def load_csv(path):
    """litescope's CSVDump: line 1 signal names, line 2 widths, then one line per
    sample of binary strings separated by ', ' (trailing separators on every line)."""
    with open(path) as f:
        lines = [l.rstrip("\n") for l in f]
    names = [n for n in lines[0].split(",") if n]
    data = []
    for l in lines[2:]:
        vals = [v.strip() for v in l.split(",")][:len(names)]
        if len(vals) < len(names):
            continue
        data.append([int(v, 2) if v and v != "x" else 0 for v in vals])
    return names, data


def col(names, needle):
    for i, n in enumerate(names):
        if needle in n:
            return i
    return None


REQTYPE = {0: "MemRd", 1: "MemWr", 2: "IORd", 3: "IOWr", 4: "MemFetchAdd", 5: "MemUncondSwap", 6: "MemCAS",
           7: "LockedRd", 8: "CfgRd0", 9: "CfgRd1", 10: "CfgWr0", 11: "CfgWr1", 12: "Msg", 13: "VendorMsg",
           14: "ATSMsg", 15: "Reserved"}


def decode_pcie(names, data, out):
    v  = col(names, "m_axis_cq_tvalid");  r = col(names, "m_axis_cq_tready"); l = col(names, "m_axis_cq_tlast")
    d  = col(names, "m_axis_cq_tdata");   u = col(names, "m_axis_cq_tuser");  k = col(names, "m_axis_cq_tkeep")
    cv = col(names, "s_axis_cc_tvalid");  cr = col(names, "s_axis_cc_tready"); cl = col(names, "s_axis_cc_tlast")
    cd = col(names, "s_axis_cc_tdata");   ck = col(names, "s_axis_cc_tkeep")
    lnk = col(names, "link_status"); rst = col(names, "pcie_rst")
    print(f"pcie analyzer: {len(data)} samples; lnk_up={data[0][lnk] if lnk is not None else '?'} "
          f"pcie_rst={data[0][rst] if rst is not None else '?'} at sample 0", file=out)
    ncq = ncc = 0
    for i, s in enumerate(data):
        if v is not None and s[v] and (r is None or (s[r] & 1)):
            ncq += 1
            td = s[d]
            addr = (td & ((1 << 64) - 1)) & ~3
            dw2 = (td >> 64) & 0xFFFFFFFF; dw3 = (td >> 96) & 0xFFFFFFFF
            dwcnt = dw2 & 0x7FF; rtype = (dw2 >> 11) & 0xF; reqid = (dw2 >> 16) & 0xFFFF
            tag = dw3 & 0xFF; bar = (dw3 >> 16) & 7; ap = (dw3 >> 19) & 0x3F
            tu = s[u] if u is not None else 0
            print(f"  [{i:5d}] CQ  {REQTYPE.get(rtype, rtype):6s} addr=0x{addr:016x} dw={dwcnt} reqid=0x{reqid:04x} "
                  f"tag={tag} bar={bar} aperture={ap} first_be={tu & 0xF:x} last_be={(tu >> 4) & 0xF:x} "
                  f"sop={(tu >> 40) & 1} tlast={s[l]} tkeep=0x{s[k]:x}  data_dw4..={' '.join(f'{(td >> (32*j)) & 0xFFFFFFFF:08x}' for j in range(4))}", file=out)
        if cv is not None and s[cv] and (cr is None or (s[cr] & 1)):
            ncc += 1
            td = s[cd]
            dw0 = td & 0xFFFFFFFF; dw1 = (td >> 32) & 0xFFFFFFFF; dw2 = (td >> 64) & 0xFFFFFFFF; dw3 = (td >> 96) & 0xFFFFFFFF
            lowaddr = dw0 & 0x7F; bytecnt = (dw0 >> 16) & 0x1FFF
            dwcnt = dw1 & 0x7FF; status = (dw1 >> 11) & 7; poison = (dw1 >> 14) & 1; reqid = (dw1 >> 16) & 0xFFFF
            tag = dw2 & 0xFF; cid = (dw2 >> 8) & 0xFFFF
            print(f"  [{i:5d}] CC  status={status} bytecnt={bytecnt} dw={dwcnt} lowaddr=0x{lowaddr:02x} reqid=0x{reqid:04x} "
                  f"tag={tag} completer=0x{cid:04x} poison={poison} tlast={s[cl]} tkeep=0x{s[ck]:x} "
                  f"DW3(data)=0x{dw3:08x}  raw={dw0:08x} {dw1:08x} {dw2:08x} {dw3:08x}", file=out)
    print(f"  {ncq} CQ beats, {ncc} CC beats accepted", file=out)


def decode_sys(names, data, out):
    cyc = col(names, "mmap_bus_cyc"); stb = col(names, "mmap_bus_stb"); we = col(names, "mmap_bus_we")
    ack = col(names, "mmap_bus_ack"); adr = col(names, "mmap_bus_adr"); dw = col(names, "mmap_bus_dat_w")
    dr = col(names, "mmap_bus_dat_r"); sel = col(names, "mmap_bus_sel")
    rqv = col(names, "req_source_valid"); rqr = col(names, "req_source_ready")
    cpv = col(names, "cmp_sink_valid"); cpr = col(names, "cmp_sink_ready"); cpd = col(names, "cmp_sink_payload_dat")
    srst = col(names, "sys_rst"); lock = col(names, "crg_locked"); be = col(names, "bus_errors_status")
    print(f"sys analyzer: {len(data)} samples; sys_rst={data[0][srst] if srst is not None else '?'} "
          f"locked={data[0][lock] if lock is not None else '?'} bus_errors={data[0][be] if be is not None else '?'}", file=out)
    n = 0
    for i, s in enumerate(data):
        ev = []
        if rqv is not None and s[rqv] and s[rqr]: ev.append("REQ->endpoint")
        if cyc is not None and s[cyc] and s[stb]:
            ev.append(f"WB {'WR' if s[we] else 'RD'} adr=0x{s[adr] << 2:08x} sel=0x{s[sel]:x}" + (f" dat_w=0x{s[dw]:08x}" if s[we] else "") + (f" ACK dat_r=0x{s[dr]:08x}" if s[ack] else ""))
        if cpv is not None and s[cpv] and s[cpr]: ev.append(f"CMP->phy dat=0x{s[cpd]:032x}")
        if ev:
            n += 1
            if n <= 400:
                print(f"  [{i:5d}] " + "; ".join(ev), file=out)
    if n == 0:
        print("  no wishbone activity, no request reached the endpoint, no completion left it", file=out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", default=os.path.expanduser("~/MiSTeX-ports/build/c1100_pcie_diag"))
    ap.add_argument("--csr", default="bitstreams/c1100_pcie_video_transport.csr.csv", help="csr.csv for the PCIe-side read (pcie_* map is shared)")
    ap.add_argument("--dev", default="/dev/litepcie0")
    ap.add_argument("--port", type=int, default=1234, help="litex_server port")
    ap.add_argument("--addr", type=lambda x: int(x, 0), default=0x4, help="BAR0 offset to read through PCIe (default ctrl_scratch)")
    ap.add_argument("--write", type=lambda x: int(x, 0), default=None, help="write this value first (through PCIe), then read")
    ap.add_argument("--no-pcie", action="store_true", help="arm and wait 5 s without issuing a read (background traffic only)")
    a = ap.parse_args()

    out_dir = os.path.join("build", "pcie_scope", datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    log = open(os.path.join(out_dir, "scope.log"), "w")
    def say(*s):
        print(*s); print(*s, file=log)

    wb = RemoteClient(csr_csv=os.path.join(a.build, "csr.csv"), port=a.port)
    wb.open()
    say(f"UART side: scratch=0x{wb.regs.ctrl_scratch.read():08x} bus_errors={wb.regs.ctrl_bus_errors.read()} "
        f"link_status=0x{wb.regs.pcie_phy_phy_link_status.read():08x} msi_enable={wb.regs.pcie_phy_phy_msi_enable.read()} "
        f"bus_master={wb.regs.pcie_phy_phy_bus_master_enable.read()}")

    an_p = LiteScopeAnalyzerDriver(wb.regs, "zanalyzer_pcie", config_csv=os.path.join(a.build, "zanalyzer_pcie.csv"), debug=False)
    an_s = LiteScopeAnalyzerDriver(wb.regs, "zanalyzer_sys",  config_csv=os.path.join(a.build, "zanalyzer_sys.csv"),  debug=False)
    for an, trig in ((an_p, "m_axis_cq_tvalid"), (an_s, "mmap_bus_cyc")):
        an.configure_group(0)
        an.configure_subsampler(1)
        name = [n for n, w in an.layouts[0] if trig in n][0]
        an.add_rising_edge_trigger(name)
        an.run(offset=64, length=an.depth)
    say("analyzers armed")
    time.sleep(0.2)

    if not a.no_pcie:
        if a.write is not None:
            pcie_write(a.dev, a.addr, a.write); say(f"PCIe write 0x{a.write:08x} -> BAR0+0x{a.addr:x}")
        v = pcie_read(a.dev, a.addr)
        say(f"PCIe read  BAR0+0x{a.addr:x} = 0x{v:08x}")
    else:
        time.sleep(5)

    for an, name in ((an_p, "pcie"), (an_s, "sys")):
        t0 = time.time()
        while not an.done() and time.time() - t0 < 5:
            time.sleep(0.05)
        say(f"{name} analyzer: {'triggered' if an.done() else 'NOT triggered in 5 s'}")
        if an.done():
            an.upload()
            an.save(os.path.join(out_dir, f"{name}.csv"))
            an.save(os.path.join(out_dir, f"{name}.vcd"))

    say(f"UART side after: scratch=0x{wb.regs.ctrl_scratch.read():08x} bus_errors={wb.regs.ctrl_bus_errors.read()}")
    wb.close()

    for name, fn in (("pcie", decode_pcie), ("sys", decode_sys)):
        p = os.path.join(out_dir, f"{name}.csv")
        if os.path.exists(p):
            names, data = load_csv(p)
            fn(names, data, log); fn(names, data, sys.stdout)
    say(f"dumps in {out_dir}")


if __name__ == "__main__":
    main()
