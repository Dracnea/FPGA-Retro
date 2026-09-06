#
# hps_pcie -- the MiSTer HPS side of hps_io, driven from PCIe registers.
#
# MiSTer's cores talk to the host through hps_io.sv over a 49-bit HPS_BUS:
# a 16-bit word in (io_din) with a one-clock io_strobe, three enable levels
# (fpga / osd / io, which sys_top turns into io_fpga / io_uio) and a 16-bit
# word back (io_dout).  On MiSTer the ARM drives it; MiSTeX drives it from a
# Raspberry Pi over SPI through sys/hps_interface.v, one 16-bit SPI transfer
# per word.  These cards have neither, so this block presents the same thing
# as a handful of CSRs on the LitePCIe BAR and Main_MiSTeX's fpga_io backend
# writes them (host/main_mistex_pcie).
#
# One "SPI word" is reproduced exactly as hps_interface.v does it: the core's
# current io_dout is captured, the new word is presented on io_din, and
# io_strobe pulses for one core clock.  The captured io_dout is what the SPI
# master would have shifted in during that word, i.e. the answer to the
# PREVIOUS word, which is how hps_io's command/response protocol works
# (send a command, read the answer while sending the next word).
#
# Two clock domains: the CSRs live in the SoC's sys domain, the core side in
# the core's clk_sys domain (whatever the core's PLL makes).  Every crossing is
# a toggle handshake or a MultiReg, so the two can be any ratio.
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen.fhdl.module import LiteXModule
from litex.soc.interconnect.csr import CSRStorage, CSRStatus, CSRField, AutoCSR


class HPSBridge(Module):
    """Pure migen: register-style host ports in `sys`, HPS_BUS-style ports in `core_cd`.

    Host side (sys domain)
      ctrl_*        levels: fpga_en, osd_en, io_en, core_reset, btn_osd, btn_user
      din_word/we   one word transaction
      din2_word/we  two word transactions, low half first
      dout          io_dout captured by the last transaction
      busy          a transaction is queued or in flight
      io_wide       hps_io's io_wide, synchronised

    Core side (core_cd domain), the same signals hps_interface.v produces
      io_din, io_strobe, fpga_enable, osd_enable, io_enable, core_reset, btn[1:0]
      io_dout (in), io_wide_in (in)
    """
    def __init__(self, core_cd="core"):
        # host side
        self.ctrl_fpga_en    = Signal()
        self.ctrl_osd_en     = Signal()
        self.ctrl_io_en      = Signal()
        self.ctrl_core_reset = Signal(reset=1)
        self.ctrl_btn_osd    = Signal()
        self.ctrl_btn_user   = Signal()
        self.din_word  = Signal(16)
        self.din_we    = Signal()
        self.din2_word = Signal(32)
        self.din2_we   = Signal()
        self.dout      = Signal(16)
        self.busy      = Signal()
        self.io_wide   = Signal()

        # core side
        self.io_din      = Signal(16)
        self.io_strobe   = Signal()
        self.fpga_enable = Signal()
        self.osd_enable  = Signal()
        self.io_enable   = Signal()
        self.core_reset  = Signal(reset=1)
        self.btn         = Signal(2)
        self.io_dout     = Signal(16)
        self.io_wide_in  = Signal()

        # --- levels, sys -> core ------------------------------------------
        for src, dst in ((self.ctrl_fpga_en, self.fpga_enable), (self.ctrl_osd_en, self.osd_enable),
                         (self.ctrl_io_en, self.io_enable),
                         (Cat(self.ctrl_btn_osd, self.ctrl_btn_user), self.btn)):
            self.specials += MultiReg(src, dst, core_cd)
        self.specials += MultiReg(self.ctrl_core_reset, self.core_reset, core_cd, reset=1)
        self.specials += MultiReg(self.io_wide_in, self.io_wide, "sys")

        # --- word queue and toggle handshake, sys side ------------------------
        q0, q1  = Signal(16), Signal(16)
        count   = Signal(2)
        word    = Signal(16)          # quasi-static while req != ack
        req     = Signal()
        ack     = Signal()            # core-domain ack, synchronised below
        ack_s   = Signal()
        self.specials += MultiReg(ack, ack_s, "sys")
        idle = Signal()
        self.comb += idle.eq(req == ack_s)

        self.sync += [
            # pushes (software waits for busy = 0 between transactions, so at
            # most two words are ever queued; a push into a full queue is dropped)
            If(self.din_we,
                If(count == 0, q0.eq(self.din_word), count.eq(1))
                .Elif(count == 1, q1.eq(self.din_word), count.eq(2)),
            ).Elif(self.din2_we,
                q0.eq(self.din2_word[:16]), q1.eq(self.din2_word[16:]), count.eq(2),
            ).Elif((count != 0) & idle,
                word.eq(q0), q0.eq(q1), count.eq(count - 1), req.eq(~req),
            ),
        ]
        self.comb += self.busy.eq((count != 0) | ~idle)

        # --- the transaction, core side ------------------------------------------
        req_s     = Signal()
        self.specials += MultiReg(req, req_s, core_cd)
        dout_core = Signal(16)        # quasi-static once ack has toggled
        state     = Signal(2)
        sync_core = getattr(self.sync, core_cd)
        sync_core += [
            self.io_strobe.eq(0),
            Case(state, {
                0: If(req_s != ack,
                        dout_core.eq(self.io_dout),   # what the SPI master would have read
                        self.io_din.eq(word),
                        state.eq(1)),
                1: [self.io_strobe.eq(1), state.eq(2)],
                2: [ack.eq(req_s), state.eq(0)],
            }),
        ]
        # dout is read by the host only after busy = 0, by which point ack_s has
        # toggled and dout_core has been stable for the crossing's length.
        self.comb += self.dout.eq(dout_core)


