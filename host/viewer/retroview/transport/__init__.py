"""Transports: where the FRM1 bytes come from.

  litepcie   Linux, the LitePCIe kernel driver's DMA ring (the card)
  file       replay of a recorded stream
  synth      generated test frames, no hardware
  windows    placeholder naming what a Windows backend needs
"""
from .base import Transport, Recorder
from .file import FileTransport, SynthTransport


def open_transport(name: str, **kw) -> Transport:
    if name == "litepcie":
        from .litepcie import LitePCIeTransport
        return LitePCIeTransport(**kw)
    if name == "file":
        return FileTransport(**kw)
    if name == "synth":
        return SynthTransport(**kw)
    if name == "windows":
        from .windows import WindowsTransport
        return WindowsTransport(**kw)
    raise ValueError(f"unknown transport {name!r}")
