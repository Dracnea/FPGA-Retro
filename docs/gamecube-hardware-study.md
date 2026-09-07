# GameCube ("Dolphin") hardware study: what is documented, what exists in HDL, and what a C1100 recreation would take

Written 2026-09-07 as the GameCube counterpart of
[ps2-hardware-study.md](ps2-hardware-study.md), and as the follow-up to the
GameCube paragraph in [retro-cores.md](retro-cores.md). Same method: sources
ranked, then the board, the chips, the buses and memories, then the RTL that
exists and the RTL that would have to be written, then a sizing scaled from
what has actually been fitted on these cards, then the clock problem with
numbers, then the order of work. The PS2 pass taught several things that
change the order here; they are called out where they apply.

## 0. What is not used, and why

The 2020 Nintendo leaks (the July "gigaleak" and the September "Emerald"
leak) contain Nintendo's internal GameCube/Wii documentation, SDK sources
and, in the Emerald set, ATI's Verilog for the Wii's Hollywood/"Vegas"
graphics chip — the direct descendant of the GameCube's Flipper
([RetroReversing's index](https://www.retroreversing.com/emeraldleak),
[Wikipedia](https://en.wikipedia.org/wiki/Nintendo_data_leak)). **None of it
is used here, downloaded here, or cited here.** It is stolen copyrighted
material; this repository is public; and a design derived from it could
never be published, which defeats the purpose. Everything below is built
from public documentation, public reverse engineering, and the behaviour of
Dolphin and the decompilation projects, exactly as the PS2 study kept Sony's
manuals out of the tree.

"Game code leaks with recompile for PC" therefore means the **clean-room
decompilation projects**: Super Smash Bros. Melee, Super Mario Sunshine and
Mario Kart: Double Dash under [doldecomp](https://github.com/doldecomp),
[Metroid Prime](https://decomp.dev/PrimeDecomp/prime) (36 % as of June
2026), Pikmin (33 %), and the rest indexed at
[gamecube.dev](https://gamecube.dev/) and
[RetroReversing](https://www.retroreversing.com/source-code/decompiled-retail-console-games).
They are legitimate, and for this purpose they are better than leaked
sources: they show exactly how retail games drive the GX FIFO, the DSP, the
EXI devices and the timers, which is the behaviour an FPGA has to reproduce.

## 1. Sources, ranked by authority

| source | what it is | covers |
|---|---|---|
| **IBM PowerPC 750CX/750CXe User's Manual** (public IBM documents; the Gekko is a 750CXe with paired-single and other extensions) | the CPU vendor's own | pipeline, caches, MMU (BATs + TLB), exceptions, timebase, every base instruction and its timing; everything except the Gekko additions |
| [**YAGCD**](https://www.gc-forever.com/yagcd/) — *Yet Another GameCube Documentation* (groepaz/hitmen; [WiiBrew entry](https://wiibrew.org/wiki/YAGCD), [PDF mirror](https://wiki.retrotechcollection.com/Yet_Another_GameCube_Documentation_(YAGCD))) | community, nocash-style | memory map; **chapter 5**, the hardware registers of CP, PE, VI, PI, MI, DSP, DI, SI, EXI, AI at 0xCC000000-0xCC008000; chapter 10, the EXI devices (memory card, IPL ROM/RTC/SRAM, modem, broadband adapter); disc and file formats; Gekko register and calling conventions |
| [**Dolphin**](https://github.com/dolphin-emu/dolphin) source | the executable specification, as PCSX2 is for the PS2 | `Core/HW/` (AudioInterface, VideoInterface, ProcessorInterface, MemoryInterface, GPFifo, MMIO, DSP with both an HLE and a **cycle-level LLE** core, EXI, SI, DVD, SystemTimers); `Core/PowerPC/` (the Gekko interpreter: paired singles, quantised loads/stores, the HID registers, the exact non-IEEE corners); `VideoCommon/` (BP/CP/XF register files, the vertex loader, TEV, texture decoders, EFB copy formats) |
| [**dolphin-emu/hwtests**](https://github.com/dolphin-emu/hwtests) | tests written to run on real hardware and pin Dolphin's behaviour | a ready-made conformance suite for an FPGA recreation: it is what the IOP boot ROM was for the PS2 pass, already written |
| [**libogc / devkitPPC**](https://github.com/devkitPro/libogc) | the free homebrew SDK | working, buildable reference for initialising every block (GX, DSP, VI, EXI, SI, DVD) without any Nintendo code; the source of every bring-up test program |
| [Copetti, *GameCube Architecture*](https://www.copetti.org/writings/consoles/gamecube/) | secondary, well cited | the block-level numbers below |
| [GC-Forever wiki](https://www.gc-forever.com/wiki/index.php?title=Hardware_Acronyms) (hardware acronyms, [board versions](https://www.gc-forever.com/wiki/index.php?title=GameCube_versions)) | community | which chip revision on which board; DOL-001 vs DOL-101 |
| [iFixit teardown](https://www.ifixit.com/Device/Nintendo_GameCube), [teardown guide](https://manuals.plus/m/9e1ec85447b03abf5bdde05591c84be2c3b9cbca9e4094d869e293f3d0796593_doc) | photos | board layout, chip designators, connectors |
| Wikipedia [Gekko](https://en.wikipedia.org/wiki/Gekko_(processor)), [technical specifications](https://en.wikipedia.org/wiki/GameCube_technical_specifications); [AnandTech on Flipper's eDRAM](https://anandtech.com/show/858/5) | secondary | process, die sizes, transistor counts |

**No service manual or official schematic for the DOL-001 is public**, unlike
the PS2's SCPH manuals. The board is known from teardowns and from the
community's pinouts of its connectors and of the digital AV port; that is
enough, because — as with the PS2 — a recreation reproduces the chips'
interfaces, not the board's traces. Where the PS2 had Sony's own EE/GS/VU
manuals, the GameCube has IBM's manual for the CPU and only community
documentation for Flipper; Dolphin's `VideoCommon` is the closest thing to a
Flipper manual that exists in public.

## 2. The board

A DOL-001 main board carries, per the teardowns, Copetti and the GC-Forever
wiki:

| block | part | notes |
|---|---|---|
| CPU "Gekko" | IBM, 180 nm copper, ~43 mm², ~4.9 W | PowerPC 750CXe core + paired singles, **486 MHz** |
| "Flipper" | ArtX/ATI, NEC 180 nm eDRAM process, 51 M transistors, about half of them the on-die 1T-SRAM | GPU + northbridge + DSP + all I/O controllers, **162 MHz** (CPU/3); 2 MB embedded frame buffer + 1 MB texture memory on die |
| main memory "Splash" | 2 × 12 MB MoSys 1T-SRAM | 64-bit bus at 162 MHz, ~1.3 GB/s (Copetti; the MoSys parts are clocked at 324 MHz internally) |
| auxiliary memory ARAM | 16 MB DRAM | 8-bit serial link to Flipper at 81 MHz, DMA only; audio samples, and games use it as swap |
| IPL / RTC / SRAM | one EXI device (Macronix), the boot ROM is XOR-scrambled | `Dolphin OS` init, main menu |
| video encoder | separate DAC/encoder chip; DOL-001 also has the **digital AV port** carrying the encoder's digital input | the digital port is why 480p component exists |
| DVD drive | mini-DVD, CAV, 2-3.1 MB/s, with its own drive controller and firmware | protocol known through Dolphin and homebrew drive replacements |
| controllers | 4 × SI ports (proprietary 1-wire serial), 2 × memory-card slots (EXI), 2 × serial ports (EXI, 32 MHz), 1 × hi-speed parallel port (8-bit, 80 MHz, hangs off ARAM's side: Game Boy Player) | |

Two facts matter for a recreation, as two did for the PS2: **every clock
is a ratio of one reference** — Gekko 486, Flipper and both memory buses
162, ARAM 81, EXI 32 (from a separate crystal) — so the system is two clock
domains with exact ratios; and **Flipper is a single die holding the GPU,
the DSP and every I/O block**, so unlike the PS2 (where EE, GS and IOP are
three chips with documented interfaces) the GameCube's internal buses are
known only through their registers, not their signals. The register map
(YAGCD ch. 5) is the interface.

## 3. The chips, block by block

### 3.1 Gekko

From IBM's 750CX/CXe manual plus Dolphin's `PowerPC/` for the additions:

- 32-bit PowerPC, 4-stage base pipeline (FPU 7, load/store 5), **up to
  three instructions issued per clock** (two integer or one integer plus
  one FP, plus a branch), in-order issue with out-of-order completion via
  rename buffers and a completion queue; branch prediction with a BTIC.
- 32 KB 8-way I-cache, 32 KB 8-way D-cache (the D-cache's upper half can be
  locked as a 16 KB scratchpad), **256 KB unified L2** on die, 64-bit
  external bus at 162 MHz.
- MMU: 4 instruction + 4 data BAT pairs (block translation, what games
  actually use) plus a 64-entry two-way TLB with hardware table walk.
- FPU: 64-bit double precision, and the Gekko additions — **paired singles**
  (two 32-bit floats in one FPR, ~50 SIMD instructions: `ps_add`, `ps_mul`,
  `ps_madd`, `ps_merge`, `ps_sum`, dot products), **quantised load/store**
  (`psq_l`/`psq_st` converting to and from packed 8/16-bit integers through
  the GQR scale registers), and the **write-gather pipe** (a 128-byte buffer
  at a fixed address that turns stores into 32-byte bursts; it is how the CPU
  feeds the GX FIFO).
- Dolphin's interpreter is the reference for the non-IEEE corners (paired
  single rounding, `frsqrte` tables, denormal handling with HID2 bits).

### 3.2 Flipper: the GPU ("GX")

Known through Dolphin's `VideoCommon` and YAGCD; the block names are
Nintendo's SDK names, which the decompilations use everywhere:

- **CP** (command processor): reads the GX FIFO (a ring in main memory that
  the CPU fills through the write-gather pipe, with high/low watermark
  interrupts), decodes the 8-bit opcodes (`BP`/`CP`/`XF` register loads,
  vertex-array draws, display-list calls), drives the vertex loader.
- **Vertex loader / XF** (transform unit): fixed-function T&L. Position and
  normal matrices from a 64 × 4 matrix memory, up to 8 texture-coordinate
  generators, lighting with up to 8 lights, per-vertex colour channels;
  the vertex formats are indexed or direct with per-attribute widths.
- **Setup/rasteriser**: triangles, quads, lines, points; **4 pixel pipes
  in a 2 × 2 quad**, up to 8 pixels per clock on Z-only.
- **Texture units**: 4, up to **8 textures per pixel**, from **1 MB TMEM**
  (1T-SRAM) used as a cache plus preloaded regions; formats I4/I8/IA4/IA8/
  RGB565/RGB5A3/RGBA8/CI4/CI8/CI14/CMPR (S3TC); bilinear, trilinear,
  anisotropic; indirect texturing (bump/EMBM) through a second lookup.
- **TEV** (texture environment): **16 stages** of a programmable combiner
  (colour and alpha, each stage `(d + lerp(a, b, c)) op bias/scale`, with
  konstant colours, swap tables, comparisons) — the whole "shader" of the
  machine.
- **PE** (pixel engine): Z test, alpha test, blending, dithering, into the
  **2 MB EFB** (embedded frame buffer: 640 × 528 × (24-bit colour + 24-bit
  Z), or 16-bit colour with 6× the AA samples in a smaller buffer); **EFB
  copy** to main memory as a texture (with format conversion, mipmapping,
  gamma) or as the **XFB** (YUV 4:2:2) for the VI; copy filters implement
  deflicker and AA resolve. Bandwidth to the eDRAM: 4 pixels of colour + Z
  read and write per clock at 162 MHz.
- Registers: `BP` (blending/pixel, 256), `CP` (command, vertex descriptors),
  `XF` (transform, 4 KB of matrices/lights/registers) — Dolphin's
  `BPMemory.h`, `CPMemory.h`, `XFMemory.h` are complete bit-level
  descriptions.

### 3.3 Flipper: the DSP

A Macronix-designed 16-bit DSP at 81 MHz with 8 KB IRAM + 8 KB IROM
(instructions), 8 KB DRAM + 4 KB DROM (data), a mailbox pair to the CPU,
DMA to main memory and ARAM, and the accelerator (ADPCM decode from ARAM).
Its instruction set is fully documented by Dolphin's **DSP LLE** core,
which has an assembler, disassembler and test suite. The IROM/DROM
contents are Nintendo's; **Dolphin ships a free reimplementation of the DSP
ROM** written for it, which is what an FPGA DSP would use. Games upload
their own DSP microcode (the "AX" mixer and a few others) at boot.

### 3.4 The I/O blocks in Flipper

| block | what | analogue already fitted here |
|---|---|---|
| **PI** | processor interface: interrupt cause/mask, GX FIFO base/watermarks, reset | N64 MI (256 LUT class) |
| **MI** | memory interface: protection regions, the 1T-SRAM controller | N64 RI + memorymux |
| **VI** | video interface: reads the XFB (YUV 4:2:2 in main memory) and produces the output timing with line doubling, deflicker taps, and the digital-port stream; NTSC/PAL/480p | **N64 VI, 3,152 LUTs in the fit** — the GameCube VI is its direct evolution (same designers, same XFB-in-main-memory model) |
| **AI** | audio interface: DMA of 16-bit stereo from main memory to the DAC, 32/48 kHz, sample counter interrupt | N64 AI, 358 LUTs |
| **DI** | DVD interface: command/status registers, DMA of sectors, cover switch, error codes; the drive protocol lives in the drive's own microcontroller | PS2 CDVD stub pattern; host-fed |
| **SI** | serial interface: 4 ports, the 1-wire controller protocol with poll timing registers | N64 PIF/SI (827 + 138 LUTs) |
| **EXI** | three channels of an SPI-like bus with chip selects: memory cards, the IPL/RTC/SRAM device, serial-port peripherals | PS2 SIO2 pattern; host-fed devices |
| **ARAM DMA** | main memory ↔ ARAM transfers, plus the DSP's own ARAM access | new, small |

The memory map (YAGCD ch. 4): main memory at 0x80000000 (cached) /
0xC0000000 (uncached), 24 MB; hardware registers at 0xCC000000 in 1 KB
blocks in the order CP, PE, VI, PI, MI, DSP, DI, SI, EXI, AI; the GX FIFO
write-gather target at 0xCC008000; the L1 locked cache at 0xE0000000.

## 4. RTL that exists

| need | exists | state |
|---|---|---|
| VI, AI, SI/controller protocol, PI-style interrupt controller, memory arbitration | **closest kin**: N64_MiSTer (Robert Peip) — `VI*.vhd`, `AI.vhd`, `SI.vhd`, `PIF.vhd`, `MI.vhd`, `RI.vhd`, `memorymux.vhd`, all fitted here on both dies | not drop-in (different registers), but the same designers' architecture one generation on; the VI in particular is a modification, not a rewrite |
| a 32-bit in-order MIPS-class CPU as a *pattern* for the Gekko | N64 `cpu.vhd`: VR4300 (64-bit MIPS III, 5-stage, caches, TLB, FPU), 13,016 LUTs fitted; PSX R3000A 4.5k | shows what a Peip-style CPU costs on this fabric; not a PowerPC |
| a fixed-function rasteriser with texturing, Z, blending and a combiner as a *pattern* | N64 `RDP*.vhd`: 12,447 LUTs for one pixel pipe with one TMU, perspective correction, LOD, Z, blend, dither, combiner; PSX GPU 11.9k | the Flipper pixel pipe is the same list with more of everything (8 textures, 16 TEV stages, S3TC, indirect); ×4 pipes |
| a vector unit with 128-bit registers and 8×16 lanes | N64 `RSP*.vhd`, 9,961 LUTs | the Gekko's paired singles are 2×FP32, narrower and floating point; the XF unit is fixed function; the RSP is a cost reference only |
| **a PowerPC core** | **open POWER cores exist, none is a 750**: [Microwatt](https://github.com/OpenPOWERFoundation/microwatt) (VHDL-2008, POWER ISA 3.0, 64-bit, in-order, small, actively maintained, boots Linux), IBM's [A2O](https://github.com/OpenPOWERFoundation/a2o) (Verilog, out-of-order, 64-bit Power 2.07, designed for 3 GHz in 45 nm; large) and A2I (in-order, multithreaded). None has the 32-bit 750's BATs, the Gekko paired singles, the quantised loads or the write-gather pipe | a Gekko would be written from the IBM 750CX manual plus Dolphin, with Microwatt as the reference for how a Power core is structured in VHDL |
| GX (CP, XF, rasteriser, TEV, PE, EFB, copy) | **no open HDL anywhere** | from Dolphin's `VideoCommon`, which is complete at the register-bit level |
| DSP | no HDL; Dolphin DSP LLE is the instruction-level spec, with a free ROM | from Dolphin |
| EXI, DI, memory cards, RTC | no HDL; YAGCD ch. 10 + Dolphin | host-fed, as the PS2 CDVD/SIO2 were built |

A fresh search (2026-09-07) finds no GameCube FPGA core, complete or in
progress, on any platform, nor a PowerPC 750 soft core; the retro-cores
verdict of 2026-09-05 stands on that point.

## 5. Sizing on the C1100 and FK33 — an estimate, not a fit

Scaled from this repo's own N64 and PSX fits on xcu55n (N64 whole core
46,188 LUTs; blocks as listed in §4), the same way the PS2 estimate was made:

| GameCube block | basis | LUT estimate | memory |
|---|---|---:|---|
| PI, MI, memory controller, ARAM DMA | N64 MI/RI/memorymux/PI 2.2k, plus arbitration for CPU/CP/PE/VI/AI/DSP/DI | 4-8k | — |
| VI | N64 VI 3.2k plus the digital port and 480p | 4-6k | XFB in main memory |
| AI, SI, EXI (3 ch.), DI, controller protocol | N64 AI+SI+PIF 1.3k; PS2 SIO2/CDVD blocks ~3k | 6-10k | memory cards and disc host-fed |
| DSP (16-bit, 81 MHz) + accelerator + mailboxes | a small DSP with 4 KB-8 KB memories; the PS1 SPU is 7k for a different job | 8-14k | 28 KB: BRAM |
| **Gekko**: 3-issue 750 pipeline, rename/completion, 32 K + 32 K L1, 256 K L2, BATs + TLB, double FPU + paired singles + quantised L/S + write gather | no analogue: 3-5× a VR4300 (13k) for the integer/MMU side; a double-precision FPU with paired-single mode is 15-25k on its own (the FP32 FMA in fabric is ~350 LUTs + 2 DSPs, doubles ~4×) | **55-90k**, 30-60 DSP | 64 KB L1 + 256 KB L2: BRAM/URAM (L2 = 8 URAM) |
| **GX**: CP + vertex loader, XF (T&L, 8 lights, 8 texgens), rasteriser, 4 × (4 texture units, TEV 16 stages, Z/alpha/blend), PE, EFB copy with format conversion | one N64 pixel pipe 12.4k; a Flipper pipe does 2-3× that; ×4; XF ~25k with DSPs for the matrix math; CP/copy ~10k | **130-190k**, 100-200 DSP | **EFB 2 MB + TMEM 1 MB in URAM**: ~96-128 URAM with 128-bit rows (the PS2 pass measured what 32-bit rows cost: double) |
| main memory 24 MB, ARAM 16 MB | | | **HBM**. 24 MB is more than the C1100's whole URAM (640 × 36 KB = 22.5 MB), so unlike the PS2's 32 MB RDRAM there is no on-chip option even in principle; bandwidth (1.3 GB/s) is trivial for HBM, latency is the design problem, and the Gekko's 256 KB L2 hides most of it |
| **total** | | **~210-320k LUT, 150-300 DSP** | ~130 URAM, ~150 BRAM |

Against the fabric: C1100 871,680 LUTs, 5,952 DSP, 640 URAM; FK33 439,680
LUTs, 2,880 DSP, 320 URAM. **Area fits on the C1100 with room**, and — the
one way the GameCube is *easier* than the PS2 — its on-chip memory need is
3 MB rather than the GS's 4 MB, so the FK33 is not URAM-bound either; it is
the FK33's 440k LUTs that make it marginal. Both need HBM for main memory.

## 6. Clock

| block | native | what this fabric does with MiSTer-style RTL |
|---|---|---|
| Gekko | 486 MHz, ~2 instructions/clock sustained in good code | the N64's VR4300 closes at −1.4 ns WNS at 93.75 MHz here without timing effort (the N64 fit). A three-issue PowerPC with rename and a double FPU, written to close on UltraScale+, is a 120-180 MHz design; A2O-class out-of-order at FPGA speeds is slower, not faster, per clock. **A cycle-accurate Gekko at native rate is not a realistic target** — the same verdict as the EE, and by a wider margin (486 vs 295 MHz) |
| Flipper GX | 162 MHz, 4 pixels/clock | reachable for a fixed-function pipeline; the PE's EFB access is 4 × (colour + Z) per clock, inside URAM's rate |
| DSP | 81 MHz | trivial |
| main memory / ARAM | 162 MHz 64-bit / 81 MHz 8-bit | HBM |
| EXI, SI | 32 MHz, ~250 kHz | trivial |

So, exactly as for the PS2, **the CPU is the blocker, and only the CPU**.
The options are the same three: (a) a half- or third-rate Gekko (games at a
third speed — a bring-up tool, not a product); (b) a non-cycle-accurate
Gekko that is faster per clock where it can be (wider issue, bigger
buffers, the L2 doing more) and throttled to match, which is what Dolphin's
JIT does in software; (c) accept a fraction of native speed for the library
of CPU-light games and see how many that is (the decompilations make that
measurable: their profiles show how much of a frame is Gekko-bound).

What the PS2 pass adds here: the GS/GX and the peripherals are the
*measurable* part and should be built and verified first against the
emulator's own renderer and the hardware test suite; the CPU comes last,
and its first version is in-order and slow, because everything else can be
proven without it — with a stand-in.

## 7. If it were pursued: the order that produces something testable at every step

The PS2 order was IOP (existing RTL) → GS standalone → EE → integration.
Applied here, with the lessons of that pass:

1. **The peripheral ring with a stand-in CPU.** PI, MI, VI, AI, SI, EXI, DI
   and the memory controller on the C1100, with main memory in HBM, the VI
   into `video_sink`, pads through `hps_pcie`/`hps_io`, memory cards and the
   disc image host-fed through Main's block-mount path (a `support/gamecube`
   module in Main, sibling of `pcecd`). The stand-in CPU is
   **Microwatt** (VHDL-2008, small, runs POWER code that `gcc` can produce
   today) so the ring can execute real test programs before a Gekko exists.
   *Verify by:* the peripheral parts of `dolphin-emu/hwtests` rebuilt for
   the stand-in, and libogc's VI/AI/EXI/SI init sequences.
   **Lesson from the IOP:** every peripheral read must return zero when
   unselected, every store arrives word-aligned with lanes in the mask,
   simulate before fitting, and give every block a `NOTE (unverified)`
   listing which Dolphin behaviour it was written from.
2. **The DSP.** A 16-bit DSP written to Dolphin's DSP LLE instruction set,
   running the free DSP ROM and then a game's AX microcode, verified against
   DSP LLE trace-for-trace and against the `hwtests` DSP tests. Small, self-
   contained, and the first block with no MiSTer ancestor.
3. **GX as a standalone unit.** Feed the GX FIFO from the host over PCIe,
   compare the EFB and the EFB copies against Dolphin's software renderer
   frame-for-frame — the same plan as the GS, with the same advantage that
   Dolphin already has the reference renderer and a fifo-log format
   (`.dff` "FIFO logs" recorded from real games) that is exactly the test
   input needed. Build order inside it: CP and vertex loader → XF → rasteriser
   with one pixel pipe and one texture unit → TEV → PE and EFB → copy → four
   pipes.
4. **Gekko**, in-order first: the 750 integer pipeline and MMU from the IBM
   manual, verified against Dolphin's interpreter with instruction traces;
   then the FPU; then paired singles and quantised loads; then the
   write-gather pipe; then dual issue and completion buffering. Replace the
   stand-in.
5. Integration, then boot: no IPL is needed — Dolphin's apploader HLE shows
   how to start a retail disc image without Nintendo's boot ROM, and homebrew
   DOLs start directly. The IPL's menu is not required for playing games.

Each step is months of work for someone who knows the fabric; the whole is
the same "full-time job for a team" the MiSTer developers describe for both
consoles. The GameCube's advantages over the PS2 in this plan are real but
modest: a complete executable spec with a hardware test suite and FIFO
recordings, one vendor manual for the CPU, a smaller on-chip memory need,
and no IOP-style second computer to build. Its disadvantage is the CPU: a
486 MHz out-of-order PowerPC is further from an FPGA than the 295 MHz EE.

This document does not change the retro-cores verdict — Dolphin on the host
GPU remains the answer for playing GameCube games — it records what that
verdict rests on and what step 1 would cost if the question is asked again.
The same host path that every fitted MiSTer core uses (bridge, sink, viewer,
Main on Ubuntu or Windows) is the one this design would plug into, so
nothing built for it is throwaway.

Sources: [YAGCD](https://www.gc-forever.com/yagcd/), [YAGCD on WiiBrew](https://wiibrew.org/wiki/YAGCD), [YAGCD PDF mirror](https://wiki.retrotechcollection.com/Yet_Another_GameCube_Documentation_(YAGCD)), [doldecomp](https://github.com/doldecomp), [Metroid Prime decomp progress](https://decomp.dev/PrimeDecomp/prime), [gamecube.dev](https://gamecube.dev/), [RetroReversing decompiled games](https://www.retroreversing.com/source-code/decompiled-retail-console-games), [Copetti, GameCube Architecture](https://www.copetti.org/writings/consoles/gamecube/), [GC-Forever hardware acronyms](https://www.gc-forever.com/wiki/index.php?title=Hardware_Acronyms), [GC-Forever GameCube versions](https://www.gc-forever.com/wiki/index.php?title=GameCube_versions), [iFixit GameCube](https://www.ifixit.com/Device/Nintendo_GameCube), [teardown guide](https://manuals.plus/m/9e1ec85447b03abf5bdde05591c84be2c3b9cbca9e4094d869e293f3d0796593_doc), [Wikipedia: Gekko](https://en.wikipedia.org/wiki/Gekko_(processor)), [Wikipedia: GameCube technical specifications](https://en.wikipedia.org/wiki/GameCube_technical_specifications), [AnandTech: embedded DRAM in Flipper](https://anandtech.com/show/858/5), [Microwatt](https://github.com/OpenPOWERFoundation/microwatt), [A2O](https://github.com/OpenPOWERFoundation/a2o), [IBM A2](https://en.wikipedia.org/wiki/IBM_A2), [Dolphin](https://github.com/dolphin-emu/dolphin), [RetroReversing: Emerald leak](https://www.retroreversing.com/emeraldleak), [Wikipedia: Nintendo data leak](https://en.wikipedia.org/wiki/Nintendo_data_leak), [Hollywood (graphics chip)](https://en.wikipedia.org/wiki/Hollywood_(graphics_chip)).
