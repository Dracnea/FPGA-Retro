#!/usr/bin/env python3
#
# C1100 PCIe transport, diagnostic build: the c1100_pcie_video design unchanged,
# plus two ways in that do not go through PCIe.
#
#   * UARTbone on the card's FPGA UART 0 (BJ41/BK41, Corundum's uart_txd[0] /
#     uart_rxd[0], which reach the on-board FT4232H). The CSR bus becomes
#     reachable with litex_server --uart, independent of the PCIe endpoint, so
#     "is the sys domain alive / does the CSR bus answer" is a direct question.
#   * Two LiteScope analyzers: one in the pcie clock domain on the raw AXI-Stream
#     interfaces of the hard IP (CQ in, CC out, RQ/RC valid), one in sys on the
#     PCIe wishbone master and the endpoint's request/completion streams. Read
#     over the same UART with litescope_cli.
#
# Why: on hardware every BAR0 read returns 0xffffffff fast, with no error status
# anywhere (docs/c1100-pcie-transport.md). Whether the request reaches the
# fabric, what the completion carries, and whether the wishbone read happens are
# exactly the three things these probes show.
#
# The CSR map of the pcie_* blocks is kept identical to the transport image by
# naming the additions so they sort last (zanalyzer_*), so the transport build's
# litepcie.ko and csr.csv remain valid for the PCIe-side registers; the new
# blocks' addresses are in this build's own csr.csv.
#
# SPDX-License-Identifier: BSD-2-Clause

import sys
from os.path import join, dirname, abspath

sys.path.insert(0, dirname(abspath(__file__)))
sys.path.insert(0, join(dirname(abspath(__file__)), "..", "platforms"))

from migen import *
from migen.genlib.cdc import MultiReg
from litex.gen.fhdl.module import LiteXModule
from litex.build.generic_platform import Subsignal, Pins, IOStandard
from litex.soc.interconnect.csr import CSRStorage, CSRStatus, AutoCSR
from litex.soc.integration.builder import Builder
from litescope import LiteScopeAnalyzer
from litepcie.software import generate_litepcie_software

import xilinx_c1100
from c1100_pcie_video import PCIeVideoSoC

# FPGA UART 0 to the FT4232H. Pins from Corundum's public AU55N constraints
# (uart_txd[0] BJ41, uart_rxd[0] BK41, LVCMOS18). Which of the FTDI's channels
# B/C/D it appears on is found by trying /dev/ttyUSB1..3.
_serial = [
    ("serial", 0,
        Subsignal("tx", Pins("BJ41")),
        Subsignal("rx", Pins("BK41")),
        IOStandard("LVCMOS18"),
    ),
]


class HardIPStatus(LiteXModule, AutoCSR):
    """The hard block's own view, as CSRs: everything PG213 says makes the
    integrated block answer a memory request itself with UR instead of
    presenting it on CQ (function disabled, memory space off, D3, FLR pending)
    plus its error and message outputs. Level signals are resynchronised to
    sys; pulse signals are latched in the pcie domain until `clear` is written.
    """
    def __init__(self, params):
        def port(name, width, fallback_open=True):
            sig = params.get(name)
            if sig is None or not isinstance(sig, Signal):
                sig = Signal(width, name=name[2:])
                params[name] = sig          # replaces Open() or adds the port
            return sig

        levels = {
            "function_status":     port("o_cfg_function_status", 16),
            "function_power_state":port("o_cfg_function_power_state", 12),
            "ltssm_state":         port("o_cfg_ltssm_state", 6),
            "negotiated_width":    port("o_cfg_negotiated_width", 3),
            "current_speed":       port("o_cfg_current_speed", 2),
            "phy_link_status":     port("o_cfg_phy_link_status", 2),
            "phy_link_down":       port("o_cfg_phy_link_down", 1),
            "np_req_count":        port("o_pcie_cq_np_req_count", 6),
            "tfc_nph_av":          port("o_pcie_tfc_nph_av", 4),
            "tfc_npd_av":          port("o_pcie_tfc_npd_av", 4),
            "rq_tag_av":           port("o_pcie_rq_tag_av", 4),
            "rx_pm_state":         port("o_cfg_rx_pm_state", 2),
            "tx_pm_state":         port("o_cfg_tx_pm_state", 2),
            "rcb_status":          port("o_cfg_rcb_status", 4),
            "max_payload":         port("o_cfg_max_payload", 2),
            "max_read_req":        port("o_cfg_max_read_req", 3),
            "msi_enable":          port("o_cfg_interrupt_msi_enable", 4),
            "flr_in_process":      port("o_cfg_flr_in_process", 4),
            "local_error_out":     port("o_cfg_local_error_out", 5),
            "msg_received_type":   port("o_cfg_msg_received_type", 5),
        }
        pulses = {
            "err_cor":             port("o_cfg_err_cor_out", 1),
            "err_nonfatal":        port("o_cfg_err_nonfatal_out", 1),
            "err_fatal":           port("o_cfg_err_fatal_out", 1),
            "local_error_valid":   port("o_cfg_local_error_valid", 1),
            "hot_reset":           port("o_cfg_hot_reset_out", 1),
            "power_state_change":  port("o_cfg_power_state_change_interrupt", 1),
            "msg_received":        port("o_cfg_msg_received", 1),
            "pl_status_change":    port("o_cfg_pl_status_change", 1),
        }
        self.clear = CSRStorage(description="write 1 to clear the latched pulse flags and the message counter")
        clear_pcie = Signal()
        self.specials += MultiReg(self.clear.re, clear_pcie, "pcie")

        for name, sig in levels.items():
            csr = CSRStatus(len(sig), name=name)
            setattr(self, name, csr)
            self.specials += MultiReg(sig, csr.status, "sys")

        for name, sig in pulses.items():
            latch = Signal(name=name + "_latch")
            self.sync.pcie += If(clear_pcie, latch.eq(0)).Elif(sig, latch.eq(1))
            csr = CSRStatus(1, name=name + "_seen")
            setattr(self, name + "_seen", csr)
            self.specials += MultiReg(latch, csr.status, "sys")

        msg_count = Signal(16)
        self.sync.pcie += If(clear_pcie, msg_count.eq(0)).Elif(pulses["msg_received"], msg_count.eq(msg_count + 1))
        self.msg_count = CSRStatus(16)
        self.specials += MultiReg(msg_count, self.msg_count.status, "sys")

        cq_count = Signal(32)   # beats accepted on the raw CQ interface, ever
        self.sync.pcie += If(params["o_m_axis_cq_tvalid"] & params["i_m_axis_cq_tready"][0], cq_count.eq(cq_count + 1))
        self.cq_beats = CSRStatus(32)
        self.specials += MultiReg(cq_count, self.cq_beats.status, "sys")


