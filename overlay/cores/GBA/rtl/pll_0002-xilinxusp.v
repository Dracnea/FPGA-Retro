// GBA core PLL "pll_0002", UltraScale+ variant -- MMCME4_ADV.
//
// Same module name, ports and output frequencies as the Altera pll_0002 the
// core instantiates, so it is selected by MiSTeX.yaml's `vivado:` list and no
// core file changes. Reference clock is MiSTer's CLK_50M (50 MHz); the board
// CRG derives that from the card's oscillator (100 MHz C1100, 200 MHz FK33).
//
//   refclk 50 MHz / DIVCLK_DIVIDE 5 -> PFD 10.000 MHz
//   CLKFBOUT_MULT_F 120.75 -> VCO 1207.5000 MHz  (MMCME4 -2: 800-1600)
//   outclk_0 = VCO/12     =   100.6250 MHz  (target 100.663296, -0.038 %)
//   outclk_1 = VCO/24     =    50.3125 MHz  (target 50.331648, -0.038 %)
// Largest frequency error against the Altera targets: 0.038 %.
// SPDX-License-Identifier: BSD-2-Clause
`timescale 1ns/10ps
module pll_0002 (
	input  wire        refclk,
	input  wire        rst,
	output wire        outclk_0,
	output wire        outclk_1,
	output wire        locked
);

	wire [15:0] din = 16'd0; wire [6:0] daddr = 7'd0; wire den = 1'b0, dwe = 1'b0, dclk = 1'b0;
	wire [15:0] dout; wire drdy;
	wire feedback;
	wire clkout0;
	wire clkout1;

	MMCME4_ADV #(
		.BANDWIDTH("OPTIMIZED"),
		.CLKIN1_PERIOD(20.000),
		.DIVCLK_DIVIDE(5),
		.CLKFBOUT_MULT_F(120.75),
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
		.DADDR(daddr), .DCLK(dclk), .DEN(den), .DI(din), .DWE(dwe), .DO(dout), .DRDY(drdy),
		.PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0), .CDDCREQ(1'b0),
		.CLKOUT0(clkout0),
		.CLKOUT1(clkout1)
	);

	BUFG bufg0 (.I(clkout0), .O(outclk_0));
	BUFG bufg1 (.I(clkout1), .O(outclk_1));
endmodule
