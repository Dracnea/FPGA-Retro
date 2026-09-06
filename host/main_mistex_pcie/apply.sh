#!/usr/bin/env bash
# Install the PCIe host port into a Main_MiSTeX checkout.
#   host/main_mistex_pcie/apply.sh /path/to/Main_MiSTeX
# Copies the new files in and applies main_mistex.patch (two small guards in
# fpga_io.cpp and a comment in shmem.cpp).  Written against Main_MiSTeX
# f8705a5; `git apply --check` tells you if a newer checkout has drifted.
set -euo pipefail
DEST=${1:?usage: $0 /path/to/Main_MiSTeX}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
[[ -f $DEST/fpga_io.cpp && -f $DEST/Makefile ]] || { echo "$DEST is not a Main_MiSTeX checkout" >&2; exit 1; }
cp -v "$HERE/fpga_io_pcie.cpp" "$HERE/Makefile.x86_64" "$DEST/"
mkdir -p "$DEST/lib/imlib2_stub" "$DEST/lib/host_stubs"
cp -v "$HERE/lib/imlib2_stub/imlib2_stub.c" "$DEST/lib/imlib2_stub/"
cp -v "$HERE/lib/host_stubs/bt_stub.c" "$DEST/lib/host_stubs/"
if git -C "$DEST" apply --check --reverse "$HERE/main_mistex.patch" 2>/dev/null; then
    echo "patch already applied"
else
    git -C "$DEST" apply --check "$HERE/main_mistex.patch"
    git -C "$DEST" apply "$HERE/main_mistex.patch"
    echo "patch applied"
fi
echo "now: cd $DEST && make -f Makefile.x86_64 -j"
