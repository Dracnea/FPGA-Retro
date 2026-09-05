# Bitstreams

Built images, kept in the repo so a card can be brought up without a Vivado
seat. **The md5 is the identity, not the filename** — record it and check it.

| file | md5 | part | built from | verified |
|---|---|---|---|---|
| `c1100_pcie_video_transport.bit` | `496aca5739e08b33e44b763ee8eeba8e` | xcu55n-fsvh2892-2LV-e | `overlay/mistex_boards/c1100_pcie_video.py` — LitePCIe gen3 x4 endpoint, DMA with scatter-gather, `(frame << 24) \| pixel_index` frame source, `hbm_cattrip` low | **On hardware 2026-09-05:** enumerates as `10ee:9034`, BAR0 128 KiB, link trained 8.0 GT/s × 4, MSI bound, `litepcie` driver attached. Timing-clean at build: WNS +0.721 ns. DMA integrity test written (`tools/frametest`), not yet run (needs root on `/dev/litepcie0`). |
| `fk33_platform_smoke.bit` | `e2a0fd0745c7c516bfc650d6d69ee740` | xcvu33p-fsvh2104-2-e | `overlay/mistex_boards/sqrl_fk33_mistex.py smoke` — CRG from the 200 MHz oscillator plus a kept counter on the LEDs | Builds and closes timing; **no FK33 is attached to this host**, so unverified on silicon. |

Loading the C1100 image: JTAG (`program_hw_devices` from Vivado, or `fjtag
--load`), then `sudo tools/pcie-bringup.sh` to drop the stale PCIe identity and
rescan. A card that held a bitstream with no PCIe endpoint needs that rescan (or
a warm reboot) before the host sees the new device.

Not here: the out-of-context core fits in `build/fit_*` produce checkpoints, not
bitstreams — a core becomes a bitstream only once it sits in a board target with
the video sink and host interface (`docs/retro-cores.md`).
