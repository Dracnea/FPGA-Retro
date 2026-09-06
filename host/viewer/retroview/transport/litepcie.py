"""Linux: the LitePCIe kernel driver's writer (card -> host) DMA ring.

A line-for-line mirror of liblitepcie's litepcie_dma.c zero-copy path
(software/user/liblitepcie in the generated litepcie software), so it can be
checked against the C without hardware:

  open /dev/litepcieN
  LOCK        request the DMA writer
  DMA         loopback off
  MMAP_DMA_INFO, mmap the rx ring (DMA_BUFFER_COUNT x DMA_BUFFER_SIZE)
  loop:  DMA_WRITER (enable=1) -> hw_count, sw_count
         poll POLLIN
         available = hw_count - sw_count; offset = sw_count % COUNT
         MMAP_DMA_WRITER_UPDATE sw_count = sw_count + available
         hand back `available` buffers starting at offset
  cleanup: DMA_WRITER enable=0, LOCK release, munmap, close

Struct layouts and ioctl numbers are those of software/kernel/litepcie.h
for the x86-64 ABI. Not run here (the card is busy); the first run against
hardware should compare its buffer count and byte rate with litepcie_test.
"""
from __future__ import annotations
import fcntl, mmap, os, select, struct
from .base import Transport

DMA_BUFFER_COUNT = 256
DMA_BUFFER_SIZE  = 8192
DMA_BUFFER_TOTAL = DMA_BUFFER_COUNT * DMA_BUFFER_SIZE

_IOC_WRITE, _IOC_READ = 1, 2
def _ioc(dir_, nr, size):        # Linux _IOC(dir, 'S', nr, size)
    return (dir_ << 30) | (size << 16) | (ord("S") << 8) | nr

# struct litepcie_ioctl_dma        { uint8_t loopback_enable; }                          -> 1
IOCTL_DMA                   = _ioc(_IOC_WRITE, 20, 1)
# struct litepcie_ioctl_dma_writer { uint8_t enable; int64_t hw_count; int64_t sw_count; } -> 24 (u8 + 7 pad)
IOCTL_DMA_WRITER            = _ioc(_IOC_WRITE | _IOC_READ, 21, 24)
DMA_WRITER = struct.Struct("<B7xqq")
# struct litepcie_ioctl_mmap_dma_info { 6 x uint64_t }                                    -> 48
IOCTL_MMAP_DMA_INFO         = _ioc(_IOC_READ, 24, 48)
MMAP_INFO = struct.Struct("<6Q")
# struct litepcie_ioctl_lock { 6 x uint8_t }                                              -> 6
IOCTL_LOCK                  = _ioc(_IOC_WRITE | _IOC_READ, 25, 6)
LOCK = struct.Struct("<6B")
# struct litepcie_ioctl_mmap_dma_update { int64_t sw_count; }                             -> 8
IOCTL_MMAP_DMA_WRITER_UPDATE = _ioc(_IOC_WRITE, 26, 8)
UPDATE = struct.Struct("<q")


class LitePCIeTransport(Transport):
    def __init__(self, device: str = "/dev/litepcie0", poll_ms: int = 100, **_):
        super().__init__()
        self.device, self.poll_ms = device, poll_ms
        self.fd = -1
        self.ring = None
        self._avail = 0
        self._offset = 0
        self.hw_count = self.sw_count = 0

    # -- the C calls, one to one -------------------------------------------
    def _lock(self, req_w, rel_w) -> bool:
        out = fcntl.ioctl(self.fd, IOCTL_LOCK, LOCK.pack(0, req_w, 0, rel_w, 0, 0))
        return bool(LOCK.unpack(out)[5])          # dma_writer_status

    def _writer(self, enable: int):
        out = fcntl.ioctl(self.fd, IOCTL_DMA_WRITER, DMA_WRITER.pack(enable, 0, 0))
        _, self.hw_count, self.sw_count = DMA_WRITER.unpack(out)

    def open(self):
        self.fd = os.open(self.device, os.O_RDWR | os.O_CLOEXEC)
        if not self._lock(1, 0):
            os.close(self.fd); self.fd = -1
            raise RuntimeError(f"{self.device}: DMA writer not available (another process holds it?)")
        fcntl.ioctl(self.fd, IOCTL_DMA, struct.pack("<B", 0))          # loopback off
        info = MMAP_INFO.unpack(fcntl.ioctl(self.fd, IOCTL_MMAP_DMA_INFO, bytes(MMAP_INFO.size)))
        tx_off, tx_size, tx_count, rx_off, rx_size, rx_count = info
        if rx_size != DMA_BUFFER_SIZE or rx_count != DMA_BUFFER_COUNT:
            raise RuntimeError(f"driver ring is {rx_count} x {rx_size}, this module expects "
                               f"{DMA_BUFFER_COUNT} x {DMA_BUFFER_SIZE} (config.h)")
        self.ring = mmap.mmap(self.fd, DMA_BUFFER_TOTAL, mmap.MAP_SHARED,
                              mmap.PROT_READ | mmap.PROT_WRITE, offset=rx_off)
        self._writer(1)

    def read(self) -> bytes:
        if self._avail == 0:
            self._writer(1)                                              # refresh counts
            r, _, _ = select.select([self.fd], [], [], self.poll_ms / 1000.0)
            if not r:
                self.stats.waits += 1
                return b""
            self._avail = self.hw_count - self.sw_count
            self._offset = self.sw_count % DMA_BUFFER_COUNT
            fcntl.ioctl(self.fd, IOCTL_MMAP_DMA_WRITER_UPDATE, UPDATE.pack(self.sw_count + self._avail))
            if self._avail == 0:
                self.stats.waits += 1
                return b""
        start = self._offset * DMA_BUFFER_SIZE
        d = bytes(self.ring[start:start + DMA_BUFFER_SIZE])
        self._avail -= 1
        self._offset = (self._offset + 1) % DMA_BUFFER_COUNT
        self.stats.chunks += 1; self.stats.bytes += len(d)
        return d

    def close(self):
        if self.fd < 0:
            return
        try:
            self._writer(0)
            self._lock(0, 1)
        finally:
            if self.ring:
                self.ring.close(); self.ring = None
            os.close(self.fd); self.fd = -1
