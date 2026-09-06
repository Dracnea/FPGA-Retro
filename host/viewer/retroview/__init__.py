"""retroview -- show the frames an FPGA-Retro card DMAs into host RAM.

The card streams FRM1 (see retroview.stream) through a PCIe DMA ring; a
transport (retroview.transport) hands the bytes to the parser; the viewer
(retroview.viewer) puts each frame on this machine's GPU with pygame/SDL2.
"""
__version__ = "0.1.0"