class HPSPCIe(LiteXModule, AutoCSR):
    """HPSBridge behind CSRs.  Names (with the `hps` attribute) are hps_control,
    hps_din, hps_dout, hps_din2, hps_status -- the contract host/main_mistex_pcie
    is written to."""
    def __init__(self, core_cd="core"):
        self.control = CSRStorage(fields=[
            CSRField("fpga_en",    size=1, offset=0, description="SSPI_FPGA_EN level"),
            CSRField("osd_en",     size=1, offset=1, description="SSPI_OSD_EN level"),
            CSRField("io_en",      size=1, offset=2, description="SSPI_IO_EN level"),
            CSRField("core_reset", size=1, offset=3, reset=1, description="HPS_CORE_RESET: 1 holds the core in reset"),
            CSRField("btn_osd",    size=1, offset=4, description="OSD button (the card has none)"),
            CSRField("btn_user",   size=1, offset=5, description="user button"),
        ])
        self.din    = CSRStorage(16, description="write: one HPS word transaction (see hps_pcie.py)")
        self.dout   = CSRStatus(16,  description="io_dout captured by the last transaction")
        self.din2   = CSRStorage(32, description="write: two transactions, low half first")
        self.status = CSRStatus(fields=[
            CSRField("io_wide", size=1, offset=0, description="hps_io WIDE parameter as seen on HPS_BUS[32]"),
            CSRField("busy",    size=1, offset=1, description="a transaction is queued or in flight"),
        ])

        self.bridge = bridge = HPSBridge(core_cd)
        self.comb += [
            bridge.ctrl_fpga_en.eq(self.control.fields.fpga_en),
            bridge.ctrl_osd_en.eq(self.control.fields.osd_en),
            bridge.ctrl_io_en.eq(self.control.fields.io_en),
            bridge.ctrl_core_reset.eq(self.control.fields.core_reset),
            bridge.ctrl_btn_osd.eq(self.control.fields.btn_osd),
            bridge.ctrl_btn_user.eq(self.control.fields.btn_user),
            bridge.din_word.eq(self.din.storage),   bridge.din_we.eq(self.din.re),
            bridge.din2_word.eq(self.din2.storage), bridge.din2_we.eq(self.din2.re),
            self.dout.status.eq(bridge.dout),
            self.status.fields.io_wide.eq(bridge.io_wide),
            self.status.fields.busy.eq(bridge.busy),
        ]
        # core-side signals, for the board file to wire to sys_top / hps_io
        self.io_din      = bridge.io_din
        self.io_strobe   = bridge.io_strobe
        self.fpga_enable = bridge.fpga_enable
        self.osd_enable  = bridge.osd_enable
        self.io_enable   = bridge.io_enable
        self.core_reset  = bridge.core_reset
        self.btn         = bridge.btn
        self.io_dout     = bridge.io_dout
        self.io_wide_in  = bridge.io_wide_in


if __name__ == "__main__":
    # Standalone Verilog of the bridge for the xsim bench (sim/run_sim.sh).
    import sys
    from migen.fhdl.verilog import convert
    b = HPSBridge("core")
    ios = {b.ctrl_fpga_en, b.ctrl_osd_en, b.ctrl_io_en, b.ctrl_core_reset, b.ctrl_btn_osd, b.ctrl_btn_user,
           b.din_word, b.din_we, b.din2_word, b.din2_we, b.dout, b.busy, b.io_wide,
           b.io_din, b.io_strobe, b.fpga_enable, b.osd_enable, b.io_enable, b.core_reset, b.btn,
           b.io_dout, b.io_wide_in}
    out = sys.argv[1] if len(sys.argv) > 1 else "hps_bridge.v"
    convert(b, ios, name="hps_bridge").write(out)
    print("wrote", out)
