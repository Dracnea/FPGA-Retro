#!/usr/bin/env bash
#
# Install this repo's overlay into a MiSTeX-ports checkout.
#
#   tools/install-overlay.sh /path/to/MiSTeX-ports [--symlink]
#
# The overlay mirrors MiSTeX-ports' directory structure exactly, so this is a
# straight copy. --symlink links instead, which is what you want while
# developing here and building there.
set -euo pipefail

DEST=${1:-}
MODE=${2:-copy}

if [[ -z $DEST ]]; then
    echo "usage: $0 /path/to/MiSTeX-ports [--symlink]" >&2
    exit 2
fi
if [[ ! -f $DEST/mistex_boards/xilinx_mistex.py ]]; then
    echo "error: $DEST does not look like a MiSTeX-ports checkout" >&2
    echo "       (expected mistex_boards/xilinx_mistex.py)" >&2
    exit 1
fi

SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")/../overlay" && pwd)

cd "$SRC"
find . -type f | while read -r f; do
    target=$DEST/${f#./}
    mkdir -p "$(dirname "$target")"
    if [[ $MODE == --symlink ]]; then
        ln -sfn "$SRC/${f#./}" "$target"
        echo "link  ${f#./}"
    else
        cp "$f" "$target"
        echo "copy  ${f#./}"
    fi
done

echo
echo "Installed into $DEST"
echo "Build the PCIe transport with:"
echo "  cd $DEST && python3 mistex_boards/c1100_pcie_video.py"
