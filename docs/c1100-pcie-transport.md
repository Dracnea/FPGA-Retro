# C1100 PCIe transport — verified build result

Stage 3 of the retro video path (`PCIe → host RAM`), built standalone so the
link and the DMA are proven before anything is built on top of them.

Build target: `overlay/mistex_boards/c1100_pcie_video.py`
Device: `xcu55n-fsvh2892-2LV-e` (Varium C1100 / Alveo U55N)
Toolchain: Vivado 2026.1

## Result

```
WNS +0.721   TNS 0.000   WHS +0.011   THS 0.000
27,816 endpoints, 0 failing
All user specified timing constraints are met.
```

`build/c1100_pcie/gateware/xilinx_c1100.bit` — 56,660,149 bytes,
md5 `496aca5739e08b33e44b763ee8eeba8e`.

Loaded over JTAG onto a physical C1100; `End of startup status: HIGH`.

## Cost

| resource | used | available | util |
|---|---:|---:|---:|
| CLB LUTs | 4,579 | 871,680 | **0.53%** |
| CLB Registers | 8,776 | 1,743,360 | 0.50% |
| Block RAM tiles | 24 | 1,344 | 1.79% |
| URAM | 0 | 640 | 0% |
| DSP | 0 | 5,952 | 0% |

This is the number that matters for the whole project: a full PCIe gen3 x4
endpoint with scatter-gather DMA and a frame source costs **half a percent** of
the device. The multi-instance goal — several complete retro systems resident at
once — is well supported by this part, and ~28 MB of untouched on-chip memory is
enough to hold multiple 8/16-bit systems with no external memory at all.

## What the design contains

- PCIe gen3 x4 endpoint (`USPPCIEDMA`), 128-bit datapath, BAR0 128 KB
- LitePCIe DMA with scatter-gather, MSI
- `hbm_cattrip` driven low (see the trap in the README)
- A frame generator emitting `(frame << 24) | pixel_index`, so DMA integrity is
  a **word-for-word check rather than a judgement by eye**
- Host software generated alongside: kernel driver, `litepcie_util.c`,
  `litepcie_test.c`, `csr.csv`, generated headers

SoC identifier string: `C1100 PCIe video transport x4 gen3`.

## Bringing the link up

The host enumerates BARs at boot. A card that previously held a bitstream with
no PCIe endpoint will still show its stale factory identity after a JTAG load,
so the host must be told to look again:

```sh
# after programming over JTAG
sudo sh -c 'echo 1 > /sys/bus/pci/devices/0000:XX:00.0/remove; sleep 1; echo 1 > /sys/bus/pci/rescan'
lspci -nn -d 10ee:      # expect 10ee:9034 with a 128K BAR0
```

A warm reboot achieves the same thing. `build/.../software/rescan.py` automates
this, but note it only removes devices whose IDs are in its own list — a card
sitting on a factory shell ID will not match, so remove it by address as above.

## The reset-CDC constraint — three attempts, and why the first two failed

The design initially missed timing at **WNS −0.806** on exactly one path:
`soc_rst` crossing from the 125 MHz sys domain into the 100 MHz input domain,
0.399 ns of delay against a 2.000 ns requirement. One endpoint. Every real clock
domain passed comfortably. The diagnosis was right from the start; applying it
correctly took three tries.

| attempt | mechanism | result |
|---|---|---|
| 1 | `set_max_delay -datapath_only -from …` via `add_platform_command` | **applied but ineffective** — matched 4 real cells, appeared in `report_exceptions`, moved slack only −0.806 → −0.802. A `-from` with no `-to` does not override the inter-clock requirement. |
| 2 | `set_clock_groups` via `add_platform_command` | **silently inert** — landed at XDC line 79, *before* the `create_clock` statements, so both clock names matched nothing. Identical −0.806. |
| 3 | `add_false_path_constraints_by_name` | lands in the pre-placement `.tcl`, after synthesis, when the clocks resolve. **+0.721.** |

**The lesson worth carrying forward.** Attempt 2 was verified against a routed
checkpoint first, where it produced +0.729 slack exactly as intended — and then
did nothing in the build. A checkpoint has every clock already resolved, while
the build XDC is read *in order*. Checkpoint verification proves a constraint's
semantics but says nothing about whether it will resolve at the point the flow
reads it.

LiteX's own API documents the trap:

```python
def add_false_path_constraints_by_name(self, *clock_names):
    # On Vivado, some generated/internal clocks are only resolvable after synthesis.
    # Emit explicit set_clock_groups in pre_placement commands for robust resolution.
```

Both failures shared a shape: **a constraint that reads correctly, emits a
warning nobody looks at, and produces a build indistinguishable from having no
constraint at all.** The tell was in the log each time — `No clocks matched`,
and `CRITICAL WARNING: [Vivado 12-4739] set_clock_groups: No valid object(s)
found`. Grep builds for those two signatures.

