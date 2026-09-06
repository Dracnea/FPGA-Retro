// tb_sink.sv -- a VGA-style generator (64x32 active, 72x35 total) into
// video_sink, the FRM1 beats captured on the sys side and checked word for
// word; then a frame with the reader stalled, to see the drop path resync.
`timescale 1ns/1ps
module tb_sink;
   reg vid_clk = 0, sys_clk = 0, vid_rst = 1, sys_rst = 1;
   always #10 vid_clk = ~vid_clk;    // 50 MHz
   always #4  sys_clk = ~sys_clk;    // 125 MHz
   localparam W = 64, H = 32, HT = 72, VT = 35, NPIX = W*H, NBEATS = NPIX/4;

   reg [7:0] r = 0, g = 0, b = 0; reg hs = 0, vs = 0, de = 0, ce_pix = 1, f1 = 0, enable = 1, ready = 1;
   wire [127:0] data; wire valid; wire [11:0] width, height; wire [31:0] frames, drops;
   video_sink dut(.vid_clk(vid_clk), .vid_rst(vid_rst), .sys_clk(sys_clk), .sys_rst(sys_rst),
      .r(r), .g(g), .b(b), .hs(hs), .vs(vs), .de(de), .ce_pix(ce_pix), .f1(f1),
      .data(data), .valid(valid), .ready(ready), .enable(enable),
      .width(width), .height(height), .frames(frames), .drops(drops));

   // ---- generator ---------------------------------------------------------
   integer hc = 0, vc = 0, fr = 0;
   always @(posedge vid_clk) if (!vid_rst) begin
      if (hc == HT-1) begin hc <= 0; if (vc == VT-1) begin vc <= 0; fr <= fr + 1; end else vc <= vc + 1; end
      else hc <= hc + 1;
   end
   always @(*) begin
      de = (hc < W) && (vc < H);
      hs = (hc >= W+2) && (hc < W+6);
      vs = (vc == H+1);
      r = hc[7:0]; g = vc[7:0]; b = fr[7:0];
   end

   // ---- capture and check ---------------------------------------------------
   integer nbeat = 0, exp_left = 0, cur_frame = -1, complete = 0, truncated = 0, bad = 0, pix;
   integer got_frames[0:15]; integer i;
   reg [31:0] w0, w1, w2, w3;
   task automatic check_pixel(input [31:0] p, input integer idx, input integer fno); begin
      // pixel idx of sink frame fno: x = idx % W, y = idx / W -> {00, r=x, g=y, b=generator frame}.
      // The generator's frame 0 has no VSYNC edge before it, so the sink's frame k is the generator's k+1.
      reg [31:0] e; e = {8'h00, 8'(idx % W), 8'(idx / W), 8'(fno + 1)};
      if (p !== e) begin
         if (bad < 5) $display("FAIL: frame %0d pixel %0d got %08x expected %08x", fno, idx, p, e);
         bad = bad + 1;
      end
   end endtask
   always @(posedge sys_clk) if (valid && ready) begin
      nbeat = nbeat + 1;
      {w3, w2, w1, w0} = data;
      if (w0 == 32'h314D5246 && (w1 & 16'hFFFF) == W && (w1 >> 16) == H) begin
         if (exp_left != 0) begin truncated = truncated + 1; $display("info: frame %0d truncated with %0d beats left", cur_frame, exp_left); end
         cur_frame = w2; exp_left = NBEATS; pix = 0;
         if (w3 !== 0) begin $display("FAIL: flags %08x", w3); bad = bad + 1; end
      end else if (exp_left > 0) begin
         check_pixel(w0, pix, cur_frame); check_pixel(w1, pix+1, cur_frame); check_pixel(w2, pix+2, cur_frame); check_pixel(w3, pix+3, cur_frame);
         pix = pix + 4; exp_left = exp_left - 1;
         if (exp_left == 0) begin complete = complete + 1; got_frames[complete] = cur_frame; end
      end else begin
         if (bad < 5) $display("FAIL: unexpected beat %032x", data); bad = bad + 1;
      end
   end

   initial begin
      repeat (3) @(posedge vid_clk); vid_rst <= 0; sys_rst <= 0;
      // generator frame 1 = sink frame 0, measured only; sink frames 1-2 stream with ready high
      wait (fr == 4); @(posedge vid_clk);
      // stall the reader for the whole of sink frame 3 (FIFO is 64 beats, a frame is 512):
      // it is truncated after the FIFO fills; releasing ready exactly at the next frame's first
      // pixel leaves no room for sink frame 4's header, so that one is dropped whole
      ready <= 0; wait (fr == 5); @(posedge vid_clk); ready <= 1;
      // sink frame 5 streams again
      wait (fr == 7); repeat (2000) @(posedge sys_clk);
      $display("beats %0d complete %0d truncated %0d bad %0d  width %0d height %0d frames %0d drops %0d",
               nbeat, complete, truncated, bad, width, height, frames, drops);
      for (i = 1; i <= complete; i = i + 1) $display("  complete frame #%0d = frame number %0d", i, got_frames[i]);
      if (bad == 0 && complete == 3 && truncated == 1 && width == W && height == H && drops == 2 &&
          got_frames[1] == 1 && got_frames[2] == 2 && got_frames[3] == 5)
         $display("PASS");
      else $display("FAIL: summary mismatch");
      $finish;
   end
   initial begin #20_000_000; $display("FAIL: timeout"); $finish; end
endmodule
