#!/usr/bin/env bash
# Generate video_sink.v from video_sink.py (FIFO depth 64 for the bench), run tb_sink.sv in xsim, grep PASS.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORTS="${1:-$HOME/MiSTeX-ports}"
command -v xvlog >/dev/null 2>&1 || . "$HOME/Xilinx/2026.1/Vivado/settings64.sh"
W="$HERE/work"; rm -rf "$W"; mkdir -p "$W"; cd "$W"
"$PORTS/venv/bin/python" "$HERE/../video_sink.py" video_sink.v
xvlog video_sink.v > xvlog_sink.log 2>&1 || { grep ERROR xvlog_sink.log; exit 1; }
xvlog -sv "$HERE/tb_sink.sv" > xvlog.log 2>&1 || { grep ERROR xvlog.log | head; exit 1; }
xelab -debug off --relax -s sink tb_sink > xelab.log 2>&1 || { grep ERROR xelab.log | head; exit 1; }
xsim sink -R 2>&1 | tee xsim.log | grep -E "FAIL|PASS|info|beats|complete frame|Error" || true
grep -q "^PASS" xsim.log
