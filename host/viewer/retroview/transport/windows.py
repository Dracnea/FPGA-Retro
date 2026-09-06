from .base import Transport


class WindowsTransport(Transport):
    """Placeholder for the Windows backend.

    The decision (2026-09-06) is Windows-specific driver files rather than a
    different gateware transport. What this class needs to exist:

    * a signed Windows kernel driver for the LitePCIe endpoint (vendor
      10ee, device 9034 as built here) exposing what the Linux driver
      exposes: BAR0 register read/write, the writer DMA ring (256 x 8 KiB
      host buffers, hardware and software counters), and an event or
      overlapped-I/O wake when a buffer completes -- e.g. a KMDF driver
      with DeviceIoControl codes mirroring LITEPCIE_IOCTL_*;
    * this class then maps the ring (or copies buffers) and mirrors
      LitePCIeTransport.read() over those calls.

    pygame/SDL2 itself runs on Windows unchanged, so the transport is the
    only missing piece for the viewer there.
    """
    def __init__(self, **_):
        super().__init__()

    def open(self):
        raise NotImplementedError(
            "retroview: no Windows transport yet -- needs a driver exposing the LitePCIe DMA ring "
            "(see retroview/transport/windows.py)")

    def read(self) -> bytes:
        raise NotImplementedError
