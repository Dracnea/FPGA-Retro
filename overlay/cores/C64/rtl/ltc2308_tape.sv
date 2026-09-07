// ltc2308_tape stub for boards without the MiSTer I/O board's LTC2308 ADC.
// sys/ltc2308.sv (the ADC driver, board-side) is left out of the emu fit;
// cores that take cassette input through it get this same-ported stand-in
// instead: no tape signal, never active. Same parameters so instantiations
// with #(.CLK_RATE(...)) still elaborate.
module ltc2308_tape #(parameter HIST_LOW = 16, HIST_HIGH = 64, ADC_RATE = 48000, CLK_RATE = 50000000, NUM_CH = 1)
(
	input         reset,
	input         clk,
	inout  [3:0]  ADC_BUS,
	output reg    dout,
	output        active,
	output        adc_sync,
	output [(NUM_CH*12)-1:0] adc_data
);
	assign ADC_BUS = 4'bzzzz;
	assign active = 1'b0;
	assign adc_sync = 1'b0;
	assign adc_data = 0;
	always @(posedge clk) dout <= 1'b0;
endmodule
