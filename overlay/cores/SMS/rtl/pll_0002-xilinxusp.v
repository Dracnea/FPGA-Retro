// Master System core PLL "pll_0002", UltraScale+ variant -- MMCME4_ADV.
// Same ports as MiSTeX's rtl/pll_0002-xilinx7.v (which it replaces on these parts).
//   refclk 50 MHz, CLKFBOUT_MULT_F 29 -> VCO 1450 MHz, outclk_0 = VCO/27 = 53.7037 MHz
//   (target 53.693175, +0.02 %; the Series-7 shim uses the same 29/27 ratio)
// SPDX-License-Identifier: BSD-2-Clause
`timescale 1ns/10ps
module pll_0002 (
	input  wire refclk,
	input  wire rst,
	output wire outclk_0,
	output wire locked
);
	wire feedback, clkout0;

	MMCME4_ADV #(
		.BANDWIDTH("OPTIMIZED"),
		.CLKIN1_PERIOD(20.000),
		.DIVCLK_DIVIDE(1),
		.CLKFBOUT_MULT_F(29.0),
		.CLKOUT0_DIVIDE_F(27.0),
		.CLKOUT0_PHASE(0.0),
		.REF_JITTER1(0.01),
		.STARTUP_WAIT("FALSE")
	) pll_0002_inst (
		.CLKFBIN(feedback), .CLKFBOUT(feedback),
		.CLKIN1(refclk), .CLKIN2(1'b0), .CLKINSEL(1'b1),
		.PWRDWN(1'b0), .RST(rst), .LOCKED(locked),
		.DADDR(7'd0), .DCLK(1'b0), .DEN(1'b0), .DI(16'd0), .DWE(1'b0),
		.PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0), .CDDCREQ(1'b0),
		.CLKOUT0(clkout0)
	);

	BUFG bufg0 (.I(clkout0), .O(outclk_0));
endmodule
