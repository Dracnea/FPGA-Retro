#!/usr/bin/env bash
#
# Bring the LitePCIe endpoint up on a freshly JTAG-programmed card.
#
# The host enumerates BARs at boot, so a card that previously held a bitstream
# without a PCIe endpoint still shows its stale factory identity after a JTAG
# load. This removes that stale device, rescans, loads the driver and verifies.
#
# Run as root:  sudo tools/pcie-bringup.sh
set -uo pipefail

SW=${LITEPCIE_SW:-${MISTEX_PORTS:?set MISTEX_PORTS or LITEPCIE_SW}/build/c1100_pcie/software}

if [[ $EUID -ne 0 ]]; then echo "must run as root" >&2; exit 1; fi

echo "== before =="
lspci -nn -d 10ee: || true

# Remove every Xilinx-vendor device so the stale factory identity goes too.
for d in $(lspci -D -n -d 10ee: | awk '{print $1}'); do
    echo "removing $d"
    echo 1 > "/sys/bus/pci/devices/$d/remove"
done

sleep 1
echo "rescanning..."
echo 1 > /sys/bus/pci/rescan
sleep 2

echo
echo "== after =="
lspci -nn -d 10ee: || true

DEV=$(lspci -D -n -d 10ee: | awk '{print $1}' | head -1)
if [[ -z ${DEV:-} ]]; then
    echo "FAIL: no Xilinx device enumerated after rescan" >&2
    exit 1
fi
echo
echo "== BARs =="
lspci -s "${DEV#0000:}" -vv 2>/dev/null | grep -E 'Region|LnkSta:|LnkCap:'

echo
echo "== driver =="
rmmod litepcie 2>/dev/null
if insmod "$SW/kernel/litepcie.ko"; then
    echo "litepcie loaded"
else
    echo "FAIL: insmod litepcie.ko" >&2
    dmesg | tail -20
    exit 1
fi
sleep 1
ls -la /dev/litepcie* 2>/dev/null || echo "no /dev/litepcie* nodes"

echo
echo "== dmesg =="
dmesg | grep -i litepcie | tail -25

echo
echo "== identifier / CSR =="
"$SW/user/litepcie_util" info 2>&1 | head -40
