// Atari Lynx core PLL "pll_0002", UltraScale+ variant -- MMCME4_ADV.
//
// Same module name, ports and frequencies as the Altera pll_0002 the core's rtl/pll.v wraps.
//   refclk 50 MHz / DIVCLK_DIVIDE 5 -> PFD 10 MHz; CLKFBOUT_MULT_F 128 -> VCO 1280 MHz
//   outclk_0 = outclk_1 = VCO/20 = 64.000 MHz exactly (upstream: two 64 MHz outputs, no phase shift)
// SPDX-License-Identifier: BSD-2-Clause
`timescale 1ns/10ps
module pll_0002 (
	input  wire refclk,
	input  wire rst,
	output wire outclk_0,
	output wire outclk_1,
	output wire locked
);
	wire feedback;
	wire c0, c1;
	MMCME4_ADV #(
		.BANDWIDTH("OPTIMIZED"),
		.CLKIN1_PERIOD(20.000),
		.DIVCLK_DIVIDE(5),
		.CLKFBOUT_MULT_F(128.0),
		.CLKOUT0_DIVIDE_F(20.0),
		.CLKOUT0_PHASE(0.0),
		.CLKOUT1_DIVIDE(20),
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
	BUFG bufg1 (.I(c1), .O(outclk_1));
endmodule
