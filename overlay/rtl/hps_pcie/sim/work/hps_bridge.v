/* Machine-generated using Migen */
module hps_bridge(
	input ctrl_fpga_en,
	input ctrl_osd_en,
	input ctrl_io_en,
	input ctrl_core_reset,
	input ctrl_btn_osd,
	input ctrl_btn_user,
	input [15:0] din_word,
	input din_we,
	input [31:0] din2_word,
	input din2_we,
	output [15:0] dout,
	output busy,
	output io_wide,
	output reg [15:0] io_din,
	output reg io_strobe,
	output fpga_enable,
	output osd_enable,
	output io_enable,
	output core_reset,
	output [1:0] btn,
	input [15:0] io_dout,
	input io_wide_in,
	input core_clk,
	input core_rst,
	input sys_clk,
	input sys_rst
);

reg [15:0] hpsbridge = 16'd0;
reg [15:0] hpsbridge_q1 = 16'd0;
reg [1:0] hpsbridge_count = 2'd0;
reg [15:0] hpsbridge_word = 16'd0;
reg hpsbridge_req = 1'd0;
reg hpsbridge_ack = 1'd0;
wire hpsbridge_ack_s;
wire hpsbridge_idle;
wire hpsbridge_req_s;
reg [15:0] hpsbridge_dout_core = 16'd0;
reg [1:0] hpsbridge_state = 2'd0;
(* no_retiming = "true" *) reg multiregimpl00 = 1'd0;
(* no_retiming = "true" *) reg multiregimpl01 = 1'd0;
(* no_retiming = "true" *) reg multiregimpl10 = 1'd0;
(* no_retiming = "true" *) reg multiregimpl11 = 1'd0;
(* no_retiming = "true" *) reg multiregimpl20 = 1'd0;
(* no_retiming = "true" *) reg multiregimpl21 = 1'd0;
(* no_retiming = "true" *) reg [1:0] multiregimpl30 = 2'd0;
(* no_retiming = "true" *) reg [1:0] multiregimpl31 = 2'd0;
(* no_retiming = "true" *) reg multiregimpl40 = 1'd1;
(* no_retiming = "true" *) reg multiregimpl41 = 1'd1;
(* no_retiming = "true" *) reg multiregimpl50 = 1'd0;
(* no_retiming = "true" *) reg multiregimpl51 = 1'd0;
(* no_retiming = "true" *) reg multiregimpl60 = 1'd0;
(* no_retiming = "true" *) reg multiregimpl61 = 1'd0;
(* no_retiming = "true" *) reg multiregimpl70 = 1'd0;
(* no_retiming = "true" *) reg multiregimpl71 = 1'd0;

// synthesis translate_off
reg dummy_s;
initial dummy_s <= 1'd0;
// synthesis translate_on

assign hpsbridge_idle = (hpsbridge_req == hpsbridge_ack_s);
assign busy = ((hpsbridge_count != 1'd0) | (~hpsbridge_idle));
assign dout = hpsbridge_dout_core;
assign fpga_enable = multiregimpl01;
assign osd_enable = multiregimpl11;
assign io_enable = multiregimpl21;
assign btn = multiregimpl31;
assign core_reset = multiregimpl41;
assign io_wide = multiregimpl51;
assign hpsbridge_ack_s = multiregimpl61;
assign hpsbridge_req_s = multiregimpl71;

always @(posedge core_clk) begin
	io_strobe <= 1'd0;
	case (hpsbridge_state)
		1'd0: begin
			if ((hpsbridge_req_s != hpsbridge_ack)) begin
				hpsbridge_dout_core <= io_dout;
				io_din <= hpsbridge_word;
				hpsbridge_state <= 1'd1;
			end
		end
		1'd1: begin
			io_strobe <= 1'd1;
			hpsbridge_state <= 2'd2;
		end
		2'd2: begin
			hpsbridge_ack <= hpsbridge_req_s;
			hpsbridge_state <= 1'd0;
		end
	endcase
	if (core_rst) begin
		io_din <= 16'd0;
		io_strobe <= 1'd0;
		hpsbridge_ack <= 1'd0;
		hpsbridge_dout_core <= 16'd0;
		hpsbridge_state <= 2'd0;
	end
	multiregimpl00 <= ctrl_fpga_en;
	multiregimpl01 <= multiregimpl00;
	multiregimpl10 <= ctrl_osd_en;
	multiregimpl11 <= multiregimpl10;
	multiregimpl20 <= ctrl_io_en;
	multiregimpl21 <= multiregimpl20;
	multiregimpl30 <= {ctrl_btn_user, ctrl_btn_osd};
	multiregimpl31 <= multiregimpl30;
	multiregimpl40 <= ctrl_core_reset;
	multiregimpl41 <= multiregimpl40;
	multiregimpl70 <= hpsbridge_req;
	multiregimpl71 <= multiregimpl70;
end

always @(posedge sys_clk) begin
	if (din_we) begin
		if ((hpsbridge_count == 1'd0)) begin
			hpsbridge <= din_word;
			hpsbridge_count <= 1'd1;
		end else begin
			if ((hpsbridge_count == 1'd1)) begin
				hpsbridge_q1 <= din_word;
				hpsbridge_count <= 2'd2;
			end
		end
	end else begin
		if (din2_we) begin
			hpsbridge <= din2_word[15:0];
			hpsbridge_q1 <= din2_word[31:16];
			hpsbridge_count <= 2'd2;
		end else begin
			if (((hpsbridge_count != 1'd0) & hpsbridge_idle)) begin
				hpsbridge_word <= hpsbridge;
				hpsbridge <= hpsbridge_q1;
				hpsbridge_count <= (hpsbridge_count - 1'd1);
				hpsbridge_req <= (~hpsbridge_req);
			end
		end
	end
	if (sys_rst) begin
		hpsbridge <= 16'd0;
		hpsbridge_q1 <= 16'd0;
		hpsbridge_count <= 2'd0;
		hpsbridge_word <= 16'd0;
		hpsbridge_req <= 1'd0;
	end
	multiregimpl50 <= io_wide_in;
	multiregimpl51 <= multiregimpl50;
	multiregimpl60 <= hpsbridge_ack;
	multiregimpl61 <= multiregimpl60;
end

endmodule
