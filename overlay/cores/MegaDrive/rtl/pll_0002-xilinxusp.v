// Mega Drive core PLL "pll_0002", UltraScale+ variant -- MMCME4_ADV.
//
// Same module name and ports as the Altera pll_0002 that rtl/pll.v wraps.
// Reference is MiSTer's CLK_50M.
//   refclk 50 MHz / DIVCLK_DIVIDE 1 -> PFD 50 MHz, CLKFBOUT_MULT_F 29 -> VCO 1450 MHz
//   outclk_0 = VCO/27   = 53.7037 MHz  (clk_sys, target 53.693175, +0.02 %)
//   outclk_1 = VCO/13.5 = 107.4074 MHz (clk_ram, target 107.386350, +0.02 %)
// The core's PLL reconfig ports (reconfig_to_pll/from_pll) are accepted and
// ignored: the core never retunes this PLL at run time.
// SPDX-License-Identifier: BSD-2-Clause
`timescale 1ns/10ps
module pll_0002 (
	input  wire refclk,
	input  wire rst,
	output wire outclk_0,
	output wire outclk_1,
	output wire locked,
	input  wire [63:0] reconfig_to_pll,
	output wire [63:0] reconfig_from_pll
);
	wire feedback, clkout0, clkout1;
	assign reconfig_from_pll = 64'd0;

	MMCME4_ADV #(
		.BANDWIDTH("OPTIMIZED"),
		.CLKIN1_PERIOD(20.000),
		.DIVCLK_DIVIDE(1),
		.CLKFBOUT_MULT_F(29.0),
		.CLKOUT0_DIVIDE_F(13.5),
		.CLKOUT0_PHASE(0.0),
		.CLKOUT1_DIVIDE(27),
		.CLKOUT1_PHASE(0.0),
		.REF_JITTER1(0.01),
		.STARTUP_WAIT("FALSE")
	) pll_0002_inst (
		.CLKFBIN(feedback), .CLKFBOUT(feedback),
		.CLKIN1(refclk), .CLKIN2(1'b0), .CLKINSEL(1'b1),
		.PWRDWN(1'b0), .RST(rst), .LOCKED(locked),
		.DADDR(7'd0), .DCLK(1'b0), .DEN(1'b0), .DI(16'd0), .DWE(1'b0),
		.PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0), .CDDCREQ(1'b0),
		.CLKOUT0(clkout1),
		.CLKOUT1(clkout0)
	);

	BUFG bufg0 (.I(clkout0), .O(outclk_0));
	BUFG bufg1 (.I(clkout1), .O(outclk_1));
endmodule