class PCIeDiagSoC(PCIeVideoSoC):
    def __init__(self, platform, baudrate=115200, depth=1024, **kwargs):
        platform.add_extension(_serial)
        PCIeVideoSoC.__init__(self, platform, **kwargs)

        # The base target declares sys <-> clk100 asynchronous by clock *name*
        # ("clkout"). With more modules in the design the MMCM output net is
        # "crg_clkout" and that constraint matches nothing (the fourth time a
        # by-name clock constraint has cost a build here; see
        # docs/c1100-pcie-transport.md). Replace it with the by-pin form.
        cmds = platform.toolchain.pre_placement_commands
        cmds[:] = [c for c in cmds if not (isinstance(c, str) and "get_clocks clkout" in c)]
        cmds.append("set_clock_groups -asynchronous "
                    "-group [get_clocks -of_objects [get_pins MMCME4_ADV/CLKOUT0]] "
                    "-group [get_clocks clk100_p]")

        # CSR bus over the UART.
        self.add_uartbone("serial", baudrate=baudrate)

        # Raw hard-IP streams, pcie clock domain. The PHY keeps the signals it
        # hands to the pcie_usp instance in pcie_usp_phy_params.
        p = self.pcie_phy.pcie_usp_phy_params
        self.zhardip = HardIPStatus(p)
        raw = [p[k] for k in (
            "o_m_axis_cq_tvalid", "i_m_axis_cq_tready", "o_m_axis_cq_tlast", "o_m_axis_cq_tkeep",
            "o_m_axis_cq_tdata", "o_m_axis_cq_tuser",
            "i_s_axis_cc_tvalid", "o_s_axis_cc_tready", "i_s_axis_cc_tlast", "i_s_axis_cc_tkeep",
            "i_s_axis_cc_tdata",
            "i_s_axis_rq_tvalid", "o_s_axis_rq_tready", "o_m_axis_rc_tvalid",
            "o_user_lnk_up",
        )]
        raw.append(self.pcie_phy.cd_pcie.rst)
        raw.append(p["o_cfg_function_status"])
        raw.append(p["o_cfg_flr_in_process"])
        self.zanalyzer_pcie = LiteScopeAnalyzer(raw, depth=depth, clock_domain="pcie",
                                                csr_csv="zanalyzer_pcie.csv")

        # sys domain: the PCIe wishbone master, the endpoint <-> PHY streams,
        # resets and lock.
        wb  = self.pcie_mmap.wishbone
        phy = self.pcie_phy
        sysg = [
            wb.cyc, wb.stb, wb.we, wb.ack, wb.err, wb.sel, wb.adr, wb.dat_w, wb.dat_r,
            phy.req_source.valid, phy.req_source.ready, phy.req_source.last,   # requests from host, after CDC
            phy.cmp_sink.valid,   phy.cmp_sink.ready,   phy.cmp_sink.last,     # completions to host, before CDC
            phy.cmp_sink.dat,
            phy.req_sink.valid, phy.cmp_source.valid,                          # DMA side, for completeness
            self.crg.cd_sys.rst, self.crg.mmcm.locked,
            self.ctrl._bus_errors.status,
        ]
        self.zanalyzer_sys = LiteScopeAnalyzer(sysg, depth=depth, clock_domain="sys",
                                               csr_csv="zanalyzer_sys.csv")


def build(do_build=False, build_dir="build/c1100_pcie_diag"):
    platform = xilinx_c1100.Platform(toolchain="vivado")
    soc      = PCIeDiagSoC(platform)
    builder  = Builder(soc, output_dir=build_dir, compile_software=False,
                       csr_csv=join(build_dir, "csr.csv"))
    builder.build(run=do_build)
    try:
        generate_litepcie_software(soc, join(build_dir, "software"))
    except Exception as e:
        print(f"note: litepcie software generation skipped: {e}")
    return builder


if __name__ == "__main__":
    build(do_build="--build" in sys.argv)
