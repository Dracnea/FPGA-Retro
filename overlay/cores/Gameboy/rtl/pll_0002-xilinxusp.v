// Game Boy core PLL "pll_0002", UltraScale+ variant -- MMCME4_ADV.
//
// Same module name, ports and output frequencies as the Altera pll_0002 the
// core's rtl/pll.v wraps, so it is selected by MiSTeX.yaml's `vivado:` list and
// no core file changes. Reference clock is MiSTer's CLK_50M (50 MHz); the board
// CRG derives that from the card's oscillator (100 MHz C1100, 200 MHz FK33).
//
//   refclk 50 MHz / DIVCLK_DIVIDE 4 -> PFD 12.500 MHz
//   CLKFBOUT_MULT_F 107.375 -> VCO 1342.1875 MHz  (MMCME4 -2: 800-1600)
//   outclk_0 = VCO/20 = 67.109375 MHz  (clk_ram, target 67.108864 = 2^26 Hz, +0.0008 %)
//   outclk_1 = VCO/40 = 33.554688 MHz  (clk_sys, target 33.554432 = 2^25 Hz, +0.0008 %)
// This PLL has no reconfig interface upstream (the core never retunes it), so
// the MMCM's DRP port is tied off.
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
		.CLKFBOUT_MULT_F(107.375),
		.CLKOUT0_DIVIDE_F(20.0),
		.CLKOUT0_PHASE(0.0),
		.CLKOUT1_DIVIDE(40),
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
