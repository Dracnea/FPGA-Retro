# fit_iop.tcl -- out-of-context synthesis of the IOP subsystem on the C1100
#   vivado -mode batch -source fit_iop.tcl -tclargs <MiSTeX-ports dir> [part]
set ports [lindex $argv 0]
set part  [expr {[llength $argv] > 1 ? [lindex $argv 1] : "xcu55n-fsvh2892-2L-e"}]
set here  [file dirname [file normalize [info script]]]
set up    $ports/cores/PSX/upstream/rtl
set ovl   [file normalize $here/../../..]
set core  [file normalize $here/..]

read_vhdl -vhdl2008 -library altera_mf $ovl/rtl/altera_compat/altera_mf_components.vhd
read_verilog -library mem [list $ovl/rtl/altera_compat/altsyncram.v $ovl/rtl/altera_compat/altdpram.v]
read_vhdl -vhdl2008 -library mem [list \
  $up/RamMLAB.vhd $up/SyncFifoFallThroughMLAB.vhd $up/SyncFifo.vhd $up/SyncFifoFallThrough.vhd \
  $up/SyncRam.vhd $ovl/cores/PSX/rtl/SyncRamDual.vhd $ovl/cores/PSX/rtl/SyncRamDualNotPow2.vhd \
  $up/SyncRamDualByteEnable.vhd $up/dpram.vhd $up/export.vhd $up/divider.vhd $up/datacache.vhd \
  $up/cpu.vhd $up/timer.vhd $up/memctrl.vhd \
  $up/spu_gauss.vhd $up/spu_ram.vhd $up/spu.vhd \
  $core/rtl/iop/iop_regstub.vhd $core/rtl/iop/iop_intc.vhd $core/rtl/iop/iop_timer32.vhd \
  $core/rtl/iop/iop_ram.vhd $core/rtl/iop/iop_spuram.vhd $core/rtl/iop/iop_spu2.vhd \
  $core/rtl/iop/iop_sio2.vhd $core/rtl/iop/iop_cdvd.vhd \
  $core/rtl/iop/iop_memorymux.vhd $core/rtl/iop/iop_top.vhd]
synth_design -top iop_top -part $part -mode out_of_context -flatten_hierarchy rebuilt
# the IOP clock and the PSX core's phase-aligned multiples.  The periods must
# be exact multiples of each other: 27.127 / 13.563 / 9.042 leaves the
# clk2x -> clk1x paths with a 0.001 ns requirement (the two rising edges land
# 1 ps apart at 27.126 vs 27.127) and every such path fails by ~4 ns.
create_clock -period 27.126 -name clk1x [get_ports clk1x]
create_clock -period 13.563 -name clk2x [get_ports clk2x]
create_clock -period  9.042 -name clk3x [get_ports clk3x]
report_utilization -file utilization.rpt
report_utilization -hierarchical -hierarchical_depth 2 -file utilization_hier.rpt
report_timing_summary -delay_type max -max_paths 10 -file timing.rpt
report_clocks -file clocks.rpt
write_checkpoint -force synth.dcp
puts "FIT DONE"
