// Amstrad CPC core PLL, UltraScale+ variant of MiSTeX's rtl/pll_0002-xilinx7.v.
// Same ports and frequency; MMCME2_ADV becomes MMCME4_ADV with the same VCO.
//   refclk 50 MHz x20 / 1 -> VCO 1000 MHz; outclk_0 = VCO/15.625 = 64 MHz
`timescale 1ns/10ps
module pll_0002 (
	input  wire refclk,
	input  wire rst,
	output wire outclk_0,
	output wire locked
);
	wire feedback, clkout0;
	MMCME4_ADV #(
		.BANDWIDTH("OPTIMIZED"), .COMPENSATION("AUTO"), .STARTUP_WAIT("FALSE"),
		.CLKIN1_PERIOD(20.0), .REF_JITTER1(0.01),
		.DIVCLK_DIVIDE(1), .CLKFBOUT_MULT_F(20.000), .CLKFBOUT_PHASE(0.0),
		.CLKOUT0_DIVIDE_F(15.625), .CLKOUT0_PHASE(0.0), .CLKOUT0_DUTY_CYCLE(0.5)
	) pll_0002_inst (
		.CLKFBIN(feedback), .CLKIN1(refclk), .CLKIN2(1'b0), .CLKINSEL(1'b1),
		.PWRDWN(1'b0), .RST(rst), .CLKFBOUT(feedback), .CLKFBOUTB(),
		.CLKOUT0(clkout0), .CLKOUT0B(), .CLKOUT1(), .CLKOUT1B(), .CLKOUT2(), .CLKOUT2B(),
		.CLKOUT3(), .CLKOUT3B(), .CLKOUT4(), .CLKOUT5(), .CLKOUT6(),
		.DADDR(7'd0), .DCLK(1'b0), .DEN(1'b0), .DI(16'd0), .DO(), .DRDY(), .DWE(1'b0),
		.CDDCREQ(1'b0), .CDDCDONE(), .PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0), .PSDONE(),
		.LOCKED(locked), .CLKINSTOPPED(), .CLKFBSTOPPED()
	);
	BUFG clk_bufg0 (.I(clkout0), .O(outclk_0));
endmodule
