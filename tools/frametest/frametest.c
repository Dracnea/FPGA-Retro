/* SPDX-License-Identifier: BSD-2-Clause
 *
 * C1100 PCIe transport bring-up check.
 *
 * The gateware's frame source emits (frame_no << 24) | pixel_index as 32-bit
 * words, so DMA integrity here is a word-for-word comparison rather than a
 * judgement by eye. This:
 *
 *   1. reads board identity, link status and PCIe sizing from CSRs
 *   2. exercises the scratch register (BAR read/write integrity)
 *   3. streams the frame source card->host over DMA and verifies every word
 *   4. reports sustained throughput
 *   5. measures enable->first-word latency, which is the number that decides
 *      whether the retro video path is viable
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>
#include <inttypes.h>

#include "liblitepcie.h"

#define DEVICE "/dev/litepcie0"

#define CSR_IDENT_BASE                  0x1000L
#define CSR_CTRL_SCRATCH                0x0004L
#define CSR_FRAME_SOURCE_ENABLE         0x0800L
#define CSR_FRAME_SOURCE_FRAMES         0x0804L
#define CSR_FRAME_SOURCE_PIXELS         0x0808L
#define CSR_PCIE_PHY_LINK_STATUS        0x3000L
#define CSR_PCIE_PHY_MSI_ENABLE         0x3004L
#define CSR_PCIE_PHY_BUS_MASTER_ENABLE  0x3008L
#define CSR_PCIE_PHY_MAX_REQUEST_SIZE   0x300cL
#define CSR_PCIE_PHY_MAX_PAYLOAD_SIZE   0x3010L

#define WIDTH  320
#define HEIGHT 240
#define NPIX   (WIDTH * HEIGHT)

static double now_us(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1e6 + ts.tv_nsec / 1e3;
}

static void read_ident(int fd, char *out, size_t n)
{
    size_t i;
    for (i = 0; i < n - 1; i++) {
        uint32_t c = litepcie_readl(fd, CSR_IDENT_BASE + 4 * i);
        out[i] = (char)(c & 0xff);
        if (!out[i]) break;
    }
    out[i] = 0;
}

int main(void)
{
    int fd = open(DEVICE, O_RDWR);
    if (fd < 0) { perror("open " DEVICE); return 1; }

    /* ---- 1. identity and link ------------------------------------------ */
    char ident[256];
    read_ident(fd, ident, sizeof(ident));

    printf("== board ==\n");
    printf("identifier          : %s\n", ident);
    printf("phy link status     : 0x%08x\n", litepcie_readl(fd, CSR_PCIE_PHY_LINK_STATUS));
    printf("bus master enable   : %u\n",    litepcie_readl(fd, CSR_PCIE_PHY_BUS_MASTER_ENABLE));
    printf("msi enable          : %u\n",    litepcie_readl(fd, CSR_PCIE_PHY_MSI_ENABLE));
    printf("max request size    : %u B\n",  litepcie_readl(fd, CSR_PCIE_PHY_MAX_REQUEST_SIZE));
    printf("max payload size    : %u B\n",  litepcie_readl(fd, CSR_PCIE_PHY_MAX_PAYLOAD_SIZE));

    /* ---- 2. scratch (BAR integrity) ------------------------------------ */
    printf("\n== scratch register ==\n");
    const uint32_t pats[] = {0x00000000, 0xffffffff, 0x5a5a5a5a, 0xa5a5a5a5, 0x12345678};
    int scratch_fail = 0;
    for (unsigned i = 0; i < sizeof(pats)/sizeof(pats[0]); i++) {
        litepcie_writel(fd, CSR_CTRL_SCRATCH, pats[i]);
        uint32_t rb = litepcie_readl(fd, CSR_CTRL_SCRATCH);
        int ok = (rb == pats[i]);
        if (!ok) scratch_fail++;
        printf("  wrote 0x%08x  read 0x%08x  %s\n", pats[i], rb, ok ? "ok" : "MISMATCH");
    }
    litepcie_writel(fd, CSR_CTRL_SCRATCH, 0x12345678);
    printf("  result: %s\n", scratch_fail ? "FAIL" : "PASS");

    /* ---- 3/4/5. DMA card->host ----------------------------------------- */
    printf("\n== DMA card->host ==\n");

    /* Start from a known-quiet state. */
    litepcie_writel(fd, CSR_FRAME_SOURCE_ENABLE, 0);

    struct litepcie_dma_ctrl dma;
    memset(&dma, 0, sizeof(dma));
    dma.use_writer = 1;
    dma.loopback   = 0;

    if (litepcie_dma_init(&dma, DEVICE, 0)) {
        fprintf(stderr, "litepcie_dma_init failed\n");
        close(fd);
        return 1;
    }

    uint32_t frames0 = litepcie_readl(fd, CSR_FRAME_SOURCE_FRAMES);
    uint32_t pixels0 = litepcie_readl(fd, CSR_FRAME_SOURCE_PIXELS);

    double t_enable = now_us();
    litepcie_writel(fd, CSR_FRAME_SOURCE_ENABLE, 1);

    uint64_t words = 0, errors = 0;
    int have_prev = 0;
    uint32_t prev = 0;
    uint64_t first_word = 0;
    double t_first = 0;
    int64_t bytes = 0;
    const int64_t target_bytes = 64ll << 20;   /* 64 MiB */
    double t_start = 0;
    int spins = 0;

    while (bytes < target_bytes && spins < 200000) {
        litepcie_dma_process(&dma);
        char *buf = litepcie_dma_next_read_buffer(&dma);
        if (!buf) { spins++; continue; }

        if (!t_first) {
            t_first = now_us();
            first_word = *(uint32_t *)buf;
            t_start = t_first;
        }

        uint32_t *w = (uint32_t *)buf;
        unsigned nw = DMA_BUFFER_SIZE / 4;
        for (unsigned i = 0; i < nw; i++) {
            uint32_t v = w[i];
            if (have_prev) {
                uint32_t pi = prev & 0x00ffffff, pf = prev >> 24;
                uint32_t ei = (pi == (uint32_t)(NPIX - 1)) ? 0 : pi + 1;
                uint32_t ef = (pi == (uint32_t)(NPIX - 1)) ? ((pf + 1) & 0xff) : pf;
                uint32_t expect = (ef << 24) | ei;
                if (v != expect) {
                    if (errors < 8)
                        printf("  MISMATCH at word %" PRIu64 ": got 0x%08x expected 0x%08x\n",
                               words, v, expect);
                    errors++;
                }
            }
            prev = v; have_prev = 1; words++;
        }
        bytes += DMA_BUFFER_SIZE;
    }
    double t_end = now_us();

    uint32_t frames1 = litepcie_readl(fd, CSR_FRAME_SOURCE_FRAMES);
    uint32_t pixels1 = litepcie_readl(fd, CSR_FRAME_SOURCE_PIXELS);
    litepcie_writel(fd, CSR_FRAME_SOURCE_ENABLE, 0);

    litepcie_dma_cleanup(&dma);

    double secs = (t_end - t_start) / 1e6;
    printf("  buffer size       : %d B x %d\n", DMA_BUFFER_SIZE, DMA_BUFFER_COUNT);
    printf("  first word        : 0x%08" PRIx64 "  (frame %" PRIu64 ", pixel %" PRIu64 ")\n",
           first_word, first_word >> 24, first_word & 0x00ffffff);
    printf("  enable -> 1st word: %.1f us\n", t_first ? (t_first - t_enable) : -1.0);
    printf("  bytes transferred : %" PRId64 " (%.1f MiB)\n", bytes, bytes / 1048576.0);
    printf("  words checked     : %" PRIu64 "\n", words);
    printf("  sequence errors   : %" PRIu64 "\n", errors);
    if (secs > 0)
        printf("  throughput        : %.2f Gbps (%.0f MB/s)\n",
               bytes * 8 / secs / 1e9, bytes / secs / 1e6);
    printf("  frames counter    : %u -> %u (+%u)\n", frames0, frames1, frames1 - frames0);
    printf("  pixels counter    : %u -> %u\n", pixels0, pixels1);

    double fps = secs > 0 ? (frames1 - frames0) / secs : 0;
    printf("  frame rate        : %.0f fps at %dx%d\n", fps, WIDTH, HEIGHT);

    printf("\n== verdict ==\n");
    printf("  scratch/BAR       : %s\n", scratch_fail ? "FAIL" : "PASS");
    printf("  DMA integrity     : %s\n",
           (words && errors == 0) ? "PASS (word-for-word)" : "FAIL");

    close(fd);
    return (scratch_fail || errors || !words) ? 1 : 0;
}
