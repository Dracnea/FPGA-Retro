// NES core PLL, UltraScale+ variant.
//
// Drop-in replacement for rtl/pll_0002-xilinx7.v, which targets Series-7 and
// instantiates MMCME2_ADV. UltraScale+ (VU33P / VU35P) has no MMCME2; the
// equivalent primitive is MMCME4_ADV.
//
// PORT AND FREQUENCY CONTRACT IS UNCHANGED. Same module name, same ports, same
// three output frequencies, same CLKOUT1 phase. A core cannot tell the
// difference, which is the point -- this file is selected by MiSTeX.yaml's
// `vivado:` source list, not by editing any core.
//
//   refclk 50 MHz, DIVCLK_DIVIDE=1  -> PFD 50 MHz
//   CLKFBOUT_MULT_F=24.0            -> VCO 1200 MHz  (MMCME4 -2 range: 800-1600)
//   outclk_0 = VCO/14 = 85.714 MHz  (SDRAM domain)
//   outclk_1 = VCO/28 = 42.857 MHz  (system clock), phase -67.494 deg
//   outclk_2 = VCO/56 = 21.429 MHz  (NES master clock, nominal 21.477 NTSC)
//
// The VCO is deliberately identical to the Series-7 version so that every
// output divider and the CLKOUT1 phase carry over unchanged. CLKOUT1's phase is
// not cosmetic -- it is the SDRAM capture phase -- so preserving it rather than
// recomputing it is what keeps this a port and not a redesign.
//
// REFERENCE CLOCK: this expects 50 MHz on `refclk`, exactly as the Series-7
// version does, because MiSTer's sys_top hands cores CLK_50M. The FK33's only
// oscillator is 200 MHz, so the board-level CRG must derive 50 MHz and feed it
// here. That division belongs in the CRG, not in this file, so that this shim
// stays valid for any UltraScale+ board regardless of its oscillator.
//
// RUNTIME DRP RECONFIGURATION -- READ BEFORE RELYING ON IT:
// The DRP port is wired through exactly as the Series-7 shim wires it, but
// MMCME2_ADV and MMCME4_ADV DO NOT SHARE A DRP REGISTER MAP. A reconfiguration
// sequence computed for MMCME2 will write the wrong counters here. On the
// Vivado path the NES core does not list altera_pll_reconfig_* among its
// sources, so the PLL is static and this is inert -- fine as-is. Any core that
// genuinely retunes its pixel clock at runtime needs an UltraScale+-aware
// sequencer. Xilinx XAPP888's UltraScale+ MMCM variant
// (mmcm_pll_drp_func_us_plus_mmcm.vh) is the correct basis for one; wire that
// in rather than writing a register map from scratch.

`timescale 1ns/10ps

module pll_0002 (
	input  wire        refclk,
	input  wire        rst,
	output wire        outclk_0,
	output wire        outclk_1,
	output wire        outclk_2,
	output wire        locked,
	input  wire [63:0] reconfig_to_pll,
	output wire [63:0] reconfig_from_pll
);

	wire [15:0] din;
	wire [6:0]  daddr;
	wire [15:0] dout;
	wire        den;
	wire        dwe;
	wire        rst_mmcm;
	wire        drdy;
	wire        dclk;

	// Reconfig bus decode -- bit-for-bit identical to the Series-7 shim, so the
	// Altera-shaped interface the core drives is unchanged.
	assign reconfig_from_pll[15:0] = dout;
	assign reconfig_from_pll[16]   = drdy;
	assign reconfig_from_pll[17]   = locked;
	assign reconfig_from_pll[63:18] = 0;

	assign din      = reconfig_to_pll[15:0];
	assign daddr    = reconfig_to_pll[22:16];
	assign den      = reconfig_to_pll[23];
	assign dwe      = reconfig_to_pll[24];
	assign rst_mmcm = reconfig_to_pll[25];
	assign dclk     = reconfig_to_pll[26];

	wire feedback;
	wire clkout0;
	wire clkout1;
	wire clkout2;

	MMCME4_ADV #(
		.BANDWIDTH            ("OPTIMIZED"),
		.CLKOUT4_CASCADE      ("FALSE"),
		.COMPENSATION         ("AUTO"),
		.STARTUP_WAIT         ("FALSE"),
		.DIVCLK_DIVIDE        (1),
		.CLKFBOUT_MULT_F      (24.000),
		.CLKFBOUT_PHASE       (0.000),
		.CLKFBOUT_USE_FINE_PS ("FALSE"),
		.CLKIN1_PERIOD        (20.000),   // 50 MHz
		.CLKOUT0_DIVIDE_F     (14.000),
		.CLKOUT0_PHASE        (0.000),
		.CLKOUT0_DUTY_CYCLE   (0.500),
		.CLKOUT0_USE_FINE_PS  ("FALSE"),
		.CLKOUT1_DIVIDE       (28),
		.CLKOUT1_PHASE        (-67.494),  // SDRAM capture phase -- do not alter
		.CLKOUT1_DUTY_CYCLE   (0.500),
		.CLKOUT1_USE_FINE_PS  ("FALSE"),
		.CLKOUT2_DIVIDE       (56),
		.CLKOUT2_PHASE        (0.000),
		.CLKOUT2_DUTY_CYCLE   (0.500),
		.CLKOUT2_USE_FINE_PS  ("FALSE"),
		.REF_JITTER1          (0.010)
	) pll_0002_inst (
		.CLKFBIN       (feedback),
		.CLKIN1        (refclk),
		.CLKIN2        (1'b0),
		.CLKINSEL      (1'b1),
		.PWRDWN        (1'b0),
		.RST           (rst | rst_mmcm),
		.CLKFBOUT      (feedback),
		.CLKFBOUTB     (),
		.CLKOUT0       (clkout0),
		.CLKOUT0B      (),
		.CLKOUT1       (clkout1),
		.CLKOUT1B      (),
		.CLKOUT2       (clkout2),
		.CLKOUT2B      (),
		.CLKOUT3       (),
		.CLKOUT3B      (),
		.CLKOUT4       (),
		.CLKOUT5       (),
		.CLKOUT6       (),
		// DRP
		.DADDR         (daddr),
		.DCLK          (dclk),
		.DEN           (den),
		.DI            (din),
		.DO            (dout),
		.DRDY          (drdy),
		.DWE           (dwe),
		// UltraScale+ only: dynamic duty-cycle adjust. Unused, tied off.
		.CDDCREQ       (1'b0),
		.CDDCDONE      (),
		// Fine phase shift -- unused; phases are set by parameter above.
		.PSCLK         (1'b0),
		.PSEN          (1'b0),
		.PSINCDEC      (1'b0),
		.PSDONE        (),
		.LOCKED        (locked),
		.CLKINSTOPPED  (),
		.CLKFBSTOPPED  ()
	);

	// Vivado transforms BUFG to BUFGCE automatically on UltraScale+; synthesis
	// logs on this silicon show exactly that ("BUFG => BUFGCE: 4 instances"), so
	// BUFG is written here for parity with the Series-7 shim.
	BUFG clk_bufg0 (.I(clkout0), .O(outclk_0));
	BUFG clk_bufg1 (.I(clkout1), .O(outclk_1));
	BUFG clk_bufg2 (.I(clkout2), .O(outclk_2));

endmodule
