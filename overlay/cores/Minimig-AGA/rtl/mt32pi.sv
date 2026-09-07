// mt32pi stub for boards without MiSTer's USER_IO port.  sys/mt32pi.sv talks
// to an external mt32-pi synthesiser over the I/O board's USER pins and is
// left out of the emu fit as board-side; Minimig instantiates it with .* so
// a same-ported stand-in is needed: reports "not available", idle USER_OUT
// (open-drain high), MIDI receive idle high, silent I2S.
module mt32pi
(
	input             CLK_AUDIO,
	input             CLK_VIDEO,
	input             CE_PIXEL,
	input             VGA_VS,
	input             VGA_DE,
	input       [6:0] USER_IN,
	output      [6:0] USER_OUT,
	input             reset,
	input             midi_tx,
	output            midi_rx,
	output reg [15:0] mt32_i2s_r,
	output reg [15:0] mt32_i2s_l,
	output reg        mt32_available,
	input             mt32_mode_req,
	input       [1:0] mt32_rom_req,
	input       [7:0] mt32_sf_req,
	output reg  [7:0] mt32_mode,
	output reg  [7:0] mt32_rom,
	output reg  [7:0] mt32_sf,
	output reg        mt32_newmode,
	output reg        mt32_lcd_en,
	output reg        mt32_lcd_pix,
	output reg        mt32_lcd_update
);
	assign USER_OUT = 7'b1111111;
	assign midi_rx  = 1'b1;
	always @(posedge CLK_AUDIO) begin
		mt32_i2s_r <= 0; mt32_i2s_l <= 0; mt32_available <= 0;
		mt32_mode <= 0; mt32_rom <= 0; mt32_sf <= 0; mt32_newmode <= 0;
		mt32_lcd_en <= 0; mt32_lcd_pix <= 0; mt32_lcd_update <= 0;
	end
endmodule
