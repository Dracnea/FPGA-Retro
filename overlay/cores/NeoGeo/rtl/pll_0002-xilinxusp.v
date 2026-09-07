// Neo Geo core PLL "pll_0002", UltraScale+ variant -- MMCME4_ADV.
//
// Same module name and ports as MiSTeX's Series-7 rtl/pll_0002-xilinx7.v and
// the same output frequencies as the Altera pll_0002 the core's rtl/pll.v
// wraps (upstream rtl/pll/pll_0002.v: 96.671316 and 48.335658 MHz from
// 50 MHz). Selected by core-fit.py in place of the -xilinx7 file.
//
// NOTE: MiSTeX's Series-7 shim sets CLKFBOUT_MULT 30 / CLKOUT0_DIVIDE 58 and
// comments that as 96.67 MHz; 50 x 30 / 58 is 25.86 MHz. That shim runs the
// core at a quarter speed. This one does not copy it.
//
//   refclk 50 MHz / DIVCLK_DIVIDE 5 -> PFD 10 MHz
//   CLKFBOUT_MULT_F 116.0 -> VCO 1160 MHz  (MMCME4 -2: 800-1600)
//   outclk_0 = VCO/12 = 96.6667 MHz  (CLK_96M; Altera makes 96.671316, -0.005 %)
//   outclk_1 = VCO/24 = 48.3333 MHz  (CLK_48M)
// The reconfig ports exist on the Series-7 shim for the sys reconfig block
// and are unused by the core; tied off here as there.
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
		.DIVCLK_DIVIDE(5),
		.CLKFBOUT_MULT_F(116.0),
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
