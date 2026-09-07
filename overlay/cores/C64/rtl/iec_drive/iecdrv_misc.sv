
module iecdrv_sync #(parameter WIDTH = 1) 
(
	input                  clk,
	input      [WIDTH-1:0] in,
	output reg [WIDTH-1:0] out
);

reg [WIDTH-1:0] s1,s2;
always @(posedge clk) begin
	s1 <= in;
	s2 <= s1;
	if(s1 == s2) out <= s2;
end

endmodule

// -------------------------------------------------------------------------------

module iecdrv_mem #(parameter DATAWIDTH, ADDRWIDTH, INITFILE=" ")
(
	input	                     clock_a,
	input	     [ADDRWIDTH-1:0] address_a,
	input	     [DATAWIDTH-1:0] data_a,
	input	                     wren_a,
	output reg [DATAWIDTH-1:0] q_a,

	input	                     clock_b,
	input	     [ADDRWIDTH-1:0] address_b,
	input	     [DATAWIDTH-1:0] data_b,
	input	                     wren_b,
	output reg [DATAWIDTH-1:0] q_b
);

(* ram_init_file = INITFILE *) reg [DATAWIDTH-1:0] ram[1<<ADDRWIDTH];

reg                 wren_a_d;
reg [ADDRWIDTH-1:0] address_a_d;
always @(posedge clock_a) begin
	wren_a_d    <= wren_a;
	address_a_d <= address_a;
end

always @(posedge clock_a) begin
	if(wren_a_d) begin
		ram[address_a_d] <= data_a;
		q_a <= data_a;
	end else begin
		q_a <= ram[address_a_d];
	end
end

reg                 wren_b_d;
reg [ADDRWIDTH-1:0] address_b_d;
always @(posedge clock_b) begin
	wren_b_d    <= wren_b;
	address_b_d <= address_b;
end

always @(posedge clock_b) begin
	if(wren_b_d) begin
		ram[address_b_d] <= data_b;
		q_b <= data_b;
	end else begin
		q_b <= ram[address_b_d];
	end
end

endmodule

// iecdrv_bitmem, rewritten for Vivado (overlay copy; everything above this
// module is upstream's).  Upstream writes ONE BIT of a byte-wide array from
// port B (ram[addr][bit] <= data_b), which Quartus infers as a mixed-width
// RAM and Vivado 2026.1 rejects ("Unsupported RAM template").  The same
// storage as eight 1-bit-wide true dual-port banks, bank k holding bit k of
// each byte: port A reads/writes all eight at once, port B one bank.  Same
// ports, same latency (registered inputs, registered outputs), same
// read-during-write behaviour (write-first on each port, as upstream).
module iecdrv_bitmem #(parameter ADDRWIDTH)
(
	input	                     clock_a,
	input	     [ADDRWIDTH-1:0] address_a,
	input	               [7:0] data_a,
	input	                     wren_a,
	output reg           [7:0] q_a,

	input	                     clock_b,
	input	     [ADDRWIDTH+2:0] address_b,
	input	                     data_b,
	input	                     wren_b,
	output reg                 q_b
);

reg                 wren_a_d;
reg [ADDRWIDTH-1:0] address_a_d;
reg           [7:0] data_a_d;
always @(posedge clock_a) begin
	wren_a_d    <= wren_a;
	address_a_d <= address_a;
	data_a_d    <= data_a;
end

reg                 wren_b_d;
reg [ADDRWIDTH+2:0] address_b_d;
reg                 data_b_d;
always @(posedge clock_b) begin
	wren_b_d    <= wren_b;
	address_b_d <= address_b;
	data_b_d    <= data_b;
end

wire [7:0] qa_bank;
wire [7:0] qb_bank;
genvar k;
generate for (k = 0; k < 8; k = k + 1) begin : bank
	reg mem [0:(1<<ADDRWIDTH)-1];
	reg qa, qb;
	always @(posedge clock_a) begin
		if (wren_a_d) begin
			mem[address_a_d] <= data_a_d[k];
			qa <= data_a_d[k];
		end else begin
			qa <= mem[address_a_d];
		end
	end
	always @(posedge clock_b) begin
		if (wren_b_d && address_b_d[2:0] == k) begin
			mem[address_b_d[ADDRWIDTH+2:3]] <= data_b_d;
			qb <= data_b_d;
		end else begin
			qb <= mem[address_b_d[ADDRWIDTH+2:3]];
		end
	end
	assign qa_bank[k] = qa;
	assign qb_bank[k] = qb;
end endgenerate

reg [2:0] bsel_d;
always @(posedge clock_b) bsel_d <= address_b_d[2:0];
always @(*) begin
	q_a = qa_bank;
	q_b = qb_bank[bsel_d];
end

endmodule
