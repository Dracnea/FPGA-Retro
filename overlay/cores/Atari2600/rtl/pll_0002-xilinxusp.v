// Atari 2600 core PLL "pll_0002", UltraScale+ variant -- MMCME4_ADV.
//
// Same module name, ports and output frequencies as the Altera pll_0002 the
// core's rtl/pll.v wraps. Reference clock is MiSTer's CLK_50M.
//   refclk 50 MHz / DIVCLK_DIVIDE 4 -> PFD 12.5 MHz; CLKFBOUT_MULT_F 68.75 -> VCO 859.375 MHz
//   (target 240 x 3.579545 = 859.0909 MHz; every output is +0.033 % fast -- the exact
//   ratio needs M = 68.727, and the MMCM steps M by 0.125). The NTSC colour clock
//   itself needs a divide of 240, past the MMCM's 128, so it is a BUFGCE_DIV of the
//   8x clock. NOTE (unverified): +0.033 % is a fit-time clock; a board build should
//   revisit whether the core's video timing tolerates it (real crystals are +-0.005 %).
//   outclk_0 = VCO/30 = 28.6458 MHz (28.63636)   outclk_1 = outclk_0/8 = 3.5807 MHz (3.579545)
//   outclk_2 = VCO/10 = 85.9375 MHz (85.90908)
// SPDX-License-Identifier: BSD-2-Clause
`timescale 1ns/10ps
module pll_0002 (
	input  wire refclk,
	input  wire rst,
	output wire outclk_0,
	output wire outclk_1,
	output wire outclk_2,
	output wire locked
);
	wire feedback;
	wire c0, c1;
	MMCME4_ADV #(
		.BANDWIDTH("OPTIMIZED"),
		.CLKIN1_PERIOD(20.000),
		.DIVCLK_DIVIDE(4),
		.CLKFBOUT_MULT_F(68.75),
		.CLKOUT0_DIVIDE_F(30.0),
		.CLKOUT0_PHASE(0.0),
		.CLKOUT1_DIVIDE(10),
		.CLKOUT1_PHASE(0.0),
		.REF_JITTER1(0.01),
		.STARTUP_WAIT("FALSE")
	) pll_0002_inst (
		.CLKFBIN(feedback), .CLKFBOUT(feedback),
		.CLKIN1(refclk), .CLKIN2(1'b0), .CLKINSEL(1'b1),
		.PWRDWN(1'b0), .RST(rst), .LOCKED(locked),
		.DADDR(7'd0), .DCLK(1'b0), .DEN(1'b0), .DI(16'd0), .DWE(1'b0),
		.PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0), .CDDCREQ(1'b0),
		.CLKOUT0(c0),
		.CLKOUT1(c1)
	);
	BUFG bufg0 (.I(c0), .O(outclk_0));
	BUFGCE_DIV #(.BUFGCE_DIVIDE(8)) bufgdiv1 (.I(c0), .CE(1'b1), .CLR(1'b0), .O(outclk_1));
	BUFG bufg2 (.I(c1), .O(outclk_2));
endmodule
