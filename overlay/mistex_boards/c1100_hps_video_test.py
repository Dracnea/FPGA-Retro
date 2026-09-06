#!/usr/bin/env python3
#
# C1100 host-path test: c1100_hps_test.py (PCIe endpoint, hps_pcie bridge,
# a real hps_io.sv in a 50 MHz core domain) plus the video path: a 640x480
# VGA-style pattern generator standing in for a core's VGA_* outputs in a
# 25 MHz "vid" domain, through rtl/video_sink into DMA0 as a FRM1 stream, which
# host/viewer displays.  One bitstream exercises both host paths of the "three
# things every core needs" (docs/retro-cores.md) -- the transport for Main and
# the picture for the viewer -- without a core or a memory bridge.
#
# Build (from a MiSTeX-ports checkout with the overlay installed):
#   venv/bin/python mistex_boards/c1100_hps_video_test.py --build
#
# SPDX-License-Identifier: BSD-2-Clause

import sys
from os.path import join, dirname, abspath, normpath

sys.path.insert(0, join(dirname(abspath(__file__)), "..", "platforms"))
sys.path.insert(0, join(dirname(abspath(__file__)), "..", "rtl", "hps_pcie"))
sys.path.insert(0, join(dirname(abspath(__file__)), "..", "rtl", "video_sink"))

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen.fhdl.module import LiteXModule
from litex.soc.cores.clock import USPMMCM
from litex.soc.integration.soc_core import SoCMini
from litex.soc.integration.builder import Builder
from litex.soc.interconnect.csr import CSRStatus, CSRField, AutoCSR

from litepcie.phy.usppciephy import USPHBMPCIEPHY
from litepcie.software import generate_litepcie_software

import xilinx_c1100
from hps_pcie import HPSPCIe
from video_sink import VideoSinkCSR, VGAPattern

PORTS_ROOT = normpath(join(dirname(abspath(__file__)), ".."))

# What Main will read as the core's configuration: name, two options, version.
CONF_STR = "HPSTEST;;O1,Option one,Off,On;O2,Option two,No,Yes;V,v1.0 C1100 hps_pcie;"


class _CRG(LiteXModule):
    """100 MHz reference -> 125 MHz sys (as c1100_pcie_video.py) and a 50 MHz
    'core' clock standing in for a MiSTer core's clk_sys, so the sys <-> core
    crossings in hps_pcie are exercised for real."""
    def __init__(self, platform, sys_clk_freq, core_clk_freq=50e6, vid_clk_freq=25e6):
        self.rst     = Signal()
        self.cd_sys  = ClockDomain()
        self.cd_core = ClockDomain()
        self.cd_vid  = ClockDomain()      # the pattern generator's pixel clock (a core's CLK_VIDEO)

        clk100 = platform.request("clk100")
        self.mmcm = mmcm = USPMMCM(speedgrade=-2, name="sys_mmcm")
        self.comb += mmcm.reset.eq(self.rst)
        mmcm.register_clkin(clk100, 100e6)
        mmcm.create_clkout(self.cd_sys,  sys_clk_freq,  margin=0)
        mmcm.create_clkout(self.cd_core, core_clk_freq, margin=0)
        mmcm.create_clkout(self.cd_vid,  vid_clk_freq,  margin=0)
        platform.add_period_constraint(clk100, 1e9/100e6)


