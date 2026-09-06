# Bitstreams

Built images, kept in the repo so a card can be brought up without a Vivado
seat. **The md5 is the identity, not the filename** — record it and check it.

| file | md5 | part | built from | verified |
|---|---|---|---|---|
| `c1100_pcie_video_transport.bit` | `496aca5739e08b33e44b763ee8eeba8e` | xcu55n-fsvh2892-2LV-e | `overlay/mistex_boards/c1100_pcie_video.py` — LitePCIe gen3 x4 endpoint, DMA with scatter-gather, `(frame << 24) \| pixel_index` frame source, `hbm_cattrip` low | **On hardware 2026-09-05:** enumerates as `10ee:9034`, BAR0 128 KiB, link trained 8.0 GT/s × 4, MSI bound, `litepcie` driver attached. Timing-clean at build: WNS +0.721 ns. DMA integrity test written (`tools/frametest`), not yet run (needs root on `/dev/litepcie0`). |
| `fk33_platform_smoke.bit` | `e2a0fd0745c7c516bfc650d6d69ee740` | xcvu33p-fsvh2104-2-e | `overlay/mistex_boards/sqrl_fk33_mistex.py smoke` — CRG from the 200 MHz oscillator plus a kept counter on the LEDs | Builds and closes timing; **no FK33 is attached to this host**, so unverified on silicon. |

| `c1100_ps2_iop.bit` | `9164ab8c3f872f460f6694d0dd60f8ec` | xcu55n-fsvh2892-2LV-e | `overlay/mistex_boards/c1100_ps2_iop.py` — the same PCIe endpoint plus the PS2 IOP subsystem (`overlay/cores/PS2`: CPU, RAM/ROM, INTC, timers, SPU2 as two PSX SPUs, SIO2 with a pad on `iop_pad0`, CDVD with no disc) on CSRs; its `csr.csv` is `c1100_ps2_iop.csr.csv` here, which `tools/ps2iop/iop_post.py` needs | Builds and closes timing: WNS +0.168 ns, 98,932 endpoints, 0 failing; 20,791 LUTs, 82 BRAM, 224 URAM. **Not loaded** — the card stays on other work. Procedure and expected output: `docs/ps2-iop-bringup.md`. |
| `c1100_hps_test.bit` | `23a727f5aa4172cbcd58a3c20dfee886` | xcu55n-fsvh2892-2LV-e | `overlay/mistex_boards/c1100_hps_test.py` — the same PCIe endpoint plus the `hps_pcie` bridge driving a real `hps_io.sv` (config string `HPSTEST;;...`) in a 50 MHz core domain; `csr.csv` beside it is what `host/main_mistex_pcie` reads | Builds and closes timing: WNS +0.731 ns, 28,504 endpoints, 0 failing; 4,797 LUTs, 23 BRAM. **Not loaded** (card busy 2026-09-06). Expected first result with Main: `got: 'HPSTEST;;O1,Option one,...'` — `docs/host-gui-compatibility.md`. |

Loading the C1100 image: JTAG (`program_hw_devices` from Vivado, or `fjtag
--load`), then `sudo tools/pcie-bringup.sh` to drop the stale PCIe identity and
rescan. A card that held a bitstream with no PCIe endpoint needs that rescan (or
a warm reboot) before the host sees the new device.

Not here: the out-of-context core fits in `build/fit_*` produce checkpoints, not
bitstreams — a core becomes a bitstream only once it sits in a board target with
the video sink and host interface (`docs/retro-cores.md`).
