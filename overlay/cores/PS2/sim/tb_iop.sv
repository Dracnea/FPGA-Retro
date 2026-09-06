// tb_iop.sv -- runs boot_test.hex on the IOP subsystem and watches the POST
// register.  PASS on 0xAA, FAIL on 0xEE, an unexpected exception, a CPU error
// flag, or the timeout.
`timescale 1ns/1ps
module tb_iop;
   // 36.864 MHz and its phase-aligned 2x / 3x, as the PSX core's PLL provides
   localparam real P1 = 27.1267;
   reg clk1x = 0, clk2x = 0, clk3x = 0, reset = 1;
   always #(P1/2) clk1x = ~clk1x;
   always #(P1/4) clk2x = ~clk2x;
   always #(P1/6) clk3x = ~clk3x;

   reg         rom_wr = 0;
   reg  [19:0] rom_addr = 0;
   reg  [31:0] rom_data = 0;
   wire [7:0]  post_code;
   wire        post_wr, cpu_error, mem_idle;
   reg         vblank = 0, hblank = 0;

   iop_top dut
   (
      .clk1x(clk1x), .clk2x(clk2x), .clk3x(clk3x), .reset(reset),
      .hblank(hblank), .vblank(vblank), .ext_irq(32'h0),
      .rom_wr(rom_wr), .rom_addr(rom_addr), .rom_data(rom_data),
      .post_code(post_code), .post_wr(post_wr),
      .cpu_error(cpu_error), .mem_idle(mem_idle)
   );

   reg [31:0] image [0:4095];
   integer i, t0;
   string romfile;

   initial begin
      if (!$value$plusargs("rom=%s", romfile)) romfile = "boot_test.hex";
      $readmemh(romfile, image);
      // load the ROM through its write port while in reset
      @(posedge clk1x);
      for (i = 0; i < 4096; i = i + 1) begin
         rom_wr <= 1; rom_addr <= i; rom_data <= image[i];
         @(posedge clk1x);
      end
      rom_wr <= 0;
      repeat (8) @(posedge clk1x);
      reset <= 0;
      $display("[%0t] reset released", $time);
   end

   // a free-running vblank/hblank so timers that count them have something to count
   always begin
      #(P1*100) hblank = 1; #(P1*10) hblank = 0;
   end
   always begin
      #(P1*30000) vblank = 1; #(P1*2000) vblank = 0;
   end

   always @(posedge clk1x) begin
      if (post_wr) begin
         $display("[%0t] POST %02x", $time, post_code);
         if (post_code == 8'hAA) begin $display("PASS"); $finish; end
         if (post_code == 8'hEE) begin $display("FAIL: test reported failure"); $finish; end
      end
      if (cpu_error && !reset) begin $display("FAIL: cpu error flag"); $finish; end
   end

   initial begin
      #(P1 * 3_000_000);   // ~80 ms of IOP time
      $display("FAIL: timeout, last POST %02x", post_code);
      $finish;
   end
endmodule
