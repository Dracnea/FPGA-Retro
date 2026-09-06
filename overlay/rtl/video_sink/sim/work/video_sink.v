/* Machine-generated using Migen */
module video_sink(
	input [7:0] r,
	input [7:0] g,
	input [7:0] b,
	input hs,
	input vs,
	input de,
	input ce_pix,
	input f1,
	output [127:0] data,
	output valid,
	input ready,
	input enable,
	output [11:0] width,
	output [11:0] height,
	output [31:0] frames,
	output [31:0] drops,
	input sys_clk,
	input sys_rst,
	input vid_clk,
	input vid_rst
);

wire asyncfifo_we;
wire asyncfifo_writable;
wire asyncfifo_re;
wire asyncfifo_readable;
wire [127:0] asyncfifo_din;
wire [127:0] asyncfifo_dout;
wire graycounter0_ce;
(* no_retiming = "true" *) reg [6:0] graycounter0_q = 7'd0;
wire [6:0] graycounter0_q_next;
reg [6:0] graycounter0_q_binary = 7'd0;
reg [6:0] graycounter0_q_next_binary;
wire graycounter1_ce;
(* no_retiming = "true" *) reg [6:0] graycounter1_q = 7'd0;
wire [6:0] graycounter1_q_next;
reg [6:0] graycounter1_q_binary = 7'd0;
reg [6:0] graycounter1_q_next_binary;
wire [6:0] produce_rdomain;
wire [6:0] consume_wdomain;
wire [5:0] wrport_adr;
wire [127:0] wrport_dat_r;
wire wrport_we;
wire [127:0] wrport_dat_w;
wire [5:0] rdport_adr;
wire [127:0] rdport_dat_r;
wire enable_v;
reg vs_prev = 1'd0;
reg de_prev = 1'd0;
reg vs_seen = 1'd0;
reg [11:0] x = 12'd0;
reg [11:0] y = 12'd0;
reg [11:0] w_meas = 12'd0;
reg [11:0] h_meas = 12'd0;
reg measured = 1'd0;
reg [31:0] frame_no = 32'd0;
reg [31:0] drops_v = 32'd0;
reg [31:0] frames_v = 32'd0;
reg dropping = 1'd0;
reg in_frame = 1'd0;
reg [127:0] pack = 128'd0;
reg [1:0] npack = 2'd0;
reg push = 1'd0;
reg [127:0] push_data = 128'd0;
wire frame_start;
wire line_end;
wire frame_end;
wire pixel;
wire active;
(* no_retiming = "true" *) reg [6:0] multiregimpl00 = 7'd0;
(* no_retiming = "true" *) reg [6:0] multiregimpl01 = 7'd0;
(* no_retiming = "true" *) reg [6:0] multiregimpl10 = 7'd0;
(* no_retiming = "true" *) reg [6:0] multiregimpl11 = 7'd0;
(* no_retiming = "true" *) reg multiregimpl20 = 1'd0;
(* no_retiming = "true" *) reg multiregimpl21 = 1'd0;
(* no_retiming = "true" *) reg [11:0] multiregimpl30 = 12'd0;
(* no_retiming = "true" *) reg [11:0] multiregimpl31 = 12'd0;
(* no_retiming = "true" *) reg [11:0] multiregimpl40 = 12'd0;
(* no_retiming = "true" *) reg [11:0] multiregimpl41 = 12'd0;
(* no_retiming = "true" *) reg [31:0] multiregimpl50 = 32'd0;
(* no_retiming = "true" *) reg [31:0] multiregimpl51 = 32'd0;
(* no_retiming = "true" *) reg [31:0] multiregimpl60 = 32'd0;
(* no_retiming = "true" *) reg [31:0] multiregimpl61 = 32'd0;

// synthesis translate_off
reg dummy_s;
initial dummy_s <= 1'd0;
// synthesis translate_on

assign data = asyncfifo_dout;
assign valid = asyncfifo_readable;
assign asyncfifo_re = (asyncfifo_readable & ready);
assign frame_start = ((de & (~de_prev)) & vs_seen);
assign line_end = ((~de) & de_prev);
assign frame_end = ((vs != vs_prev) & in_frame);
assign active = ((de & ce_pix) & (in_frame | (frame_start & enable_v)));
assign pixel = (active & (~dropping));
assign asyncfifo_din = push_data;
assign asyncfifo_we = (push & asyncfifo_writable);
assign graycounter0_ce = (asyncfifo_writable & asyncfifo_we);
assign graycounter1_ce = (asyncfifo_readable & asyncfifo_re);
assign asyncfifo_writable = (((graycounter0_q[6] == consume_wdomain[6]) | (graycounter0_q[5] == consume_wdomain[5])) | (graycounter0_q[4:0] != consume_wdomain[4:0]));
assign asyncfifo_readable = (graycounter1_q != produce_rdomain);
assign wrport_adr = graycounter0_q_binary[5:0];
assign wrport_dat_w = asyncfifo_din;
assign wrport_we = graycounter0_ce;
assign rdport_adr = graycounter1_q_next_binary[5:0];
assign asyncfifo_dout = rdport_dat_r;

