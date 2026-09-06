// fpga_io_pcie.cpp -- Main_MiSTeX's FPGA transport over a LitePCIe endpoint.
//
// On MiSTeX boards Main talks to the core's hps_io through an SPI slave
// (sys/hps_interface.v) driven from a Raspberry Pi's spidev, with four GPIO
// levels beside it.  On the UltraScale+ cards (FPGA-Retro) the same bridge is
// a CSR block on the PCIe BAR, reached through the litepcie driver's register
// ioctl.  This file implements the fpga_io.h API on those CSRs; the SPI/GPIO
// implementation stays in fpga_io.cpp and is selected when PCIE_HOST is not
// defined.
//
// CSR contract (FPGA-Retro overlay, LiteX module `hps`; the addresses are read
// from the csr.csv generated with the bitstream, never hard-coded):
//   hps_control  rw  bit0 fpga_en  bit1 osd_en  bit2 io_en  bit3 core_reset
//                    bit4 btn_osd  bit5 btn_user
//   hps_din      wo  16-bit: one SPI-word transaction -- the core's io_dout is
//                    latched into hps_dout, the word is presented as io_din and
//                    io_strobe pulses once
//   hps_din2     wo  two words, low half first, transacted back to back
//   hps_dout     ro  the io_dout latched by the last transaction
//   hps_status   ro  bit0 io_wide  bit1 busy (transaction in flight)
//
// Environment: MISTEX_PCIE_DEV (default /dev/litepcie0) and MISTEX_CSR_CSV
// (default: csr.csv next to the executable, then ./csr.csv, then
// /etc/mistex/csr.csv).
//
// SPDX-License-Identifier: GPL-3.0-or-later (as Main_MiSTeX)
#ifdef PCIE_HOST

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <limits.h>
#include <sys/ioctl.h>

#include "cfg.h"
#include "fpga_io.h"
#include "file_io.h"
#include "input.h"
#include "osd.h"
#include "menu.h"
#include "offload.h"
#include "spi.h"

// litepcie driver ioctl (software/kernel/litepcie.h of the generated driver)
struct litepcie_ioctl_reg { uint32_t addr; uint32_t val; uint8_t is_write; };
#define LITEPCIE_IOCTL      'S'
#define LITEPCIE_IOCTL_REG  _IOWR(LITEPCIE_IOCTL, 0, struct litepcie_ioctl_reg)

#define HPS_CTRL_FPGA_EN    (1 << 0)
#define HPS_CTRL_OSD_EN     (1 << 1)
#define HPS_CTRL_IO_EN      (1 << 2)
#define HPS_CTRL_CORE_RESET (1 << 3)
#define HPS_CTRL_BTN_OSD    (1 << 4)
#define HPS_CTRL_BTN_USER   (1 << 5)

#define HPS_STAT_IO_WIDE    (1 << 0)
#define HPS_STAT_BUSY       (1 << 1)

bool spi_trace = 0;
static const bool spi_en_trace = 0;

static int      pcie_fd = -1;
static uint32_t csr_control, csr_din, csr_din2, csr_dout, csr_status;
static bool     csr_ok = false;
static uint32_t control_shadow = 0;

static uint32_t pcie_readl(uint32_t addr)
{
	struct litepcie_ioctl_reg m = { addr, 0, 0 };
	if (ioctl(pcie_fd, LITEPCIE_IOCTL_REG, &m) < 0) {
		printf("litepcie readl(0x%08x): %s\n", addr, strerror(errno));
		return 0;
	}
	return m.val;
}

static void pcie_writel(uint32_t addr, uint32_t val)
{
	struct litepcie_ioctl_reg m = { addr, val, 1 };
	if (ioctl(pcie_fd, LITEPCIE_IOCTL_REG, &m) < 0)
		printf("litepcie writel(0x%08x, 0x%08x): %s\n", addr, val, strerror(errno));
}

static int csr_lookup(const char *path)
{
	FILE *f = fopen(path, "r");
	if (!f) return -1;
	char line[512];
	int found = 0;
	while (fgets(line, sizeof(line), f)) {
		char kind[32], name[128];
		unsigned addr;
		if (sscanf(line, "%31[^,],%127[^,],%x", kind, name, &addr) != 3) continue;
		if (strcmp(kind, "csr_register")) continue;
		uint32_t *slot = 0;
		if      (!strcmp(name, "hps_control")) slot = &csr_control;
		else if (!strcmp(name, "hps_din"))     slot = &csr_din;
		else if (!strcmp(name, "hps_din2"))    slot = &csr_din2;
		else if (!strcmp(name, "hps_dout"))    slot = &csr_dout;
		else if (!strcmp(name, "hps_status"))  slot = &csr_status;
		if (slot) { *slot = addr; found++; }
	}
	fclose(f);
	return found == 5 ? 0 : -2;
}

