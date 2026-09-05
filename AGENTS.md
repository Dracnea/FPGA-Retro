# AGENTS.md — read me first

This repo is **public**. It holds the work to bring MiSTer/MiSTeX onto AMD
UltraScale+ accelerator cards, and it is intended to be shared.

## 1. The public/private boundary is absolute

The maintainer also runs **private** FPGA work on the same machines and the same
cards. None of it belongs here — not the files, and not references to them.

- Nothing from the private trees is copied, quoted, or cited in this repo.
- Watch for leakage through **provenance**, not just through file moves. It is
  natural to write "pin data taken from `<private-path>/foo.xdc`" in a header
  comment; doing so publishes the existence and structure of private work.
  Re-attribute derived data to its **public** upstream instead — for the C1100
  pinout that is Corundum's AU55N target, which is where it actually originates.
- Keep the engineering claim, drop the private locator. "Verified through
  place-and-route on this card" is fine. Naming the private build that verified
  it is not.
- Grep before the first push of any migrated file. A public repo's history
  cannot be quietly corrected afterwards.

## 2. Nothing goes in a document unless it is verified

A statement here is one someone will act on without re-checking.

- **Verified** = measured on real hardware, or observed directly in a tool's
  output. State it plainly, with the measurement and the date where it matters.
- **Not verified** = reasoned, inferred, or true of a different card. It still
  gets written down, but tagged:

  ```markdown
  > **NOTE (unverified):** the FK33 CRG can derive 50 MHz cleanly from its 200 MHz osc.
  > *Verify by: building the NES core against it and checking MMCM lock.*
  > Delete this note and state the result plainly once confirmed.
  ```

- **"X does not work" needs the same proof as "X works".** A negative claim
  stops the next person trying, so an unverified one costs more than silence.
- **Contradictions get recorded, not resolved.** Two runs legitimately produce
  two different numbers. Keep both with dates rather than averaging.
- Never cite a file you have not confirmed exists. Grep first.
- Arithmetic on a utilisation report is **not** a measurement. "Six cores fit"
  is a placement result, not a division.

## 3. Constraints are not code — verify they took effect

The C1100 PCIe bring-up lost two full builds to constraints that read correctly
and did nothing (see `docs/c1100-pcie-transport.md`). Both were visible in the
log and invisible in the result.

- After any timing-constraint change, **grep the build log** for
  `No clocks matched`, `12-4739`, and `is not supported`.
- A constraint verified against a **routed checkpoint** is not verified for the
  **build**. A checkpoint has every clock resolved; the build XDC is read in
  order. Generated and internal clocks only exist after synthesis — use
  `add_false_path_constraints_by_name` / pre-placement commands for those.
- An unchanged WNS after a constraint change is the signature of an inert
  constraint, not of a wrong diagnosis. Check the constraint landed before
  re-diagnosing the path.

## 4. Hardware safety

- **`hbm_cattrip` (BE45) must be driven low** on the C1100 by any design that
  does not instantiate HBM. Floating it powers the card off via the satellite
  controller.
- **Never `SIGKILL` a process holding an FTDI channel.** `SIGTERM`, wait, verify
  the channel came back. A hard kill leaves all four channels marked open at the
  driver level with nothing holding them.
- Programming over JTAG while the card is enumerated on PCIe drops the link.
  Prefer removing the PCIe device first, then program, then rescan.
- These are passively cooled datacenter cards. Watch temperatures in a desktop
  chassis.

## 5. Layout

`overlay/` mirrors the directory structure of a
[MiSTeX-ports](https://github.com/MiSTeX-devel/MiSTeX-ports) checkout exactly, so
installing it is a copy. Keep it that way — do not restructure paths for tidiness.
