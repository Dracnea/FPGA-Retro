#!/usr/bin/env bash
#
# Why do BAR0 reads return 0xFFFFFFFF?  One root-side pass per bitstream that
# separates the three cases the host cannot tell apart from user space:
#
#   completion timeout   the endpoint never answered (fabric side dead: clock,
#                        reset, CQ path) -- root port DevSta/UESta shows CmpltTO
#   unsupported request  the endpoint answered UR (BAR hit not recognised) --
#                        endpoint DevSta UnsupReq+, root port shows a UR/RxMA
#   completion with ff   the endpoint answered with data (on-chip bus timed out:
#                        address decode) -- no error bits anywhere,
#                        ctrl_bus_errors would count if it were readable
#
#   sudo tools/pcie-diag.sh [bitstream.bit ...]     default: the transport image
#
# For each image: JTAG load as the invoking user, remove + rescan, clear the
# status bits on both ends, insmod, read through the driver and directly
# through resource0 (bypasses the driver), then dump both ends' status and the
# kernel log. Output: build/pcie_diag/<timestamp>.log
set -uo pipefail
cd "$(dirname "$0")/.."
[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }
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
FJTAG=${FJTAG:-$USER_HOME/.cache/fjtag-target/release/fjtag}
BITS=("$@"); [[ ${#BITS[@]} -gt 0 ]] || BITS=(bitstreams/c1100_pcie_video_transport.bit)
mkdir -p build/pcie_diag; chown "$USER_NAME" build/pcie_diag
LOG=build/pcie_diag/$(date +%Y%m%d-%H%M%S).log
exec > >(tee "$LOG") 2>&1
as_user() { runuser -u "$USER_NAME" -- "$@"; }

status_dump() {   # $1 = label
    local ep rp
    ep=$(lspci -D -n -d 10ee: | awk '{print $1}' | head -1); [[ -n $ep ]] || { echo "[$1] no Xilinx device"; return; }
    rp=$(basename "$(readlink -f /sys/bus/pci/devices/$ep/..)")
    echo "---- [$1] endpoint $ep"
    lspci -vv -s "${ep#0000:}" | grep -E 'Control:|Status:|DevSta|UESta|CESta|LnkSta:|Region 0|Kernel driver'
    echo "---- [$1] root port $rp"
    lspci -vv -s "${rp#0000:}" | grep -E 'Status:|Secondary status|DevSta|UESta|CESta|LnkSta:|RootSta|ErrorSrc|Memory behind|Prefetchable'
}
clear_status() {
    for d in $(lspci -D -n -d 10ee: | awk '{print $1}'); do
        rp=$(basename "$(readlink -f /sys/bus/pci/devices/$d/..)")
        for dev in "$d" "$rp"; do
            setpci -s "${dev#0000:}" STATUS=ffff 2>/dev/null                        # PCI status (RxMA, STA, ...)
            setpci -s "${dev#0000:}" SEC_STATUS=ffff 2>/dev/null                    # bridge secondary status (RxMA from the link)
            setpci -s "${dev#0000:}" CAP_EXP+0a.w=000f 2>/dev/null                  # DevSta: CorrErr NonFatal Fatal UnsupReq
            if lspci -s "${dev#0000:}" -vv 2>/dev/null | grep -q 'Advanced Error Reporting'; then
                setpci -s "${dev#0000:}" ECAP_AER+04.l=ffffffff 2>/dev/null     # UESta
                setpci -s "${dev#0000:}" ECAP_AER+10.l=ffffffff 2>/dev/null     # CESta
            fi
        done
    done
}

for BIT in "${BITS[@]}"; do
    CSR=${BIT%.bit}.csr.csv
    SW=$(sw_for_bit "$BIT")
    echo; echo "========== $(date -Is)  $BIT  md5 $(md5sum "$BIT" | cut -c1-32)  driver $SW/kernel/litepcie.ko"
    echo "== JTAG load"; as_user "$FJTAG" --load "$BIT" --no-serve || { echo "FAIL: load"; continue; }
    echo "== PCIe remove + rescan"
    rmmod litepcie 2>/dev/null
    for d in $(lspci -D -n -d 10ee: | awk '{print $1}'); do echo 1 > "/sys/bus/pci/devices/$d/remove"; done
    sleep 1; echo 1 > /sys/bus/pci/rescan; sleep 2
    lspci -nn -d 10ee:
    EP=$(lspci -D -n -d 10ee: | awk '{print $1}' | head -1); [[ -n $EP ]] || continue
    status_dump "after rescan, before any BAR access"
    clear_status
    echo "== enable memory space without the driver and read BAR0 directly (resource0 mmap)"
    setpci -s "${EP#0000:}" COMMAND=0x0006
    python3 - "$EP" <<'PY'
import mmap, os, struct, sys, time
ep = sys.argv[1]
fd = os.open(f"/sys/bus/pci/devices/{ep}/resource0", os.O_RDWR | os.O_SYNC)
m = mmap.mmap(fd, 0x20000, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
def rd(a): return struct.unpack("<I", m[a:a+4])[0]
t0 = time.perf_counter(); v = rd(0x0); dt = time.perf_counter() - t0
print(f"raw read ctrl_reset  @0x0000 = 0x{v:08x}  ({dt*1e6:.1f} us)")
print(f"raw read scratch     @0x0004 = 0x{rd(4):08x}")
print(f"raw read bus_errors  @0x0008 = 0x{rd(8):08x}")
print("raw read ident @0x800:", bytes(m[0x800:0x820]))
m[4:8] = struct.pack("<I", 0x12345678); print(f"scratch after write  = 0x{rd(4):08x}")
t0 = time.perf_counter()
for _ in range(1000): rd(0x0)
print(f"1000 reads: {(time.perf_counter()-t0)*1e3:.1f} ms total  -> {(time.perf_counter()-t0)*1e6/1000:.1f} us each "
      "(a completion timeout is ~10-50 ms each; a real completion is ~1-2 us)")
m.close(); os.close(fd)
PY
    status_dump "after raw reads"
    clear_status
    echo "== driver"
    insmod "$SW/kernel/litepcie.ko" && sleep 1 && chgrp plugdev /dev/litepcie0 && chmod 0660 /dev/litepcie0
    "$SW/user/litepcie_util" scratch_test 2>&1 | head -6
    status_dump "after driver reads"
    echo "== /proc/iomem around the BARs"; grep -iE "$(lspci -vv -s "${EP#0000:}" | grep -oE 'Memory at [0-9a-f]+' | awk '{print $3}' | cut -c1-5 | paste -sd'|')" /proc/iomem | head
    echo "== kernel log"; dmesg | tail -12
done
echo; echo "== done; log $LOG"
