// altsyncram -- Vivado stand-in for Intel's synchronous RAM megafunction.
// Interface per the Intel documentation; behaviour is read-first on each port
// (Intel NEW_DATA_NO_NBE_READ returns the new data -- see README.md).
// SPDX-License-Identifier: BSD-2-Clause
`timescale 1ns/1ps
module altsyncram #(
    parameter integer width_a               = 8,
    parameter integer widthad_a             = 8,
    parameter integer numwords_a            = (1 << widthad_a),
    parameter integer width_b               = width_a,
    parameter integer widthad_b             = widthad_a,
    parameter integer numwords_b            = (1 << widthad_b),
    parameter integer width_byteena_a       = 1,
    parameter integer width_byteena_b       = 1,
    parameter         operation_mode        = "BIDIR_DUAL_PORT",
    parameter         outdata_reg_a         = "UNREGISTERED",
    parameter         outdata_reg_b         = "UNREGISTERED",
    parameter         address_reg_b         = "CLOCK1",
    parameter         indata_reg_b          = "CLOCK1",
    parameter         wrcontrol_wraddress_reg_b = "CLOCK1",
    parameter         rdcontrol_reg_b       = "CLOCK1",
    parameter         byteena_reg_b         = "CLOCK1",
    parameter         clock_enable_input_a  = "NORMAL",
    parameter         clock_enable_input_b  = "NORMAL",
    parameter         clock_enable_output_a = "BYPASS",
    parameter         clock_enable_output_b = "BYPASS",
    parameter         clock_enable_core_a   = "USE_INPUT_CLKEN",
    parameter         clock_enable_core_b   = "USE_INPUT_CLKEN",
    parameter         outdata_aclr_a        = "NONE",
    parameter         outdata_aclr_b        = "NONE",
    parameter         indata_aclr_a         = "NONE",
    parameter         address_aclr_a        = "NONE",
    parameter         address_aclr_b        = "NONE",
    parameter         wrcontrol_aclr_a      = "NONE",
    parameter         byteena_aclr_a        = "NONE",
    parameter         byteena_aclr_b        = "NONE",
    parameter         read_during_write_mode_port_a      = "NEW_DATA_NO_NBE_READ",
    parameter         read_during_write_mode_port_b      = "NEW_DATA_NO_NBE_READ",
    parameter         read_during_write_mode_mixed_ports = "DONT_CARE",
    parameter         power_up_uninitialized = "FALSE",
    parameter         init_file             = "UNUSED",
    parameter         init_file_layout      = "PORT_A",
    parameter         ram_block_type        = "AUTO",
    parameter         intended_device_family = "Cyclone V",
    parameter         lpm_type              = "altsyncram",
    parameter         lpm_hint              = "UNUSED",
    parameter integer maximum_depth         = 0,
    parameter integer byte_size             = 8,
    parameter         enable_ecc            = "FALSE",
    parameter         implement_in_les      = "OFF",
    parameter         ecc_pipeline_stage_enabled = "FALSE"
) (
    input  wire [widthad_a-1:0]        address_a,
    input  wire [widthad_b-1:0]        address_b,
    input  wire [width_a-1:0]          data_a,
    input  wire [width_b-1:0]          data_b,
    input  wire                        wren_a,
    input  wire                        wren_b,
    input  wire                        rden_a,
    input  wire                        rden_b,
    input  wire                        clock0,
    input  wire                        clock1,
    input  wire                        clocken0,
    input  wire                        clocken1,
    input  wire                        clocken2,
    input  wire                        clocken3,
    input  wire [width_byteena_a-1:0]  byteena_a,
    input  wire [width_byteena_b-1:0]  byteena_b,
    input  wire                        aclr0,
    input  wire                        aclr1,
    input  wire                        addressstall_a,
    input  wire                        addressstall_b,
    output wire [width_a-1:0]          q_a,
    output wire [width_b-1:0]          q_b,
    output wire [2:0]                  eccstatus
);
    // The narrowest port defines the storage word; a wider port touches RA / RB
    // consecutive words per access, which is how Intel lays out mixed widths.
    localparam integer W     = (width_a < width_b) ? width_a : width_b;
    localparam integer RA    = width_a / W;
    localparam integer RB    = width_b / W;
    localparam integer DEPTH = (numwords_a * RA > numwords_b * RB) ? numwords_a * RA : numwords_b * RB;
    localparam integer BEA   = width_a / width_byteena_a;   // data bits per byte-enable lane
    localparam integer BEB   = width_b / width_byteena_b;
    localparam         BIDIR = (operation_mode == "BIDIR_DUAL_PORT");

    reg [W-1:0] mem [0:DEPTH-1];

    wire clk_b  = (address_reg_b == "CLOCK1") ? clock1   : clock0;
    wire en_b   = (address_reg_b == "CLOCK1") ? clocken1 : clocken0;
    wire clk_bq = (outdata_reg_b == "CLOCK1") ? clock1   : clock0;

    reg [width_a-1:0] ra = {width_a{1'b0}};
    reg [width_b-1:0] rb = {width_b{1'b0}};
    integer i, j;

    always @(posedge clock0) begin
        if (clocken0) begin
            for (i = 0; i < RA; i = i + 1) begin
                for (j = 0; j < W; j = j + 1)
                    if (wren_a && byteena_a[(i*W + j) / BEA])
                        mem[address_a*RA + i][j] <= data_a[i*W + j];
                if (rden_a) ra[i*W +: W] <= mem[address_a*RA + i];
            end
        end
    end

    always @(posedge clk_b) begin
        if (en_b) begin
            for (i = 0; i < RB; i = i + 1) begin
                for (j = 0; j < W; j = j + 1)
                    if (BIDIR && wren_b && byteena_b[(i*W + j) / BEB])
                        mem[address_b*RB + i][j] <= data_b[i*W + j];
                if (rden_b) rb[i*W +: W] <= mem[address_b*RB + i];
            end
        end
    end

    reg [width_a-1:0] ra_q = {width_a{1'b0}};
    reg [width_b-1:0] rb_q = {width_b{1'b0}};
    always @(posedge clock0) ra_q <= ra;
    always @(posedge clk_bq) rb_q <= rb;
    assign q_a = (outdata_reg_a == "UNREGISTERED") ? ra : ra_q;
    assign q_b = (outdata_reg_b == "UNREGISTERED") ? rb : rb_q;
    assign eccstatus = 3'b000;
endmodule