The final +0.721 landed within 8 ps of the +0.729 measured on the checkpoint,
confirming the checkpoint experiment had been predicting the right thing all
along — only the delivery mechanism was wrong.

### Not our warnings

Build 3 still reports two `12-4739` criticals. Both come from **Xilinx's own
generated PCIe IP constraints** (`ip_pcie4c_uscale_plus_impl_x1y0.xdc`:
`set_false_path -from [get_pins sys_reset]`, and a switching-activity constraint
that only affects power estimation). Build 2 had ten; the eight that vanished
were ours.

## Hardware bring-up, verified

Loaded over JTAG (`End of startup status: HIGH`), then PCIe remove + rescan.
The endpoint enumerates and the driver binds:

```
c1:00.0 Memory controller [0580]: Xilinx Corporation Device [10ee:9034]
        Control: Mem+ BusMaster+
        Region 0: Memory at b6c00000 (32-bit, non-prefetchable) [size=128K]
        Kernel driver in use: litepcie
/dev/litepcie0
```

Link parameters read from sysfs:

| | |
|---|---|
| current / max link speed | 8.0 GT/s (gen3) |
| current / max link width | x4 |
| MSI | allocated, irq 347 |

Link trained at the design's full target, gen3 x4, with no downshift.

### 2026-09-07: BAR0 reads return 0xFFFFFFFF — the endpoint enumerates but no register is reachable

The section above verified enumeration, link training and driver binding. It
did **not** verify a register read: no `litepcie_util info` output was
recorded, and none of the three images derived from this design had been
loaded. Today two of them were (`c1100_ps2_iop.bit`, then
`c1100_hps_video_test.bit`), with the same result on both:

```
litepcie 0000:c1:00.0: Version \xff\xff\xff...          (driver probe)
SoC Identifier   : ����...                               (litepcie_util info)
Write 0x12345678 to Scratch register:  Read: 0xffffffff  (litepcie_util scratch_test)
video_dims / video_frames / video_drops : ffffffff        (tools/csrw.py)
iop_status : ffffffff                                     (tools/ps2iop/iop_post.py)
```

Host side, identical to the 09-05 record: `10ee:9034`, BAR0 at `b6c00000`
(128 K, inside the root port's window `b6c00000-b6cfffff`, assigned on
rescan), `Control: Mem+ BusMaster+`, LnkSta 8 GT/s x4, MSI allocated,
`litepcie` bound, no AER or link message in the kernel log. Config-space
access therefore works (it is answered by the hard IP) and memory access
to BAR0 does not (it is answered by the fabric). `c1100_pcie_video_transport.bit`
itself has not been re-tested since 09-05 and was never read from, so as
of today **no register read has ever succeeded on this card** — this is a
bring-up defect in the base transport design, not a regression in the
derived images.

Ruled out from user space: the 100 MHz input (BK43/BK44 is the pin every
working design on this card uses, Corundum's `clk_100mhz_1`); pin placement
(`xilinx_c1100_io.rpt` shows the lanes on quad 227, refclk on `MGTREFCLK0_225`,
and the link trained); the driver (`ctrl_scratch` reads ff through the
driver's ioctl, the driver's own probe read the identifier as ff).

Three cases remain, and they are distinguishable only from the root port's
status registers, which need root. `tools/pcie-diag.sh` (run with sudo,
default image the transport one) clears the status bits on both ends,
reads BAR0 directly through `resource0` with the driver unloaded, times the
reads, then dumps `DevSta`/`UESta`/`CESta` on both ends and the kernel log:

| case | what the host sees | meaning |
|---|---|---|
| completion timeout | reads take ms each; root port `DevSta` CorrErr/NonFatal, `UESta` CmpltTO | the endpoint never answered: the CQ → sys crossing is stuck, i.e. the sys domain is not running or is held in reset |
| unsupported request | reads fast; endpoint `DevSta UnsupReq+`, root port `Status: <MAbort+` | the endpoint rejected the BAR hit: BAR/aperture mismatch between the IP and the depacketizer |
| completion with data ff | reads fast; no error bits anywhere | the endpoint answered: LiteX's wishbone timeout returned ff, so the on-chip address decode never selected the CSR bridge |

Until that has run, every hardware claim below the enumeration section for
`c1100_hps_test`, `c1100_hps_video_test` and `c1100_ps2_iop` stands
unverified, and the PS2 IOP `hw-test.sh` output of 2026-09-07 (POST FF,
`cpu_error` 1, counts 0xffffffff) is the all-ones read, not an IOP result.

**Device node permissions.** The driver creates `/dev/litepcie0` as
`root:root 0600`, so every tool needs root. `tools/99-litepcie.rules` relaxes
this to the `plugdev` group, which makes iterating on measurements practical.
