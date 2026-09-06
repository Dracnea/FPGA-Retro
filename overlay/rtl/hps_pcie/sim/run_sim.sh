#!/usr/bin/env bash
# Generate hps_bridge.v from hps_pcie.py, build the bench against the real
# hps_io.sv of a MiSTeX-ports checkout, run, grep PASS.
#   ./run_sim.sh [path/to/MiSTeX-ports]   (default ~/MiSTeX-ports; its venv/bin/python is used for migen)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORTS="${1:-$HOME/MiSTeX-ports}"
SYS="$PORTS/cores/Template/sys"
command -v xvlog >/dev/null 2>&1 || . "$HOME/Xilinx/2026.1/Vivado/settings64.sh"
W="$HERE/work"; rm -rf "$W"; mkdir -p "$W"; cd "$W"
"$PORTS/venv/bin/python" "$HERE/../hps_pcie.py" hps_bridge.v
xvlog hps_bridge.v > xvlog_bridge.log 2>&1 || { grep ERROR xvlog_bridge.log; exit 1; }
# hps_io.sv declares things after using them; Vivado synthesis accepts that,
# xvlog does not.  Simulate a rearranged copy (sim/hoist.py); the real file
# is what gets synthesised.
python3 "$HERE/hoist.py" "$SYS/hps_io.sv" hps_io_sim.sv
xvlog -sv -d XILINX hps_io_sim.sv "$HERE/../hps_io_wrap.sv" "$HERE/tb_hps.sv" > xvlog.log 2>&1 || { grep ERROR xvlog.log | head; exit 1; }
xelab -debug off --relax -s hps tb_hps > xelab.log 2>&1 || { grep ERROR xelab.log | head; exit 1; }
xsim hps -R 2>&1 | tee xsim.log | grep -E "^ok|FAIL|PASS|Error" || true
grep -q "^PASS" xsim.log
