// C64 core PLL, UltraScale+ variant of MiSTeX's rtl/pll-xilinx7.v.
// Same module name, ports and output frequencies; PLLE2_ADV (Series-7) becomes
// MMCME4_ADV, with the same VCOs so every divider carries over unchanged.
//   inst1: refclk 50 MHz x24 / 1 -> VCO 1200 MHz; c0 = VCO/25 = 48 MHz
//   inst2: refclk 50 MHz x53 / 2 -> VCO 1325 MHz; c1 = VCO/21 = 63.095 MHz, c2 = VCO/42 = 31.548 MHz
// MMCME4 -2 VCO range is 800-1600 MHz; both are inside it.  No DRP.
`timescale 1 ps / 1 ps

module pll (
	input  wire areset,
	input  wire inclk0,
	output wire c0,
	output wire c1,
	output wire c2,
	output wire locked
);
	wire feedback1, feedback2;
	wire outclk_0_bufg, outclk_1_bufg, outclk_2_bufg;
	wire locked1, locked2;

	MMCME4_ADV #(
		.BANDWIDTH("OPTIMIZED"), .COMPENSATION("AUTO"), .STARTUP_WAIT("FALSE"),
		.CLKIN1_PERIOD(20.0), .REF_JITTER1(0.01),
		.DIVCLK_DIVIDE(1), .CLKFBOUT_MULT_F(24.000), .CLKFBOUT_PHASE(0.0),
		.CLKOUT0_DIVIDE_F(25.000), .CLKOUT0_PHASE(0.0), .CLKOUT0_DUTY_CYCLE(0.5)
	) mmcm_inst1 (
		.CLKFBIN(feedback1), .CLKIN1(inclk0), .CLKIN2(1'b0), .CLKINSEL(1'b1),
		.PWRDWN(1'b0), .RST(areset), .CLKFBOUT(feedback1), .CLKFBOUTB(),
		.CLKOUT0(outclk_0_bufg), .CLKOUT0B(), .CLKOUT1(), .CLKOUT1B(), .CLKOUT2(), .CLKOUT2B(),
		.CLKOUT3(), .CLKOUT3B(), .CLKOUT4(), .CLKOUT5(), .CLKOUT6(),
		.DADDR(7'd0), .DCLK(1'b0), .DEN(1'b0), .DI(16'd0), .DO(), .DRDY(), .DWE(1'b0),
		.CDDCREQ(1'b0), .CDDCDONE(), .PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0), .PSDONE(),
		.LOCKED(locked1), .CLKINSTOPPED(), .CLKFBSTOPPED()
	);

	MMCME4_ADV #(
		.BANDWIDTH("OPTIMIZED"), .COMPENSATION("AUTO"), .STARTUP_WAIT("FALSE"),
		.CLKIN1_PERIOD(20.0), .REF_JITTER1(0.01),
		.DIVCLK_DIVIDE(2), .CLKFBOUT_MULT_F(53.000), .CLKFBOUT_PHASE(0.0),
		.CLKOUT0_DIVIDE_F(21.000), .CLKOUT0_PHASE(0.0), .CLKOUT0_DUTY_CYCLE(0.5),
		.CLKOUT1_DIVIDE(42), .CLKOUT1_PHASE(0.0), .CLKOUT1_DUTY_CYCLE(0.5)
	) mmcm_inst2 (
		.CLKFBIN(feedback2), .CLKIN1(inclk0), .CLKIN2(1'b0), .CLKINSEL(1'b1),
		.PWRDWN(1'b0), .RST(areset), .CLKFBOUT(feedback2), .CLKFBOUTB(),
		.CLKOUT0(outclk_1_bufg), .CLKOUT0B(), .CLKOUT1(outclk_2_bufg), .CLKOUT1B(), .CLKOUT2(), .CLKOUT2B(),
		.CLKOUT3(), .CLKOUT3B(), .CLKOUT4(), .CLKOUT5(), .CLKOUT6(),
		.DADDR(7'd0), .DCLK(1'b0), .DEN(1'b0), .DI(16'd0), .DO(), .DRDY(), .DWE(1'b0),
		.CDDCREQ(1'b0), .CDDCDONE(), .PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0), .PSDONE(),
		.LOCKED(locked2), .CLKINSTOPPED(), .CLKFBSTOPPED()
	);

	BUFG outclk_bufg_0 (.I(outclk_0_bufg), .O(c0));
	BUFG outclk_bufg_1 (.I(outclk_1_bufg), .O(c1));
	BUFG outclk_bufg_2 (.I(outclk_2_bufg), .O(c2));
	assign locked = locked1 & locked2;
endmodule