class HPSTestCore(LiteXModule, AutoCSR):
    """hps_io_wrap in the core domain, its outputs on CSRs for the host to check."""
    def __init__(self, platform, hps):
        self.joystick0 = CSRStatus(32, description="hps_io joystick_0 (UIO_JOYSTICK0 words)")
        self.joystick1 = CSRStatus(32, description="hps_io joystick_1")
        self.status_lo = CSRStatus(32, description="hps_io status[31:0] (OSD option bits)")
        self.misc      = CSRStatus(fields=[
            CSRField("buttons",        size=2,  offset=0,  description="hps_io buttons (cfg[1:0])"),
            CSRField("ioctl_download", size=1,  offset=2),
            CSRField("ioctl_index",    size=16, offset=8),
        ])
        self.ioctl_count = CSRStatus(32, description="ioctl_wr strobes seen (file upload words)")
        self.ioctl_last  = CSRStatus(32, description="last ioctl address (27 bits) and data byte")

        joystick_0 = Signal(32); joystick_1 = Signal(32); status = Signal(128); buttons = Signal(2)
        ioctl_download = Signal(); ioctl_index = Signal(16); ioctl_wr = Signal()
        ioctl_addr = Signal(27); ioctl_dout = Signal(16)
        io_dout = Signal(16); io_wide = Signal(); io_wait = Signal()

        self.specials += Instance("hps_io_wrap",
            p_CONF_STR = CONF_STR, p_WIDE = 0, p_VDNUM = 1,
            i_clk_sys     = ClockSignal("core"),
            i_io_din      = hps.io_din,
            i_io_strobe   = hps.io_strobe,
            i_fpga_enable = hps.fpga_enable,
            i_osd_enable  = hps.osd_enable,
            i_io_enable   = hps.io_enable,
            o_io_dout     = io_dout,
            o_io_wide     = io_wide,
            o_io_wait     = io_wait,
            o_joystick_0  = joystick_0,
            o_joystick_1  = joystick_1,
            o_status      = status,
            o_buttons     = buttons,
            o_ioctl_download = ioctl_download,
            o_ioctl_index = ioctl_index,
            o_ioctl_wr    = ioctl_wr,
            o_ioctl_addr  = ioctl_addr,
            o_ioctl_dout  = ioctl_dout,
        )
        self.comb += [hps.io_dout.eq(io_dout), hps.io_wide_in.eq(io_wide)]

        # core-domain counters, then quasi-static values across to sys
        count = Signal(32); last = Signal(32)
        self.sync.core += If(ioctl_wr, count.eq(count + 1), last.eq(Cat(ioctl_dout[:8], ioctl_addr[:24])))
        for src, dst in ((joystick_0, self.joystick0.status), (joystick_1, self.joystick1.status),
                         (status[:32], self.status_lo.status), (buttons, self.misc.fields.buttons),
                         (ioctl_download, self.misc.fields.ioctl_download), (ioctl_index, self.misc.fields.ioctl_index),
                         (count, self.ioctl_count.status), (last, self.ioctl_last.status)):
            self.specials += MultiReg(src, dst, "sys")

        sys_dir = join(PORTS_ROOT, "cores", "Template", "sys")
        platform.add_source(join(sys_dir, "hps_io.sv"), language="systemverilog")
        platform.add_source(join(PORTS_ROOT, "rtl", "hps_pcie", "hps_io_wrap.sv"), language="systemverilog")
        # hps_io.sv selects its Xilinx-safe config-string path on this define, as MiSTeX's flow does
        platform.toolchain.pre_synthesis_commands.append(
            "set_property verilog_define {{XILINX=1}} [current_fileset]")


class HPSTestSoC(SoCMini):
    def __init__(self, platform, speed="gen3", nlanes=4, sys_clk_freq=125e6):
        SoCMini.__init__(self, platform, sys_clk_freq, ident=f"C1100 HPS + video path test x{nlanes} {speed}")
        self.crg = _CRG(platform, sys_clk_freq)
        self.comb += platform.request("hbm_cattrip").eq(0)      # non-negotiable on this board

        pcie_pads = platform.request(f"pcie_x{nlanes}")
        self.pcie_phy = USPHBMPCIEPHY(platform, pcie_pads, speed=speed,
                                      data_width={1:64, 4:128, 8:256, 16:512}[nlanes], bar0_size=0x20000)
        self.add_pcie(phy=self.pcie_phy, ndmas=1, with_dma_buffering=True, dma_buffering_depth=1024,
                      with_dma_loopback=False)

        self.hps     = HPSPCIe(core_cd="core")
        self.hpstest = HPSTestCore(platform, self.hps)

        # Video: pattern -> sink -> DMA0 writer (card -> host RAM)
        self.pattern = VGAPattern()
        self.video   = video = VideoSinkCSR(vid_cd="vid", fifo_depth=1024)
        p = self.pattern
        self.comb += [
            video.r.eq(p.r), video.g.eq(p.g), video.b.eq(p.b),
            video.hs.eq(p.hs), video.vs.eq(p.vs), video.de.eq(p.de), video.ce_pix.eq(p.ce_pix), video.f1.eq(p.f1),
            video.source.connect(self.pcie_dma0.sink),
        ]

        # Both MMCM outputs derive from clk100, so Vivado times sys <-> core
        # paths as related; every crossing is a MultiReg / handshake, so declare
        # the groups asynchronous -- by MMCM pin, in the pre-placement commands
        # (docs/ps2-iop-bringup.md, build 2, for why not by name).
        platform.toolchain.pre_placement_commands.append(
            "set_clock_groups -asynchronous "
            "-group [get_clocks -of_objects [get_pins sys_mmcm/CLKOUT0]] "
            "-group [get_clocks -of_objects [get_pins sys_mmcm/CLKOUT1]] "
            "-group [get_clocks -of_objects [get_pins sys_mmcm/CLKOUT2]] "
            "-group [get_clocks clk100_p]")


def build(nlanes=4, speed="gen3", do_build=False, build_dir="build/c1100_hps_video_test"):
    platform = xilinx_c1100.Platform(toolchain="vivado")
    soc      = HPSTestSoC(platform, speed=speed, nlanes=nlanes)
    builder  = Builder(soc, output_dir=build_dir, compile_software=False, csr_csv=join(build_dir, "csr.csv"))
    builder.build(run=do_build)
    try:
        generate_litepcie_software(soc, join(build_dir, "software"))
    except Exception as e:
        print(f"note: litepcie software generation skipped: {e}")
    return builder


if __name__ == "__main__":
    build(nlanes=16 if "--x16" in sys.argv else 4, do_build="--build" in sys.argv)
