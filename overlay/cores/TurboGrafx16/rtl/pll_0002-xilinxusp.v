// TurboGrafx-16 core PLL "pll_0002", UltraScale+ variant -- MMCME4_ADV.
//
// Same module name and ports as the Altera pll_0002 that rtl/pll.v wraps.
//   refclk 50 MHz / DIVCLK_DIVIDE 2 -> PFD 25 MHz, CLKFBOUT_MULT_F 41.25 -> VCO 1031.25 MHz
//   outclk_0 = VCO/12 = 85.9375 MHz  (clk_ram, target 85.909090, +0.033 %)
//   outclk_1 = VCO/24 = 42.96875 MHz (clk_sys, target 42.954545, +0.033 %)
// SPDX-License-Identifier: BSD-2-Clause
`timescale 1ns/10ps
module pll_0002 (
	input  wire refclk,
	input  wire rst,
	output wire outclk_0,
	output wire outclk_1,
	output wire locked
);
	wire feedback, clkout0, clkout1;

	MMCME4_ADV #(
		.BANDWIDTH("OPTIMIZED"),
		.CLKIN1_PERIOD(20.000),
		.DIVCLK_DIVIDE(2),
		.CLKFBOUT_MULT_F(41.25),
		.CLKOUT0_DIVIDE_F(12.0),
		.CLKOUT0_PHASE(0.0),
		.CLKOUT1_DIVIDE(24),
		.CLKOUT1_PHASE(0.0),
		.REF_JITTER1(0.01),
		.STARTUP_WAIT("FALSE")
	) pll_0002_inst (
		.CLKFBIN(feedback), .CLKFBOUT(feedback),
		.CLKIN1(refclk), .CLKIN2(1'b0), .CLKINSEL(1'b1),
		.PWRDWN(1'b0), .RST(rst), .LOCKED(locked),
		.DADDR(7'd0), .DCLK(1'b0), .DEN(1'b0), .DI(16'd0), .DWE(1'b0),
		.PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0), .CDDCREQ(1'b0),
		.CLKOUT0(clkout0),
		.CLKOUT1(clkout1)
	);

	BUFG bufg0 (.I(clkout0), .O(outclk_0));
	BUFG bufg1 (.I(clkout1), .O(outclk_1));
endmodule
