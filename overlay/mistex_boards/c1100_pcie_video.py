#!/usr/bin/env python3
#
# C1100 PCIe transport -- stage 1 of the retro video path.
#
# Target flow (the whole reason this file exists):
#
#   Retro core -> FPGA framebuffer -> PCIe DMA -> host RAM -> host software
#                -> GPU -> HDMI/DisplayPort -> monitor
#
# This file builds the middle of that chain and nothing else yet: a PCIe
# endpoint with DMA, plus a synthetic frame generator standing in for the retro
# core. Proving the link and the DMA first is deliberate -- every later stage is
# worthless if the card cannot move bytes into host RAM, and that is the single
# assumption the whole architecture rests on.
#
# WHY THIS ARCHITECTURE AND NOT MiSTeX's
# --------------------------------------
# MiSTer's ARM HPS shares DDR3 with the FPGA fabric, so Main_MiSTer's
# shmem_map()/shmem_get() genuinely map fabric memory and the host can read
# frames out (that is how its screenshot and scaler paths work).
#
# MiSTeX replaced the HPS with a Raspberry Pi Zero on SPI + GPIO. SPI cannot
# map memory, so Main_MiSTeX/shmem.cpp is a STUB -- all four of shmem_map,
# shmem_unmap, shmem_put and shmem_get print "TODO: not implemented" and return
# nothing, with 20 call sites depending on them. MiSTeX therefore has no frame
# path at all; its video leaves the FPGA's own HDMI pins and the host never
# sees a pixel.
#
# PCIe gives that capability back, and more of it than MiSTer had: a BAR plus
# DMA is real shared access to fabric memory over a much faster link. So this
# design is architecturally closer to original MiSTer than MiSTeX is, and the
# port seam on the software side is small and well-defined -- implement those
# four shmem functions over PCIe, and re-target the SPI transport.
#
# STATUS: builds clean and closes timing; see docs/c1100-pcie-transport.md for
# the measured result. Note that the host enumerates BARs at boot, so a card
# previously holding a bitstream with no PCIe endpoint needs the link restored
# (JTAG load plus a PCIe rescan, or a warm reboot) before it will appear.
#
# SPDX-License-Identifier: BSD-2-Clause

import sys
from os.path import join, dirname, abspath

sys.path.insert(0, join(dirname(abspath(__file__)), "..", "platforms"))

from migen import *

from litex.gen.fhdl.module import LiteXModule
from litex.soc.cores.clock import USPMMCM
from litex.soc.integration.soc_core import SoCMini
from litex.soc.integration.builder import Builder
from litex.soc.interconnect.csr import CSRStorage, CSRStatus, AutoCSR

from litepcie.phy.usppciephy import USPHBMPCIEPHY
from litepcie.core import LitePCIeEndpoint, LitePCIeMSI
from litepcie.frontend.dma import LitePCIeDMA
from litepcie.frontend.wishbone import LitePCIeWishboneBridge
from litepcie.software import generate_litepcie_software

import xilinx_c1100


# Clocking -----------------------------------------------------------------------------------------

class _CRG(LiteXModule):
    """100 MHz reference (BK43/BK44) -> sys clock.

    Note this is 100 MHz, NOT the FK33's 200 MHz. margin=0 forces integer
    dividers; LiteX's default +-1% tolerance silently produced a 100.79 MHz
    "100 MHz" clock on the FK33, and retro cores divide these down to exact
    console rates.
    """
    def __init__(self, platform, sys_clk_freq):
        self.rst    = Signal()
        self.cd_sys = ClockDomain()

        clk100 = platform.request("clk100")

        self.mmcm = mmcm = USPMMCM(speedgrade=-2)
        self.comb += mmcm.reset.eq(self.rst)
        mmcm.register_clkin(clk100, 100e6)
        mmcm.create_clkout(self.cd_sys, sys_clk_freq, margin=0)

        platform.add_period_constraint(clk100, 1e9/100e6)


# Frame source -------------------------------------------------------------------------------------

class TestFrameSource(LiteXModule, AutoCSR):
    """Stands in for the retro core's video output.

    Emits a deterministic pattern so the host can verify DMA integrity exactly:
    every 32-bit word is (frame_number << 24) | pixel_index & 0xffffff. A host
    that reads a frame can check it word-for-word, which turns "did the DMA
    work" into a yes/no answer instead of a judgement about whether an image
    looks right.

    A real core replaces this with VGA_R/G/B packed into the same stream, which
    is why the interface is a plain stream endpoint and not something bespoke.
    """
    def __init__(self, dma_sink, width=320, height=240):
        self.enable  = CSRStorage(reset=0)
        self.frames  = CSRStatus(32)
        self.pixels  = CSRStatus(32)

        frame_no = Signal(8)
        idx      = Signal(24)
        npix     = width * height

        self.comb += [
            dma_sink.valid.eq(self.enable.storage),
            dma_sink.data.eq(Cat(idx, frame_no)),
        ]
        self.sync += [
            If(self.enable.storage & dma_sink.ready,
                self.pixels.status.eq(self.pixels.status + 1),
                If(idx == (npix - 1),
                    idx.eq(0),
                    frame_no.eq(frame_no + 1),
                    self.frames.status.eq(self.frames.status + 1),
                ).Else(
                    idx.eq(idx + 1),
                ),
            ),
        ]


# SoC ----------------------------------------------------------------------------------------------

