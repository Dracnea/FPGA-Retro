#!/usr/bin/env python3
#
# MiSTeX board target for the SQRL Forest Kitten 33 (xcvu33p, UltraScale+ HBM).
#
# This is deliberately NOT the three-line wrapper the other boards use, e.g.
# qmtech_xc7k325t_mistex.py, which just calls build_xilinx() from
# xilinx_mistex.py. That path cannot run here, and the reason is worth stating
# plainly because it shapes the whole port:
#
#   build_xilinx() is Series-7 code. It imports S7PLL / S7MMCM / S7IDELAYCTRL,
#   VideoS7HDMIPHY, and litedram's s7ddrphy + MT41K128M16, none of which exist
#   or apply on UltraScale+. It then calls platform.request() for
#       clk50, cpu_reset, ddram, led, rgb, i2c, sdcard,
#       sdram, spdif, pmod, pmod_mode, snac, hps_spi, hps_control
#   The FK33 physically has: a 200 MHz oscillator, PCIe, one I2C bus, 7 LEDs.
#   Every other request above would raise on this platform.
#
# So this file supplies the parts that CAN be written today -- the UltraScale+
# clock generator, correctly derived from the board's only oscillator -- and is
# explicit about the parts that cannot, rather than half-building something that
# appears to work and does not.
#
# SPDX-License-Identifier: BSD-2-Clause

import sys
from os.path import join, dirname, abspath

sys.path.insert(0, join(dirname(abspath(__file__)), "..", "platforms"))

from migen import *
from litex.gen.fhdl.module import LiteXModule
from litex.soc.cores.clock import USPMMCM

import sqrl_fk33


# Clock generation ---------------------------------------------------------------------------------

class _CRG(LiteXModule):
    """UltraScale+ clock generator for the FK33.

    The FK33 has a single 200 MHz LVDS oscillator on BC26/BC27 and nothing else.
    Every clock a MiSTer core expects has to come from it.

    Note the 50 MHz output: MiSTer's sys_top hands cores a CLK_50M, and the core
    PLL shim (rtl/pll_0002-xilinxusp.v) is written to expect exactly that, so
    that the shim stays board-independent. The 200 -> 50 MHz division belongs
    here, in the board's CRG, and nowhere else.
    """

    def __init__(self, platform, sys_clk_freq=100e6):
        self.rst        = Signal()
        self.cd_sys     = ClockDomain()
        self.cd_clk50   = ClockDomain()   # feeds the core PLL shim as CLK_50M
        self.cd_retro   = ClockDomain()
        self.cd_retro2x = ClockDomain()

        clk200 = platform.request("clk200")

        # -2 speed grade: xcvu33p-fsvh2104-2-e. Getting this wrong silently
        # changes the VCO limits LiteX will solve within.
        self.mmcm = mmcm = USPMMCM(speedgrade=-2)
        self.comb += mmcm.reset.eq(self.rst)

        mmcm.register_clkin(clk200, 200e6)
        # margin=0 is not fussiness. LiteX defaults to +-1% and will happily
        # solve a fractional divider inside it: left at the default it picked
        # CLKOUT0_DIVIDE_F=15.875 for a "100 MHz" sys clock, i.e. 100.79 MHz.
        # A retro core's clocks are divided down from these to hit exact console
        # timings, so an 0.8% error at the top compounds into wrong frame and
        # audio rates. At VCO=1600 MHz every clock below is an integer divide.
        mmcm.create_clkout(self.cd_sys,     sys_clk_freq, margin=0)
        mmcm.create_clkout(self.cd_clk50,   50e6,         margin=0)
        mmcm.create_clkout(self.cd_retro,   50e6,         margin=0)
        mmcm.create_clkout(self.cd_retro2x, 100e6,        margin=0)

        platform.add_period_constraint(clk200, 1e9/200e6)


# What is still missing ----------------------------------------------------------------------------

# Ordered by what blocks what. (1) and (2) are done; this list is the rest.
MISSING = {
    "video sink": (
        "The FK33 has no display output of any kind -- no HDMI, DP, VGA, and no "
        "expansion header to add one. VideoS7HDMIPHY has no counterpart here. "
        "The core's VGA_* output must be written into a framebuffer and DMA'd to "
        "the host over PCIe (LitePCIe USPHBMPCIEPHY), then presented by a host "
        "application. This is new authorship, and it is the critical path."
    ),
    "host interface (HPS replacement)": (
        "MiSTeX replaces MiSTer's ARM HPS with an external SBC over SPIBone "
        "(hps_spi / hps_control pins). The FK33 has no such pins exposed. The "
        "natural substitute is the host PC over the same PCIe link that carries "
        "video, which means hps_io's transport is re-implemented, not re-pinned."
    ),
    "core memory": (
        "No SDRAM and no DDR3; litedram's s7ddrphy and MT41K128M16 do not apply. "
        "For NES this is a non-issue and an advantage: the whole machine fits in "
        "on-chip BRAM/URAM (the vu33p has 672 BRAM tiles + 320 URAM, ~14 MB). "
        "HBM is available but is high-latency and burst-oriented, so it suits "
        "framebuffers and large ROMs rather than a CPU bus."
    ),
}


def build(coredir, core, toolchain="vivado"):
    raise NotImplementedError(
        "The FK33 MiSTeX target is not buildable yet.\n\n"
        "Done:      platforms/sqrl_fk33.py (pin map, verified lane-for-lane\n"
        "           against the vendor XDC) and the _CRG above.\n"
        "           cores/NES/rtl/pll_0002-xilinxusp.v (MMCME4_ADV shim).\n\n"
        "Blocked on:\n  - " + "\n  - ".join(
            f"{k}: {v.split('.')[0]}." for k, v in MISSING.items()
        ) + "\n\n"
        "Run smoke_test() instead to validate the platform through Vivado."
    )


def smoke_test(build_dir="build/fk33_smoke", do_build=False):
    """Smallest design that proves the platform file is correct.

    Instantiates the CRG and blinks an LED off the derived system clock. No
    core, no PCIe, no video. If this places, routes and reports a met 200 MHz
    constraint, then the pin map, the speed grade, the clock constraint and the
    Vivado path are all confirmed -- which is worth knowing before any of the
    missing pieces above are written on top of them.
    """
    from litex.soc.integration.soc_core import SoCMini
    from litex.soc.integration.builder import Builder

    platform = sqrl_fk33.Platform(toolchain="vivado")

    class SmokeSoC(SoCMini):
        def __init__(self):
            sys_clk_freq = 100e6
            SoCMini.__init__(self, platform, sys_clk_freq, ident="FK33 platform smoke test")
            self.crg = _CRG(platform, sys_clk_freq)

            counter = Signal(27)
            self.sync += counter.eq(counter + 1)
            for i in range(7):
                self.comb += platform.request("user_led", i).eq(counter[26 - i])

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
        print("Usage: sqrl_fk33_mistex.py smoke [--build]")
