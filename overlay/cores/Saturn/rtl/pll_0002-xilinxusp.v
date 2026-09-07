// Sega Saturn core PLL "pll_0002", UltraScale+ variant -- MMCME4_ADV.
//
// Same module name, ports and output frequencies as the Altera pll_0002 the
// core's pll.v wraps (rtl/pll/pll_0002.v: 57.272799 and 114.545598 MHz from
// 50 MHz). Selected by MiSTeX.yaml's vivado: list; no core file changes.
//
//   refclk 50 MHz / DIVCLK_DIVIDE 4 -> PFD 12.5 MHz
//   CLKFBOUT_MULT_F 91.625 -> VCO 1145.3125 MHz  (MMCME4 -2: 800-1600)
//   outclk_0 = VCO/20 = 57.2656 MHz   (clk_sys; Altera makes 57.2728, -0.012 %)
//   outclk_1 = VCO/10 = 114.5313 MHz  (clk_ram, 2x clk_sys, same phase)
// The nearest on-grid ratio to 57.2727 (= 50 x 63/55) that keeps the PFD
// above 10 MHz; the deviation is below the tolerance of the console's own
// crystal. No reconfig interface upstream; the DRP port is tied off.
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
		.DIVCLK_DIVIDE(4),
		.CLKFBOUT_MULT_F(91.625),
		.CLKOUT0_DIVIDE_F(20.0),
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
		.CLKOUT0(clkout0),
		.CLKOUT1(clkout1)
	);

	BUFG bufg0 (.I(clkout0), .O(outclk_0));
	BUFG bufg1 (.I(clkout1), .O(outclk_1));
endmodule
