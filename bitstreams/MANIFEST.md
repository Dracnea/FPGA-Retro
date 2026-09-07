# Bitstreams

Built images, kept in the repo so a card can be brought up without a Vivado
seat. **The md5 is the identity, not the filename** — record it and check it.

| file | md5 | part | built from | verified |
|---|---|---|---|---|
| `c1100_pcie_video_transport.bit` | `496aca5739e08b33e44b763ee8eeba8e` | xcu55n-fsvh2892-2LV-e | `overlay/mistex_boards/c1100_pcie_video.py` — LitePCIe gen3 x4 endpoint, DMA with scatter-gather, `(frame << 24) \| pixel_index` frame source, `hbm_cattrip` low | **On hardware 2026-09-05:** enumerates as `10ee:9034`, BAR0 128 KiB, link trained 8.0 GT/s × 4, MSI bound, `litepcie` driver attached. **No register read was verified**, and on 2026-09-07 the two images derived from it read `0xffffffff` from every CSR; run `sudo tools/pcie-diag.sh` on this image next (`docs/c1100-pcie-transport.md`). Timing-clean at build: WNS +0.721 ns. DMA integrity test written (`tools/frametest`), not yet run. |
| `fk33_platform_smoke.bit` | `e2a0fd0745c7c516bfc650d6d69ee740` | xcvu33p-fsvh2104-2-e | `overlay/mistex_boards/sqrl_fk33_mistex.py smoke` — CRG from the 200 MHz oscillator plus a kept counter on the LEDs | Builds and closes timing; **no FK33 is attached to this host**, so unverified on silicon. |

| `c1100_ps2_iop.bit` | `9164ab8c3f872f460f6694d0dd60f8ec` | xcu55n-fsvh2892-2LV-e | `overlay/mistex_boards/c1100_ps2_iop.py` — the same PCIe endpoint plus the PS2 IOP subsystem (`overlay/cores/PS2`: CPU, RAM/ROM, INTC, timers, SPU2 as two PSX SPUs, SIO2 with a pad on `iop_pad0`, CDVD with no disc) on CSRs; its `csr.csv` is `c1100_ps2_iop.csr.csv` here, which `tools/ps2iop/iop_post.py` needs | Builds and closes timing: WNS +0.168 ns, 98,932 endpoints, 0 failing; 20,791 LUTs, 82 BRAM, 224 URAM. **Loaded over JTAG 2026-09-07:** `DONE=1 EOS=1 CRC_ERR=0`, enumerates as `10ee:9034`, driver binds — and every BAR0 read returns `0xffffffff`, so the POST run produced no result (`docs/ps2-iop-bringup.md`, `docs/c1100-pcie-transport.md`). |
| `c1100_hps_test.bit` | `23a727f5aa4172cbcd58a3c20dfee886` | xcu55n-fsvh2892-2LV-e | `overlay/mistex_boards/c1100_hps_test.py` — the same PCIe endpoint plus the `hps_pcie` bridge driving a real `hps_io.sv` (config string `HPSTEST;;...`) in a 50 MHz core domain; `csr.csv` beside it is what `host/main_mistex_pcie` reads | Builds and closes timing: WNS +0.731 ns, 28,504 endpoints, 0 failing; 4,797 LUTs, 23 BRAM. **Not loaded** (card busy 2026-09-06). Expected first result with Main: `got: 'HPSTEST;;O1,Option one,...'` — `docs/host-gui-compatibility.md`. |
| `c1100_hps_video_test.bit` | `9680c6a7693fa6fefc8929b0fb5a7b78` | xcu55n-fsvh2892-2LV-e | `overlay/mistex_boards/c1100_hps_video_test.py` — `c1100_hps_test` plus a 640x480 pattern generator through `rtl/video_sink` into DMA0 as a FRM1 stream; `csr.csv` beside it serves both `host/main_mistex_pcie` and `host/viewer` | Builds and closes timing: WNS +0.598 ns, 31,213 endpoints, 0 failing; 5,214 LUTs. **Not loaded** (card busy 2026-09-06). **Loaded 2026-09-07:** `DONE=1 EOS=1 CRC_ERR=0`, enumerates, driver binds, and every BAR0 read returns `0xffffffff` (`video_dims` included), no DMA data; `docs/host-video-path.md`, `docs/c1100-pcie-transport.md`. Supersedes `c1100_hps_test.bit` for the HPS test too. |

Loading the C1100 image: JTAG (`program_hw_devices` from Vivado, or `fjtag
--load`), then `sudo tools/pcie-bringup.sh` to drop the stale PCIe identity and
rescan. A card that held a bitstream with no PCIe endpoint needs that rescan (or
a warm reboot) before the host sees the new device.

Not here: the out-of-context core fits in `build/fit_*` produce checkpoints, not
bitstreams — a core becomes a bitstream only once it sits in a board target with
the video sink and host interface (`docs/retro-cores.md`).
| `c1100_pcie_diag.bit` | `1498d0361c1231a34333fb41f090431e` | xcu55n-fsvh2892-2LV-e | `overlay/mistex_boards/c1100_pcie_diag.py` — the transport design plus UARTbone on FPGA UART 0 (BJ41/BK41, shows up as `/dev/ttyUSB2`, 115200) two LiteScope analyzers (`zanalyzer_pcie.csv`, `zanalyzer_sys.csv` beside it) and the hard block's own status outputs as `zhardip_*` CSRs (`tools/pcie-hardip.py`); pcie_* CSR addresses identical to the transport image | Built 2026-09-07: WNS −0.006 ns on two paths inside the pcie-domain analyzer's own trigger memory, nothing in the design under test. **Loaded the same day:** identifier, scratch write/read, PHY link status and both analyzers all work over the UART (`tools/uart-probe.sh`, `tools/pcie-scope.py`); `docs/c1100-pcie-transport.md`. |
