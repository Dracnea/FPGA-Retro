/* bt_stub.c -- libbluetooth stand-in for hosts without it (FPGA-Retro x86-64
 * build).  Main_MiSTeX only calls hci_get_route() to decide whether to show
 * the Bluetooth pairing entries; reporting "no adapter" hides them.  Link the
 * real -lbluetooth instead when the dev package is installed.
 * SPDX-License-Identifier: BSD-2-Clause */
int hci_get_route(void *bdaddr) { (void)bdaddr; return -1; }
