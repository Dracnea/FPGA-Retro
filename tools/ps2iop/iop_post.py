#!/usr/bin/env python3
"""Drive the C1100 PS2 IOP bring-up design over PCIe: load a ROM, release reset,
watch the POST register.

    iop_post.py [--dev /dev/litepcie0] [--csr csr.csv] status
    iop_post.py ... load ROM.hex|ROM.bin [--addr WORD]     # write an image into the IOP ROM
    iop_post.py ... reset {hold|release}
    iop_post.py ... run ROM.hex|ROM.bin [--timeout SEC]    # load, release, poll until AA/EE

ROM images are either the assembler's one-hex-word-per-line files
(cores/PS2/sim/asm_r3000.py) or raw little-endian words.  Word address 0 is
0xBFC00000, the reset vector.  Register access goes through the litepcie
driver's LITEPCIE_IOCTL_REG ioctl, the same path litepcie_util uses, so the
device node needs to be readable (tools/99-litepcie.rules) and the csr.csv must
be the one generated with the loaded bitstream.
"""
import argparse, fcntl, os, struct, sys, time

# _IOWR('S', 0, struct litepcie_ioctl_reg { u32 addr; u32 val; u8 is_write; })  -> 12 bytes
LITEPCIE_IOCTL_REG = (3 << 30) | (12 << 16) | (ord("S") << 8) | 0

POST_PASS = 0xAA
POST_FAIL = 0xEE


class Dev:
    def __init__(self, path, csr_csv):
        self.fd = os.open(path, os.O_RDWR)
        self.regs = {}
        with open(csr_csv) as f:
            for line in f:
                parts = line.strip().split(",")
                if parts and parts[0] == "csr_register":
                    self.regs[parts[1]] = int(parts[2], 0)

    def readl(self, addr):
        buf = struct.pack("IIB3x", addr, 0, 0)
        out = fcntl.ioctl(self.fd, LITEPCIE_IOCTL_REG, buf)
        return struct.unpack("IIB3x", out)[1]

    def writel(self, addr, val):
        fcntl.ioctl(self.fd, LITEPCIE_IOCTL_REG, struct.pack("IIB3x", addr, val & 0xFFFFFFFF, 1))

    def reg(self, name):
        if name not in self.regs:
            sys.exit(f"csr.csv has no register {name}; is it the csr.csv of the loaded bitstream?")
        return self.regs[name]

    def rd(self, name):  return self.readl(self.reg(name))
    def wr(self, name, v): self.writel(self.reg(name), v)


def read_image(path):
    if path.endswith(".hex"):
        words = []
        with open(path) as f:
            for line in f:
                s = line.split("//")[0].strip()
                if s:
                    words.append(int(s, 16))
        return words
    data = open(path, "rb").read()
    if len(data) % 4:
        data += b"\0" * (4 - len(data) % 4)
    return list(struct.unpack("<%dI" % (len(data) // 4), data))


def status(dev):
    s = dev.rd("iop_status")
    return {
        "post":       s & 0xFF,
        "cpu_error":  (s >> 8) & 1,
        "mem_idle":   (s >> 9) & 1,
        "locked":     (s >> 10) & 1,
        "heartbeat":  (s >> 11) & 1,
        "post_count": dev.rd("iop_post_count"),
        "rom_count":  dev.rd("iop_rom_count"),
        "reset":      dev.rd("iop_reset") & 1,
    }


def show(dev):
    s = status(dev)
    print(f"POST {s['post']:02X}  post_count {s['post_count']}  reset {s['reset']}  "
          f"locked {s['locked']}  heartbeat {s['heartbeat']}  cpu_error {s['cpu_error']}  "
          f"mem_idle {s['mem_idle']}  rom_count {s['rom_count']}")
    return s


def load(dev, path, addr=0):
    words = read_image(path)
    dev.wr("iop_rom_addr", addr)
    t0 = time.time()
    for w in words:
        dev.wr("iop_rom_data", w)
    dt = time.time() - t0
    print(f"loaded {len(words)} words at word address {addr} in {dt:.2f} s")
    return len(words)


def run(dev, path, timeout):
    dev.wr("iop_reset", 1)
    load(dev, path)
    seen = None
    dev.wr("iop_reset", 0)
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = status(dev)
        if s["post"] != seen:
            seen = s["post"]
            print(f"[{time.time()-t0:7.3f}s] POST {seen:02X}  (count {s['post_count']})")
            if seen == POST_PASS:
                print("PASS"); return 0
            if seen == POST_FAIL:
                print("FAIL: test reported failure"); return 1
        if s["cpu_error"]:
            print("FAIL: cpu error flag"); return 1
        time.sleep(0.01)
    print(f"FAIL: timeout, last POST {seen if seen is not None else 0:02X}")
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dev", default="/dev/litepcie0")
    ap.add_argument("--csr", default="csr.csv")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("load");  p.add_argument("rom"); p.add_argument("--addr", type=lambda x: int(x, 0), default=0)
    p = sub.add_parser("reset"); p.add_argument("state", choices=["hold", "release"])
    p = sub.add_parser("run");   p.add_argument("rom"); p.add_argument("--timeout", type=float, default=5.0)
    a = ap.parse_args()

    dev = Dev(a.dev, a.csr)
    if a.cmd == "status":
        show(dev)
    elif a.cmd == "load":
        load(dev, a.rom, a.addr)
    elif a.cmd == "reset":
        dev.wr("iop_reset", 1 if a.state == "hold" else 0)
        show(dev)
    elif a.cmd == "run":
        sys.exit(run(dev, a.rom, a.timeout))


if __name__ == "__main__":
    main()