// synthesis translate_off
reg dummy_d;
// synthesis translate_on
always @(*) begin
	graycounter0_q_next_binary <= 7'd0;
	if (graycounter0_ce) begin
		graycounter0_q_next_binary <= (graycounter0_q_binary + 1'd1);
	end else begin
		graycounter0_q_next_binary <= graycounter0_q_binary;
	end
// synthesis translate_off
	dummy_d <= dummy_s;
// synthesis translate_on
end
assign graycounter0_q_next = (graycounter0_q_next_binary ^ graycounter0_q_next_binary[6:1]);

// synthesis translate_off
reg dummy_d_1;
// synthesis translate_on
always @(*) begin
	graycounter1_q_next_binary <= 7'd0;
	if (graycounter1_ce) begin
		graycounter1_q_next_binary <= (graycounter1_q_binary + 1'd1);
	end else begin
		graycounter1_q_next_binary <= graycounter1_q_binary;
	end
// synthesis translate_off
	dummy_d_1 <= dummy_s;
// synthesis translate_on
end
assign graycounter1_q_next = (graycounter1_q_next_binary ^ graycounter1_q_next_binary[6:1]);
assign produce_rdomain = multiregimpl01;
assign consume_wdomain = multiregimpl11;
assign enable_v = multiregimpl21;
assign width = multiregimpl31;
assign height = multiregimpl41;
assign frames = multiregimpl51;
assign drops = multiregimpl61;

always @(posedge sys_clk) begin
	graycounter1_q_binary <= graycounter1_q_next_binary;
	graycounter1_q <= graycounter1_q_next;
	if (sys_rst) begin
		graycounter1_q <= 7'd0;
		graycounter1_q_binary <= 7'd0;
	end
	multiregimpl00 <= graycounter0_q;
	multiregimpl01 <= multiregimpl00;
	multiregimpl30 <= w_meas;
	multiregimpl31 <= multiregimpl30;
	multiregimpl40 <= h_meas;
	multiregimpl41 <= multiregimpl40;
	multiregimpl50 <= frames_v;
	multiregimpl51 <= multiregimpl50;
	multiregimpl60 <= drops_v;
	multiregimpl61 <= multiregimpl60;
end

always @(posedge vid_clk) begin
	vs_prev <= vs;
	de_prev <= de;
	push <= 1'd0;
	if ((vs != vs_prev)) begin
		vs_seen <= 1'd1;
	end
	if (de) begin
		vs_seen <= 1'd0;
	end
	if (frame_end) begin
		in_frame <= 1'd0;
		if ((y != 1'd0)) begin
			h_meas <= y;
			measured <= 1'd1;
		end
		if ((npack != 1'd0)) begin
			push <= (~dropping);
			push_data <= pack;
			npack <= 1'd0;
			pack <= 1'd0;
		end
		if ((~dropping)) begin
			frames_v <= (frames_v + 1'd1);
		end
		dropping <= 1'd0;
		x <= 1'd0;
		y <= 1'd0;
	end
	if ((frame_start & enable_v)) begin
		in_frame <= 1'd1;
		x <= 1'd0;
		y <= 1'd0;
		npack <= 1'd0;
		pack <= 1'd0;
		frame_no <= (frame_no + 1'd1);
		if ((measured & asyncfifo_writable)) begin
			push <= 1'd1;
			push_data <= {31'd0, f1, frame_no, 4'd0, h_meas, 4'd0, w_meas, 32'd827150918};
			dropping <= 1'd0;
		end else begin
			dropping <= 1'd1;
			if (measured) begin
				drops_v <= (drops_v + 1'd1);
			end
		end
	end
	if (active) begin
		x <= (x + 1'd1);
	end
	if (pixel) begin
		case (npack)
			1'd0: begin
				pack[31:0] <= {8'd0, r, g, b};
			end
			1'd1: begin
				pack[63:32] <= {8'd0, r, g, b};
			end
			2'd2: begin
				pack[95:64] <= {8'd0, r, g, b};
			end
			2'd3: begin
				pack[127:96] <= {8'd0, r, g, b};
			end
		endcase
		npack <= (npack + 1'd1);
		if ((npack == 2'd3)) begin
			push <= 1'd1;
			push_data <= {8'd0, r, g, b, pack[95:0]};
			pack <= 1'd0;
		end
	end
	if ((line_end & in_frame)) begin
		y <= (y + 1'd1);
		x <= 1'd0;
		if ((x != 1'd0)) begin
			w_meas <= x;
		end
	end
	if ((((push & (~asyncfifo_writable)) & in_frame) & (~dropping))) begin
		dropping <= 1'd1;
		drops_v <= (drops_v + 1'd1);
	end
	graycounter0_q_binary <= graycounter0_q_next_binary;
	graycounter0_q <= graycounter0_q_next;
	if (vid_rst) begin
		graycounter0_q <= 7'd0;
		graycounter0_q_binary <= 7'd0;
		vs_prev <= 1'd0;
		de_prev <= 1'd0;
		vs_seen <= 1'd0;
		x <= 12'd0;
		y <= 12'd0;
		w_meas <= 12'd0;
		h_meas <= 12'd0;
		measured <= 1'd0;
		frame_no <= 32'd0;
		drops_v <= 32'd0;
		frames_v <= 32'd0;
		dropping <= 1'd0;
		in_frame <= 1'd0;
		pack <= 128'd0;
		npack <= 2'd0;
		push <= 1'd0;
		push_data <= 128'd0;
	end
	multiregimpl10 <= graycounter1_q;
	multiregimpl11 <= multiregimpl10;
	multiregimpl20 <= enable;
	multiregimpl21 <= multiregimpl20;
end

reg [127:0] storage[0:63];
reg [5:0] memadr;
reg [5:0] memadr_1;
always @(posedge vid_clk) begin
	if (wrport_we)
		storage[wrport_adr] <= wrport_dat_w;
	memadr <= wrport_adr;
end

always @(posedge sys_clk) begin
	memadr_1 <= rdport_adr;
end

assign wrport_dat_r = storage[memadr];
assign rdport_dat_r = storage[memadr_1];

endmodule
