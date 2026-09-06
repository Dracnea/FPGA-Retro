// tb_hps.sv -- drives hps_bridge (the migen HPSBridge converted to Verilog)
// exactly as Main_MiSTeX's fpga_io backend does, into hps_io_wrap + the real
// hps_io.sv, and checks the answers hps_io gives: the config string, the
// status/version words, a joystick update and a two-word (din2) transaction.
`timescale 1ns/1ps
module tb_hps;
   localparam string CONF = "HPSTEST;;O1,Foo,No,Yes;O2,Bar,Off,On;V,v1.0;";   // > 32 bytes, as every real core is (MAX_W)
   reg sys_clk = 0, core_clk = 0, sys_rst = 1, core_rst = 1;
   always #4 sys_clk = ~sys_clk;        // 125 MHz
   always #10 core_clk = ~core_clk;     // 50 MHz
   // host-side register ports
   reg fpga_en = 0, osd_en = 0, io_en = 0, core_reset = 1, btn_osd = 0, btn_user = 0;
   reg [15:0] din_word = 0; reg din_we = 0; reg [31:0] din2_word = 0; reg din2_we = 0;
   wire [15:0] dout; wire busy, io_wide;
   // core side
   wire [15:0] io_din, io_dout; wire io_strobe, fpga_enable, osd_enable, io_enable, core_reset_c, io_wide_in, io_wait;
   wire [1:0] btn;
   wire [31:0] joystick_0, joystick_1; wire [127:0] status; wire [1:0] buttons;
   wire ioctl_download, ioctl_wr; wire [15:0] ioctl_index, ioctl_dout; wire [26:0] ioctl_addr; wire [10:0] ps2_key;

   hps_bridge bridge(
      .sys_clk(sys_clk), .sys_rst(sys_rst), .core_clk(core_clk), .core_rst(core_rst),
      .ctrl_fpga_en(fpga_en), .ctrl_osd_en(osd_en), .ctrl_io_en(io_en), .ctrl_core_reset(core_reset),
      .ctrl_btn_osd(btn_osd), .ctrl_btn_user(btn_user),
      .din_word(din_word), .din_we(din_we), .din2_word(din2_word), .din2_we(din2_we),
      .dout(dout), .busy(busy), .io_wide(io_wide),
      .io_din(io_din), .io_strobe(io_strobe), .fpga_enable(fpga_enable), .osd_enable(osd_enable),
      .io_enable(io_enable), .core_reset(core_reset_c), .btn(btn), .io_dout(io_dout), .io_wide_in(io_wide_in));

   hps_io_wrap #(.CONF_STR(CONF)) wrap(
      .clk_sys(core_clk), .io_din(io_din), .io_strobe(io_strobe), .fpga_enable(fpga_enable),
      .osd_enable(osd_enable), .io_enable(io_enable), .io_dout(io_dout), .io_wide(io_wide_in), .io_wait(io_wait),
      .joystick_0(joystick_0), .joystick_1(joystick_1), .status(status), .buttons(buttons),
      .ioctl_download(ioctl_download), .ioctl_index(ioctl_index), .ioctl_wr(ioctl_wr), .ioctl_addr(ioctl_addr),
      .ioctl_dout(ioctl_dout), .ps2_key(ps2_key));

   integer fails = 0;
   // --- the fpga_io backend primitives, as software would issue them ---------
   task automatic wait_idle; begin @(posedge sys_clk); while (busy) @(posedge sys_clk); end endtask
   task automatic spi_w(input [15:0] w, output [15:0] r); begin
      wait_idle; din_word <= w; din_we <= 1; @(posedge sys_clk); din_we <= 0; wait_idle; r = dout;
   end endtask
   task automatic spi_w2(input [31:0] w); begin
      wait_idle; din2_word <= w; din2_we <= 1; @(posedge sys_clk); din2_we <= 0; wait_idle;
   end endtask
   task automatic enable_io;  begin io_en <= 1; repeat (6) @(posedge sys_clk); end endtask
   task automatic disable_io; begin io_en <= 0; repeat (6) @(posedge sys_clk); end endtask
   task automatic check(input string what, input [31:0] got, input [31:0] exp); begin
      if (got !== exp) begin $display("FAIL: %s got %08x expected %08x", what, got, exp); fails = fails + 1; end
      else $display("ok   %s = %08x", what, got);
   end endtask

   reg [15:0] r; string s; integer i;
   initial begin
      repeat (5) @(posedge sys_clk); sys_rst <= 0; core_rst <= 0;
      repeat (20) @(posedge sys_clk);
      core_reset <= 0;

      // user_io_read_confstr(): EnableIO; spi_w(UIO_GET_STRING); bytes until 0; DisableIO
      // (Main: "read one null word until the result shows up" -- the answer to a
      // word is what the NEXT word shifts in)
      enable_io; spi_w(16'h14, r); spi_w(16'h0, r); s = "";
      for (i = 0; i < 64; i = i + 1) begin spi_w(16'h0, r); if (r[7:0] == 0) break; s = {s, string'(r[7:0])}; end
      disable_io;
      if (s != CONF) begin $display("FAIL: conf string '%s' expected '%s'", s, CONF); fails = fails + 1; end
      else $display("ok   conf string '%s'", s);

      // UIO_GET_STATUS 0x29 -> {4'hA, stflg}
      enable_io; spi_w(16'h29, r); spi_w(16'h0, r); disable_io; check("GET_STATUS 0xA nibble", r[7:4], 4'hA);   // {4'hA, stflg} is 8 bits wide
      // UIO_SET_FLTNUM 0x2B first word answers {HPS_BUS[48:46], 4'b0111}
      enable_io; spi_w(16'h2B, r); spi_w(16'h0, r); disable_io; check("0x2B capability word", r, 16'h0007);
      // UIO_JOYSTICK0: two words
      enable_io; spi_w(16'h02, r); spi_w(16'h1234, r); spi_w(16'h5678, r); disable_io;
      repeat (4) @(posedge core_clk); check("joystick_0 via din", joystick_0, 32'h56781234);
      // the same through one din2 write
      enable_io; spi_w(16'h02, r); spi_w2(32'hBEEFCAFE); disable_io;
      repeat (4) @(posedge core_clk); check("joystick_0 via din2", joystick_0, 32'hBEEFCAFE);
      // UIO_BUT_SW: cfg -> buttons
      enable_io; spi_w(16'h01, r); spi_w(16'h0003, r); disable_io;
      repeat (4) @(posedge core_clk); check("buttons via cfg", buttons, 2'b11);
      // levels
      fpga_en <= 1; osd_en <= 1; repeat (6) @(posedge core_clk);
      check("fpga_enable level", fpga_enable, 1); check("osd_enable level", osd_enable, 1);
      check("core_reset released", core_reset_c, 0); check("io_wide (WIDE=0)", io_wide, 0);

      if (fails == 0) $display("PASS"); else $display("FAIL: %0d checks failed", fails);
      $finish;
   end
   initial begin #2_000_000; $display("FAIL: timeout"); $finish; end
endmodule
