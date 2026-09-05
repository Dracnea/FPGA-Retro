#!/usr/bin/env python3
#
# MiSTeX board target for the Xilinx Varium C1100 (Alveo U55N, xcu55n).
#
# Companion to sqrl_fk33_mistex.py. Same reasoning applies: build_xilinx() from
# xilinx_mistex.py is Series-7 code (S7PLL / VideoS7HDMIPHY / s7ddrphy) and
# requests fourteen platform resources this card does not have, so it cannot be
# used here either.
#
# The C1100 differs from the FK33 in three ways that matter:
#   * 100 MHz reference clock, not 200 MHz.
#   * hbm_cattrip must be driven LOW or the card powers itself off.
#   * It is roughly twice the FK33: 871,680 LUTs vs 439,680, 1,344 BRAM tiles
#     vs 672, 640 URAM vs 320. That is ~28 MB of on-chip memory, which is the
#     single most interesting property for hosting retro cores -- an NES fits
#     with four orders of magnitude to spare, and many instances fit at once.
#
# SPDX-License-Identifier: BSD-2-Clause

import sys
from os.path import join, dirname, abspath

sys.path.insert(0, join(dirname(abspath(__file__)), "..", "platforms"))

from migen import *
from litex.gen.fhdl.module import LiteXModule
from litex.soc.cores.clock import USPMMCM

import xilinx_c1100


# Clock generation ---------------------------------------------------------------------------------

class _CRG(LiteXModule):
    """UltraScale+ clock generator for the C1100.

    Reference is 100 MHz on BK43/BK44 -- half the FK33's. Do not copy CRG
    constants between the two boards; the register_clkin() frequency below is
    the whole difference and getting it wrong yields a design that builds and
    runs at the wrong speed.

    The 50 MHz output feeds the core PLL shim (rtl/pll_0002-xilinxusp.v) as
    MiSTer's CLK_50M, exactly as on the FK33. That shim is board-independent
    precisely so it can be shared between these two targets unchanged.
    """

    def __init__(self, platform, sys_clk_freq=100e6):
        self.rst        = Signal()
        self.cd_sys     = ClockDomain()
        self.cd_clk50   = ClockDomain()
        self.cd_retro   = ClockDomain()
        self.cd_retro2x = ClockDomain()

        clk100 = platform.request("clk100")

        self.mmcm = mmcm = USPMMCM(speedgrade=-2)
        self.comb += mmcm.reset.eq(self.rst)

        mmcm.register_clkin(clk100, 100e6)
        # margin=0: LiteX defaults to +-1% and will solve a fractional divider
        # inside it. On the FK33 that produced a "100 MHz" clock that was
        # actually 100.79 MHz. Retro cores divide these down to hit exact
        # console timings, so the error compounds into wrong frame/audio rates.
        mmcm.create_clkout(self.cd_sys,     sys_clk_freq, margin=0)
        mmcm.create_clkout(self.cd_clk50,   50e6,         margin=0)
        mmcm.create_clkout(self.cd_retro,   50e6,         margin=0)
        mmcm.create_clkout(self.cd_retro2x, 100e6,        margin=0)

        platform.add_period_constraint(clk100, 1e9/100e6)


# What is still missing ----------------------------------------------------------------------------

MISSING = {
    "PCIe pin map": (
        "The C1100's PCIe lane assignments are in no constraint file in this "
        "tree and Vivado ships no U55N board file. They must come from the "
        "official Alveo U55N XDC. Until then no PCIe design can be built for "
        "this card, which blocks the video path specifically."
    ),
    "video sink": (
        "No display output of any kind. The core's VGA_* must be written to a "
        "framebuffer and DMA'd to the host over PCIe (LitePCIe USPHBMPCIEPHY, "
        "which exists and targets UltraScale+ HBM parts). This is the critical "
        "path and it depends on the PCIe pin map above."
    ),
    "host interface (HPS replacement)": (
        "MiSTeX substitutes an external SBC over SPIBone for MiSTer's ARM HPS. "
        "The C1100 exposes no such pins. The host PC over PCIe is the natural "
        "replacement, which means re-implementing hps_io's transport."
    ),
}


def build(coredir, core, toolchain="vivado"):
    raise NotImplementedError(
        "The C1100 MiSTeX target is not buildable yet.\n\n"
        "Done:      platforms/xilinx_c1100.py (pins verified against our own\n"
        "           bitstreams built on this card) and the _CRG above.\n"
        "           cores/NES/rtl/pll_0002-xilinxusp.v is shared with the FK33\n"
        "           unchanged -- both are UltraScale+ MMCME4_ADV parts.\n\n"
        "Blocked on:\n  - " + "\n  - ".join(
            f"{k}: {v.split('.')[0]}." for k, v in MISSING.items()
        ) + "\n\n"
        "Run smoke_test() instead to validate the platform through Vivado."
    )


def smoke_test(build_dir="build/c1100_smoke", do_build=False):
    """Smallest design that proves the platform file is correct on this card.

    Unlike the FK33 -- which is not physically present -- the C1100 IS attached
    to this machine, so the resulting bitstream can actually be loaded over JTAG
    and confirmed on silicon.

    hbm_cattrip is driven LOW here and in every design for this board. Omitting
    it is the documented way to have the satellite controller power the card off
    mid-bring-up.
    """
    from litex.soc.integration.soc_core import SoCMini
    from litex.soc.integration.builder import Builder

    platform = xilinx_c1100.Platform(toolchain="vivado")

    class SmokeSoC(SoCMini):
        def __init__(self):
            sys_clk_freq = 100e6
            SoCMini.__init__(self, platform, sys_clk_freq, ident="C1100 platform smoke test")
            self.crg = _CRG(platform, sys_clk_freq)

            # Non-negotiable on this board.
            self.comb += platform.request("hbm_cattrip").eq(0)

            # Free-running counter so the sys clock domain has real sequential
            # logic to constrain.
            #
            # attr={"keep","dont_touch"} is REQUIRED here, and the reason is
            # worth recording. The FK33 smoke test drives 7 LEDs from its
            # counter, so the logic has an observable endpoint and survives.
            # The C1100 exposes no LEDs, so an unattributed counter drives
            # nothing, synthesis removes it entirely, and the build reports
            # "CLB LUTs 0 / CLB Registers 8" with "WNS 0.000" -- which reads
            # like a pass but means there were no paths to time at all. Keeping
            # the counter is what makes this a timing test rather than a
            # pin-map test.
            counter = Signal(28, attr={"keep", "dont_touch"})
            self.sync += counter.eq(counter + 1)

    soc = SmokeSoC()
    builder = Builder(soc, output_dir=build_dir, compile_software=False)
    builder.build(run=do_build)
    return builder


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "smoke":
        smoke_test(do_build="--build" in sys.argv)
    else:
        print(__doc__)
        print("\nMissing pieces:\n")
        for k, v in MISSING.items():
            print(f"  {k}:\n    {v}\n")
        print("Usage: xilinx_c1100_mistex.py smoke [--build]")
