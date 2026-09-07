// Minimig-AGA core PLL, UltraScale+ variant of MiSTeX's rtl/pll_0002-xilinx7.v.
// Same ports and frequencies; MMCME2_ADV becomes MMCME4_ADV with the same VCO.
//   refclk 50 MHz x27.25 / 1 -> VCO 1362.5 MHz
//   outclk_0 = VCO/12 = 113.542 MHz (SDRAM / DDRAM domain), outclk_1 = VCO/48 = 28.385 MHz (system)
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
		.BANDWIDTH("OPTIMIZED"), .COMPENSATION("AUTO"), .STARTUP_WAIT("FALSE"),
		.CLKIN1_PERIOD(20.0), .REF_JITTER1(0.01),
		.DIVCLK_DIVIDE(1), .CLKFBOUT_MULT_F(27.250), .CLKFBOUT_PHASE(0.0),
		.CLKOUT0_DIVIDE_F(12.000), .CLKOUT0_PHASE(0.0), .CLKOUT0_DUTY_CYCLE(0.5),
		.CLKOUT1_DIVIDE(48), .CLKOUT1_PHASE(0.0), .CLKOUT1_DUTY_CYCLE(0.5)
	) pll_0002_inst (
		.CLKFBIN(feedback), .CLKIN1(refclk), .CLKIN2(1'b0), .CLKINSEL(1'b1),
		.PWRDWN(1'b0), .RST(rst), .CLKFBOUT(feedback), .CLKFBOUTB(),
		.CLKOUT0(clkout0), .CLKOUT0B(), .CLKOUT1(clkout1), .CLKOUT1B(), .CLKOUT2(), .CLKOUT2B(),
		.CLKOUT3(), .CLKOUT3B(), .CLKOUT4(), .CLKOUT5(), .CLKOUT6(),
		.DADDR(7'd0), .DCLK(1'b0), .DEN(1'b0), .DI(16'd0), .DO(), .DRDY(), .DWE(1'b0),
		.CDDCREQ(1'b0), .CDDCDONE(), .PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0), .PSDONE(),
		.LOCKED(locked), .CLKINSTOPPED(), .CLKFBSTOPPED()
	);
	BUFG clk_bufg0 (.I(clkout0), .O(outclk_0));
	BUFG clk_bufg1 (.I(clkout1), .O(outclk_1));
endmodule
