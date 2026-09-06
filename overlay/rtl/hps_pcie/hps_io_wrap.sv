// hps_io_wrap.sv -- hps_io.sv with the 49-bit HPS_BUS assembled the way
// sys_top.v assembles it, and the enables turned into io_fpga / io_uio the
// way sys_top does, so a board file (or a testbench) can drive it from
// hps_pcie's core-side signals without touching an inout.
//
// HPS_BUS, from sys_top.v:
//   {fb_en, sl[1:0], f1, vs_hdmi, clk_100, clk_vid, ce_pix, de, hs, vs,
//    io_wait, clk_sys, io_fpga, io_uio, io_strobe, io_wide, io_din[15:0], io_dout[15:0]}
// Bits 37 (io_wait), 36 (clk_sys), 32 (io_wide) and 15:0 (io_dout) are driven
// by hps_io; the rest by the system.  Video-side inputs are tied off here:
// this wrapper is for the host transport, not the scaler.
module hps_io_wrap #(parameter CONF_STR = "TEST;;", WIDE = 0, VDNUM = 1)
(
    input         clk_sys,
    // from hps_pcie
    input  [15:0] io_din,
    input         io_strobe,
    input         fpga_enable,
    input         osd_enable,
    input         io_enable,
    // to hps_pcie
    output [15:0] io_dout,
    output        io_wide,
    output        io_wait,
    // what the core would see (the subset the bench checks)
    output [31:0] joystick_0,
    output [31:0] joystick_1,
    output [127:0] status,
    output [1:0]  buttons,
    output        ioctl_download,
    output [15:0] ioctl_index,
    output        ioctl_wr,
    output [26:0] ioctl_addr,
    output [15:0] ioctl_dout,
    output [10:0] ps2_key
);
    wire io_fpga = ~osd_enable & fpga_enable;
    wire io_uio  = ~osd_enable & io_enable;
    wire [48:0] HPS_BUS;
    assign HPS_BUS[48]    = 1'b0;          // fb_en
    assign HPS_BUS[47:46] = 2'b00;         // sl
    assign HPS_BUS[45:38] = 8'b0;          // f1, vs_hdmi, clk_100, clk_vid, ce_pix, de, hs, vs
    assign HPS_BUS[35]    = io_fpga;
    assign HPS_BUS[34]    = io_uio;
    assign HPS_BUS[33]    = io_strobe;
    assign HPS_BUS[31:16] = io_din;
    assign io_wait = HPS_BUS[37];
    assign io_wide = HPS_BUS[32];
    assign io_dout = HPS_BUS[15:0];

    // Inout buses a core without an EXT_BUS / gamma block leaves undriven.
    // hps_io muxes its read data on EXT_BUS[32], so that bit must be a real 0,
    // not a floating one (in simulation a floating select gives X on every read).
    wire [35:0] EXT_BUS;
    assign EXT_BUS[32]   = 1'b0;
    assign EXT_BUS[15:0] = 16'b0;
    wire [21:0] gamma_bus;
    assign gamma_bus[21] = 1'b0;

    wire [15:0] ioctl_dout_w;
    generate if (WIDE) begin
        assign ioctl_dout = ioctl_dout_w;
    end else begin
        assign ioctl_dout = {8'b0, ioctl_dout_w[7:0]};
    end endgenerate

    hps_io #(.CONF_STR(CONF_STR), .WIDE(WIDE), .VDNUM(VDNUM)) hps_io
    (
        .clk_sys(clk_sys),
        .HPS_BUS(HPS_BUS),
        .joystick_0(joystick_0),
        .joystick_1(joystick_1),
        .joystick_0_rumble(16'd0), .joystick_1_rumble(16'd0), .joystick_2_rumble(16'd0),
        .joystick_3_rumble(16'd0), .joystick_4_rumble(16'd0), .joystick_5_rumble(16'd0),
        .ps2_kbd_clk_in(1'b1), .ps2_kbd_data_in(1'b1), .ps2_kbd_led_status(3'b0), .ps2_kbd_led_use(3'b0),
        .ps2_mouse_clk_in(1'b1), .ps2_mouse_data_in(1'b1),
        .ps2_key(ps2_key),
        .buttons(buttons),
        .video_rotated(1'b0), .new_vmode(1'b0),
        .status(status), .status_in(128'd0), .status_set(1'b0), .status_menumask(16'd0),
        .info_req(1'b0), .info(8'd0),
        .sd_lba('{default:32'd0}), .sd_blk_cnt('{default:6'd0}), .sd_rd({VDNUM{1'b0}}), .sd_wr({VDNUM{1'b0}}),
        .sd_buff_din('{default:{(WIDE?16:8){1'b0}}}),
        .ioctl_download(ioctl_download), .ioctl_index(ioctl_index), .ioctl_wr(ioctl_wr),
        .ioctl_addr(ioctl_addr), .ioctl_dout(ioctl_dout_w[(WIDE?15:7):0]),
        .ioctl_upload_req(1'b0), .ioctl_upload_index(8'd0), .ioctl_din({(WIDE?16:8){1'b0}}),
        .ioctl_wait(1'b0),
        .EXT_BUS(EXT_BUS), .gamma_bus(gamma_bus)
    );
    generate if (!WIDE) assign ioctl_dout_w[15:8] = 8'b0; endgenerate
endmodule
