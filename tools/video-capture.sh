#!/usr/bin/env bash
#
# Capture what the card draws, for review by someone who was not at the screen.
#
#   sudo tools/video-capture.sh [bitstream.bit] [seconds]
#
# Loads the bitstream over JTAG (default: bitstreams/c1100_hps_video_test.bit,
# the 640x480 pattern generator through the video sink), restores the PCIe
# identity and the litepcie driver (root), enables the sink, then runs
# retroview headless as the invoking user for the given time (default 10 s)
# and leaves in build/video/<timestamp>/:
#
#   session.frm1        the raw FRM1 stream, replayable with
#                       retroview --transport file --file session.frm1
#   session.avi         MJPEG AVI, opens in any player
#   shots/frame-*.png   one PNG per second of video
#   contact.png         the shots tiled into one image
#   capture.log         retroview's statistics plus video_dims / video_frames /
#                       video_drops read from the card before and after
#
# Whatever bitstream holds the card afterwards is this one; reload the PS2
# image (or any other) when done.
set -uo pipefail
cd "$(dirname "$0")/.."
BIT=${1:-bitstreams/c1100_hps_video_test.bit}
SECS=${2:-10}
CSR=${BIT%.bit}.csr.csv
[[ $EUID -eq 0 ]] || { echo "run with sudo (PCIe rescan and driver need root)" >&2; exit 1; }
[[ -f $BIT && -f $CSR ]] || { echo "need $BIT and $CSR" >&2; exit 1; }
USER_NAME=${SUDO_USER:-dracnea}
USER_HOME=$(getent passwd "$USER_NAME" | cut -d: -f6)

# The LitePCIe kernel module hard-codes the CSR addresses of the image it was
# generated with (csr.h), and the pcie_* blocks sit at different addresses in
# different images (whatever sorts before them shifts them). So the driver has
# to match the bitstream: each build directory carries its own software/.
sw_for_bit() {   # $1 = bitstream path -> software dir of the build that made it
    local n; n=$(basename "$1" .bit)
    case $n in
        c1100_pcie_video_transport) n=c1100_pcie ;;
        c1100_pcie_diag)            n=c1100_pcie_diag ;;
    esac
    echo "${LITEPCIE_SW:-$USER_HOME/MiSTeX-ports/build/$n/software}"
}
SW=$(sw_for_bit "$BIT")
[[ -f $SW/kernel/litepcie.ko ]] || { echo "no driver for this image: $SW/kernel/litepcie.ko (build it: make -C $SW/kernel)" >&2; exit 1; }
OUT=build/video/$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT"; chown -R "$USER_NAME" build/video
as_user() { runuser -u "$USER_NAME" -- "$@"; }
exec > >(tee "$OUT/capture.log") 2>&1
echo "== $(date -Is) capture from $BIT for $SECS s -> $OUT"

echo "== JTAG load (as $USER_NAME)"
as_user env FJTAG="${FJTAG:-}" PATH="$PATH" tools/jtag-load.sh "$BIT" || { echo "FAIL: JTAG load"; exit 1; }

echo "== PCIe: drop the stale identity, rescan, driver"
for d in $(lspci -D -n -d 10ee: | awk '{print $1}'); do echo 1 > "/sys/bus/pci/devices/$d/remove"; done
sleep 1; echo 1 > /sys/bus/pci/rescan; sleep 2
lspci -nn -d 10ee:
rmmod litepcie 2>/dev/null; insmod "$SW/kernel/litepcie.ko" || { echo "FAIL: insmod"; exit 1; }
sleep 1
[[ -e /etc/udev/rules.d/99-litepcie.rules ]] || { cp tools/99-litepcie.rules /etc/udev/rules.d/; udevadm control --reload-rules; udevadm trigger; }
chgrp plugdev /dev/litepcie0 && chmod 0660 /dev/litepcie0

echo "== sink on"
as_user tools/csrw.py --csr "$CSR" write video_enable 1
for r in video_dims video_frames video_drops; do echo -n "$r before: "; as_user tools/csrw.py --csr "$CSR" read $r; done

echo "== retroview headless, $SECS s"
FRAMES=$(( SECS * 60 ))
cd host/viewer
as_user env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/retroview --transport litepcie --headless \
    --frames "$FRAMES" --timeout 15 --record "../../$OUT/session.frm1" --video "../../$OUT/session.avi" --video-fps 59.5 \
    --shots "../../$OUT/shots" --shot-every 60 --contact "../../$OUT/contact.png" --screenshot "../../$OUT/last.png"
cd ../..
for r in video_dims video_frames video_drops; do echo -n "$r after: "; as_user tools/csrw.py --csr "$CSR" read $r; done
chown -R "$USER_NAME" "$OUT"
echo "== done $(date -Is): review $OUT/contact.png, play $OUT/session.avi"