static void write_control()
{
	pcie_writel(csr_control, control_shadow);
}

int fpga_io_init()
{
	const char *dev = getenv("MISTEX_PCIE_DEV");
	if (!dev) dev = "/dev/litepcie0";

	// find the csr.csv that matches the loaded bitstream
	const char *env = getenv("MISTEX_CSR_CSV");
	char beside[PATH_MAX];
	const char *candidates[4];
	int n = 0;
	if (env) candidates[n++] = env;
	{
		char *app = getappname();
		snprintf(beside, sizeof(beside), "%s", app);
		char *slash = strrchr(beside, '/');
		if (slash) { strcpy(slash + 1, "csr.csv"); candidates[n++] = beside; }
	}
	candidates[n++] = "csr.csv";
	candidates[n++] = "/etc/mistex/csr.csv";

	const char *used = 0;
	for (int i = 0; i < n; i++) {
		int r = csr_lookup(candidates[i]);
		if (r == 0) { used = candidates[i]; break; }
		if (r == -2) printf("csr.csv %s has no hps_* registers -- not a FPGA-Retro hps bitstream?\n", candidates[i]);
	}
	if (!used) {
		printf("ERROR: no csr.csv with the hps_* registers found (MISTEX_CSR_CSV, beside the executable, ./csr.csv, /etc/mistex/csr.csv)\n");
		return -1;
	}
	printf("PCIe HPS bridge: csr map %s (hps_control 0x%08x)\n", used, csr_control);

	pcie_fd = open(dev, O_RDWR | O_CLOEXEC);
	if (pcie_fd < 0) {
		printf("ERROR: cannot open %s: %s (is the litepcie driver loaded and the FPGA-Retro bitstream enumerated?)\n", dev, strerror(errno));
		return -1;
	}
	csr_ok = true;
	control_shadow = 0;
	write_control();
	printf("PCIe HPS bridge: %s open, io_wide=%d\n", dev, fpga_get_fio_size());
	return 0;
}

int fpga_core_id()
{
	return 0x5CA623A4;
}

int fpga_get_fio_size()
{
	// 0: normal (8-bit) or 1: wide (16-bit) IO
	if (!csr_ok) return 0;
	return (pcie_readl(csr_status) & HPS_STAT_IO_WIDE) ? 1 : 0;
}

int fpga_get_io_version()
{
	return 1;
}

void fpga_set_led(uint32_t on)
{
	(void)on;
}

int fpga_get_buttons()
{
	// The card has no buttons; menu/OSD are reached from the keyboard
	// (input.cpp).  A host-side tool may set the btn_* bits in hps_control.
	if (!csr_ok) return 0;
	uint32_t c = pcie_readl(csr_control);
	return ((c & HPS_CTRL_BTN_OSD) ? BUTTON_OSD : 0) | ((c & HPS_CTRL_BTN_USER) ? BUTTON_USR : 0);
}

int fpga_get_io_type()
{
	return 1;
}

void reboot(int cold)
{
	// MiSTeX reboots the SBC here.  This is the user's PC: reset the core and
	// leave the process instead.
	(void)cold;
	sync();
	fpga_core_reset();
	printf("reboot(): not rebooting the host; exiting\n");
	exit(0);
}

char *getappname()
{
	static char dest[PATH_MAX];
	memset(dest, 0, sizeof(dest));
	char path[64];
	sprintf(path, "/proc/%d/exe", getpid());
	if (readlink(path, dest, PATH_MAX - 1) < 0) dest[0] = 0;
	return dest;
}

void app_restart(const char *path, const char *xml)
{
	sync();
	fpga_core_reset();

	input_switch(0);
	input_uinp_destroy();
	offload_stop();

	char *appname = getappname();
	printf("restarting the %s\n", appname);
	execl(appname, appname, path, xml, NULL);

	printf("Something went wrong restarting %s: %s\n", appname, strerror(errno));
	exit(1);
}

int fpga_load_rbf(const char *name, const char *config, const char *xml)
{
	// The card is programmed over JTAG (or by whatever the user runs), not
	// from here: there is no fpgaloader on the PCIe path yet.  Log what the
	// menu asked for, treat it as loaded, and restart Main for that core's
	// configuration so the rest of the flow (config string, OSD) proceeds
	// against whatever bitstream is actually in the card.
	OsdDisable();
	static char path[1024];
	if (name[0] == '/')
		strcpy(path, name);
	else
		sprintf(path, "%s/%s",
		        !strcasecmp(name, cfg.menu_core_filename) ? getStorageDir(0) : getRootDir(),
		        name);
	printf("fpga_load_rbf: bitstream %s must be loaded onto the card by the user (JTAG); assuming it is.\n", path);
	if (config) {
		fpga_core_reset();
	}
	Info("Bitstream load is manual on this host", 3000);
	app_restart(!strcasecmp(name, cfg.menu_core_filename) ? cfg.menu_core_filename : path, xml);
	return 0;
}