class PCIeVideoSoC(SoCMini):
    def __init__(self, platform, speed="gen3", nlanes=4, sys_clk_freq=125e6):
        SoCMini.__init__(self, platform, sys_clk_freq,
                         ident=f"C1100 PCIe video transport x{nlanes} {speed}")

        self.crg = _CRG(platform, sys_clk_freq)

        # Non-negotiable on this board: if hbm_cattrip floats, the satellite
        # controller reads a catastrophic over-temperature event and powers the
        # card off. Documented in our tree as the trap that silently kills a
        # C1100 bring-up.
        self.comb += platform.request("hbm_cattrip").eq(0)

        # PCIe. USPHBMPCIEPHY is LitePCIe's UltraScale+ HBM variant, which is
        # exactly this device class (xcu55n is a VU35P-class HBM part).
        # x4 is the default because a card sharing a desktop with a GPU
        # commonly gets 4 lanes.
        pcie_pads = platform.request(f"pcie_x{nlanes}")
        self.pcie_phy = USPHBMPCIEPHY(platform, pcie_pads,
                                      speed      = speed,
                                      data_width = {1:64, 4:128, 8:256, 16:512}[nlanes],
                                      bar0_size  = 0x20000)

        self.add_pcie(phy=self.pcie_phy, ndmas=1,
                      with_dma_buffering = True, dma_buffering_depth=1024,
                      with_dma_loopback  = False)

        # Frame generator feeding DMA0's writer (card -> host RAM).
        self.frame_source = TestFrameSource(self.pcie_dma0.sink)

        # --- Reset CDC exception ------------------------------------------------
        # Without this the design misses timing by 806 ps on exactly ONE path,
        # and the path is not real work:
        #
        #   STARTPOINT  reset_storage_reg[0]/C   (clkout, the 125 MHz sys clock)
        #   ENDPOINT    FDCE/D                   (clk100_p, the raw 100 MHz input)
        #   LOGIC LEVELS 1     DATAPATH 0.399 ns     REQUIREMENT 2.000 ns
        #
        # reset_storage_reg is LiteX's software-writable SoC reset CSR. It
        # changes when software writes it -- never on a cycle-accurate basis --
        # and it is synchronised on the destination side. It fails only because
        # 125 MHz and 100 MHz are unrelated frequencies whose tightest edge
        # alignment is 2 ns, so Vivado times an asynchronous reset handoff as a
        # same-cycle transfer. 0.399 ns of delay against a 2 ns requirement is
        # the signature of a mis-timed crossing, not a slow path.
        #
        # This is the identical diagnosis to the FK33 victory wire
        # (gcore[N].u_engine/victory_reg -> vic_s1_reg[N]), which moved that
        # design from WNS -0.039 to +0.035 once declared.
        #
        # WHY set_clock_groups AND NOT set_max_delay. The obvious fix --
        #   set_max_delay -datapath_only -from [get_cells ... reset_storage_reg*]
        # was tried first and DOES NOT WORK. Verified against the routed
        # checkpoint: it matches 4 real cells and appears in report_exceptions,
        # yet slack moved only -0.806 -> -0.802 and the worst endpoint was
        # unchanged. A -from with no -to does not override the inter-clock
        # requirement that is the actual cause. Do not "simplify" this back.
        #
        # Declaring the two clocks asynchronous is correct here rather than a
        # blunt instrument, because clk100_p carries NO functional logic: it has
        # ~7 endpoints, all MMCM and reset infrastructure, and the only crossing
        # is soc_rst, which is synchronised at its destination. There are no
        # real synchronous paths between the domains to lose.
        #
        # Measured against the routed checkpoint before adopting:
        #   before: WNS -0.806, reset_storage_reg[0]/C -> FDCE/D (net soc_rst)
        #   after : WNS +0.729, worst path entirely inside pcie_clk
        # AND WHY add_false_path_constraints_by_name AND NOT add_platform_command.
        # Emitting the same set_clock_groups via add_platform_command ALSO does
        # not work, and fails silently in the classic way:
        #
        #   WARNING [Vivado 12-627] No clocks matched 'clkout'.       xdc:79
        #   WARNING [Vivado 12-627] No clocks matched 'clk100_p'.     xdc:79
        #   CRITICAL WARNING [Vivado 12-4739] set_clock_groups: No valid object(s)
        #
        # add_platform_command lands the constraint early in the XDC, BEFORE the
        # create_clock statements have run, so both names resolve to nothing and
        # the build reports exactly the slack it had with no constraint at all
        # (-0.806 both times). Verifying the constraint against a routed
        # checkpoint does NOT catch this -- a checkpoint has every clock already
        # resolved; the build XDC is read in order.
        #
        # LiteX's own API exists for precisely this and says so:
        #   "On Vivado, some generated/internal clocks are only resolvable after
        #    synthesis. Emit explicit set_clock_groups in pre_placement_commands
        #    for robust resolution."
        #
        # AFTER BUILDING, CHECK THE LOG. If it contains "No clocks matched" or
        # 12-4739 for these names, the constraint is inert again and the timing
        # number is meaningless.
        platform.add_false_path_constraints_by_name("clkout", "clk100_p")


def build(nlanes=4, speed="gen3", do_build=False, build_dir="build/c1100_pcie"):
    platform = xilinx_c1100.Platform(toolchain="vivado")
    soc      = PCIeVideoSoC(platform, speed=speed, nlanes=nlanes)
    builder  = Builder(soc, output_dir=build_dir, compile_software=False,
                       csr_csv=join(build_dir, "csr.csv"))
    builder.build(run=do_build)
    # Host-side driver + userspace tools, generated to match this gateware.
    try:
        generate_litepcie_software(soc, join(build_dir, "software"))
    except Exception as e:
        print(f"note: litepcie software generation skipped: {e}")
    return builder


if __name__ == "__main__":
    build(nlanes = 4 if "--x4" in sys.argv else (16 if "--x16" in sys.argv else 4),
          do_build = "--build" in sys.argv)
