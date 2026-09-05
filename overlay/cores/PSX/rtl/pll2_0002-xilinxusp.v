// PSX core PLL "pll2_0002", UltraScale+ variant -- MMCME4_ADV.
//
// Same module name, ports and output frequencies as the Altera pll_0002 the
// core instantiates, so it is selected by MiSTeX.yaml's `vivado:` list and no
// core file changes. Reference clock is MiSTer's CLK_50M (50 MHz); the board
// CRG derives that from the card's oscillator (100 MHz C1100, 200 MHz FK33).
//
//   refclk 50 MHz / DIVCLK_DIVIDE 5 -> PFD 10.000 MHz
//   CLKFBOUT_MULT_F 107.375 -> VCO 1073.7500 MHz  (MMCME4 -2: 800-1600)
//   outclk_0 = VCO/20     =    53.6875 MHz  (target 53.693175, -0.011 %)
// Largest frequency error against the Altera targets: 0.011 %.
// The reconfig bus is decoded exactly as MiSTeX's Series-7 shims decode it, but
// MMCME2 and MMCME4 do not share a DRP register map: a sequence computed for
// MMCME2 writes the wrong counters here. On the Vivado path the Altera
// reconfig IP is not in the source list, so the PLL is static and this is
// inert. Runtime retuning needs an UltraScale+-aware sequencer (XAPP888's
// mmcm_pll_drp_func_us_plus_mmcm.vh).
// SPDX-License-Identifier: BSD-2-Clause
`timescale 1ns/10ps
module pll2_0002 (
	input  wire        refclk,
	input  wire        rst,
	output wire        outclk_0,
	output wire        locked
,
	input  wire [63:0] reconfig_to_pll,
	output wire [63:0] reconfig_from_pll
);

	wire [15:0] din   = reconfig_to_pll[15:0];
	wire [6:0]  daddr = reconfig_to_pll[22:16];
	wire        den   = reconfig_to_pll[23];
	wire        dwe   = reconfig_to_pll[24];
	wire        dclk  = reconfig_to_pll[26];
	wire [15:0] dout;
	wire        drdy;
	assign reconfig_from_pll[15:0]  = dout;
	assign reconfig_from_pll[16]    = drdy;
	assign reconfig_from_pll[17]    = locked;
	assign reconfig_from_pll[63:18] = 0;
	wire feedback;
	wire clkout0;

	MMCME4_ADV #(
		.BANDWIDTH("OPTIMIZED"),
		.CLKIN1_PERIOD(20.000),
		.DIVCLK_DIVIDE(5),
		.CLKFBOUT_MULT_F(107.375),
		.CLKOUT0_DIVIDE_F(20.0),
		.CLKOUT0_PHASE(0.0),
		.REF_JITTER1(0.01),
		.STARTUP_WAIT("FALSE")
	) pll2_0002_inst (
		.CLKFBIN(feedback), .CLKFBOUT(feedback),
		.CLKIN1(refclk), .CLKIN2(1'b0), .CLKINSEL(1'b1),
		.PWRDWN(1'b0), .RST(rst), .LOCKED(locked),
		.DADDR(daddr), .DCLK(dclk), .DEN(den), .DI(din), .DWE(dwe), .DO(dout), .DRDY(drdy),
		.PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0), .CDDCREQ(1'b0),
		.CLKOUT0(clkout0)
	);

	BUFG bufg0 (.I(clkout0), .O(outclk_0));
endmodule