void fpga_core_reset()
{
	printf("fpga_core_reset()\n");
	if (!csr_ok) return;
	control_shadow |= HPS_CTRL_CORE_RESET;
	write_control();
	usleep(100000);
	control_shadow &= ~HPS_CTRL_CORE_RESET;
	write_control();
}

int is_fpga_ready(int quick)
{
	(void)quick;
	return csr_ok;
}

void fpga_spi_en(uint32_t mask, uint32_t en)
{
	if (spi_en_trace) printf("fpga_spi_en(%8x, %x)\n", mask, en);
	uint32_t bits = 0;
	if (mask & SSPI_FPGA_EN) bits |= HPS_CTRL_FPGA_EN;
	if (mask & SSPI_OSD_EN)  bits |= HPS_CTRL_OSD_EN;
	if (mask & SSPI_IO_EN)   bits |= HPS_CTRL_IO_EN;
	if (en) control_shadow |= bits; else control_shadow &= ~bits;
	if (csr_ok) write_control();
}

void fpga_wait_to_reset()
{
	printf("FPGA is not ready (no PCIe HPS bridge). Waiting...\n");
	while (!is_fpga_ready(0)) sleep(1);
}

static inline void wait_not_busy()
{
	for (int i = 0; i < 1000; i++) {
		if (!(pcie_readl(csr_status) & HPS_STAT_BUSY)) return;
	}
	printf("hps: transaction stuck busy\n");
}

uint16_t fpga_spi(uint16_t word)
{
	if (spi_trace) printf("fpga_spi(%04x)", word);
	if (!csr_ok) return 0xFFFF;
	pcie_writel(csr_din, word);
	wait_not_busy();
	uint16_t result = pcie_readl(csr_dout) & 0xFFFF;
	if (spi_trace) printf(" => %04x\n", result);
	return result;
}

uint16_t fpga_spi_fast(uint16_t word)
{
	if (spi_trace) printf("fpga_spi_fast(%04x)\n", word);
	if (csr_ok) pcie_writel(csr_din, word);
	return 0;
}

// The SPI implementation sends one zero word before every block; keep that.
static inline void block_prologue() { pcie_writel(csr_din, 0); }

void fpga_spi_fast_block_write(const uint16_t *buffer, uint32_t length)
{
	if (spi_trace) printf("fpga_spi_fast_block_write(%d)\n", length);
	if (!csr_ok) return;
	block_prologue();
	while (length >= 2) {
		pcie_writel(csr_din2, (uint32_t)buffer[0] | ((uint32_t)buffer[1] << 16));
		buffer += 2; length -= 2;
	}
	if (length) pcie_writel(csr_din, *buffer);
}

void fpga_spi_fast_block_read(uint16_t *buf, uint32_t length)
{
	if (!csr_ok) return;
	block_prologue();
	while (length--) {
		pcie_writel(csr_din, 0);
		*buf++ = pcie_readl(csr_dout) & 0xFFFF;
	}
}

void fpga_spi_fast_block_write_8(const uint8_t *buf, uint32_t length)
{
	if (spi_trace) printf("fpga_spi_fast_block_write_8(%d)\n", length);
	if (!csr_ok) return;
	block_prologue();
	while (length >= 2) {
		pcie_writel(csr_din2, (uint32_t)buf[0] | ((uint32_t)buf[1] << 16));
		buf += 2; length -= 2;
	}
	if (length) pcie_writel(csr_din, *buf);
}

void fpga_spi_fast_block_read_8(uint8_t *buf, uint32_t length)
{
	if (spi_trace) printf("fpga_spi_fast_block_read_8(%d)\n", length);
	if (!csr_ok) return;
	block_prologue();
	while (length--) {
		pcie_writel(csr_din, 0);
		*buf++ = pcie_readl(csr_dout) & 0xFF;
	}
}

void fpga_spi_fast_block_write_be(const uint16_t *buf, uint32_t length)
{
	if (spi_trace) printf("fpga_spi_fast_block_write_be(%d)\n", length);
	if (!csr_ok) return;
	block_prologue();
	while (length--) {
		uint16_t w = *buf++;
		pcie_writel(csr_din, (uint16_t)((w << 8) | (w >> 8)));
	}
}

void fpga_spi_fast_block_read_be(uint16_t *buf, uint32_t length)
{
	if (!csr_ok) return;
	block_prologue();
	while (length--) {
		pcie_writel(csr_din, 0);
		uint16_t w = pcie_readl(csr_dout) & 0xFFFF;
		*buf++ = (uint16_t)((w << 8) | (w >> 8));
	}
}

#endif // PCIE_HOST
