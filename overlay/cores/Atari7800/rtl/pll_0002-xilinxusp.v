// Atari 7800 core PLL "pll_0002", UltraScale+ variant -- MMCME4_ADV.
//
// Same module name, ports and output frequencies as the Altera pll_0002 the
// core's rtl/pll.v wraps. Reference clock is MiSTer's CLK_50M.
//   refclk 50 MHz / DIVCLK_DIVIDE 4 -> PFD 12.5 MHz; CLKFBOUT_MULT_F 68.75 -> VCO 859.375 MHz
//   (target 240 x 3.579545 = 859.0909 MHz; every output is +0.033 % fast -- the exact
//   ratio needs M = 68.727, and the MMCM steps M by 0.125). The NTSC colour clock
//   itself needs a divide of 240, past the MMCM's 128, so it is a BUFGCE_DIV of the
//   8x clock. NOTE (unverified): +0.033 % is a fit-time clock; a board build should
//   revisit whether the core's video timing tolerates it (real crystals are +-0.005 %).
//   outclk_0 = VCO/60 = 14.3229 MHz (14.318182)  outclk_1 = VCO/15 = 57.2917 MHz (57.272728)
//   outclk_2 = VCO/120 = 7.1615 MHz (7.159091)   outclk_3 = VCO/12 = 71.6146 MHz (71.59091)
// SPDX-License-Identifier: BSD-2-Clause
`timescale 1ns/10ps
module pll_0002 (
	input  wire refclk,
	input  wire rst,
	output wire outclk_0,
	output wire outclk_1,
	output wire outclk_2,
	output wire outclk_3,
	output wire locked
);
	wire feedback;
	wire c0, c1, c2, c3;
	MMCME4_ADV #(
		.BANDWIDTH("OPTIMIZED"),
		.CLKIN1_PERIOD(20.000),
		.DIVCLK_DIVIDE(4),
		.CLKFBOUT_MULT_F(68.75),
		.CLKOUT0_DIVIDE_F(60.0),
		.CLKOUT0_PHASE(0.0),
		.CLKOUT1_DIVIDE(15),
		.CLKOUT1_PHASE(0.0),
		.CLKOUT2_DIVIDE(120),
		.CLKOUT2_PHASE(0.0),
		.CLKOUT3_DIVIDE(12),
		.CLKOUT3_PHASE(0.0),
		.REF_JITTER1(0.01),
		.STARTUP_WAIT("FALSE")
	) pll_0002_inst (
		.CLKFBIN(feedback), .CLKFBOUT(feedback),
		.CLKIN1(refclk), .CLKIN2(1'b0), .CLKINSEL(1'b1),
		.PWRDWN(1'b0), .RST(rst), .LOCKED(locked),
		.DADDR(7'd0), .DCLK(1'b0), .DEN(1'b0), .DI(16'd0), .DWE(1'b0),
		.PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0), .CDDCREQ(1'b0),
		.CLKOUT0(c0),
		.CLKOUT1(c1),
		.CLKOUT2(c2),
		.CLKOUT3(c3)
	);
	BUFG bufg0 (.I(c0), .O(outclk_0));
	BUFG bufg1 (.I(c1), .O(outclk_1));
	BUFG bufg2 (.I(c2), .O(outclk_2));
	BUFG bufg3 (.I(c3), .O(outclk_3));
endmodule
