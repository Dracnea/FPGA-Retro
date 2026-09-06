# boot_test.s -- IOP subsystem bring-up ROM.  Runs from the reset vector
# (0xBFC00000, uncached) and reports through the POST register 0x1F802070.
#   01  alive               02  RAM word test         03  byte/half access
#   04  code copied to RAM and run cached (KSEG0)     05  timer 3 polled
#   06  timer 3 interrupt taken through the BEV=1 vector at 0xBFC00180
#   AA  all passed          EE  a check failed (the failing stage is the
#                               POST value before it)

.org 0xBFC00000
        j       start
        nop

# ---- general exception vector while BEV=1 -------------------------------
.org 0xBFC00180
        mfc0    $k0, $13                # CAUSE
        nop
        andi    $k0, $k0, 0x7C          # ExcCode
        bne     $k0, $zero, fail        # anything but an interrupt is a failure
        nop
        li      $k1, 0x1F801070
        li      $k0, 0xFFFFBFFF         # acknowledge RTC3 (bit 14)
        sw      $k0, 0($k1)
        li      $k0, 0x1F801484
        lw      $k1, 0($k0)             # read timer 3 MODE: clears the reached flags
        nop
        li      $k0, 0xA0001000
        li      $k1, 1
        sw      $k1, 0($k0)             # flag for the main loop
        li      $k0, 0x1F802070
        li      $k1, 0x5A
        sb      $k1, 0($k0)
        mfc0    $k0, $14                # EPC
        nop
        jr      $k0
        rfe

# ---- main -----------------------------------------------------------------
start:
        li      $sp, 0x801FFF00
        li      $s7, 0x1F802070         # POST
        li      $t0, 1
        sb      $t0, 0($s7)

# SSBUS configuration the real IOPBOOT does first; the values are stored and
# read back through memctrl, nothing here depends on them yet
        li      $t0, 0x1F801000
        li      $t1, 0x1F000000
        sw      $t1, 0x00($t0)          # EXP1 base
        li      $t1, 0x1F802000
        sw      $t1, 0x04($t0)          # EXP2 base
        li      $t1, 0x0013243F
        sw      $t1, 0x10($t0)          # BIOS ROM delay/size
        lw      $t2, 0x10($t0)
        nop
        bne     $t2, $t1, fail          # must read back
        nop
        li      $t1, 0x00000B88
        sw      $t1, 0x60($t0)          # RAM_SIZE
        lw      $t2, 0x60($t0)
        nop
        bne     $t2, $t1, fail
        nop

# ---- 02: RAM word test, uncached ------------------------------------------
        li      $t0, 0xA0010000
        li      $t1, 256
        li      $t2, 0x12345678
w_loop: sw      $t2, 0($t0)
        addiu   $t2, $t2, 0x1111
        addiu   $t0, $t0, 4
        addiu   $t1, $t1, -1
        bne     $t1, $zero, w_loop
        nop
        li      $t0, 0xA0010000
        li      $t1, 256
        li      $t2, 0x12345678
r_loop: lw      $t3, 0($t0)
        nop
        bne     $t3, $t2, fail
        nop
        addiu   $t2, $t2, 0x1111
        addiu   $t0, $t0, 4
        addiu   $t1, $t1, -1
        bne     $t1, $zero, r_loop
        nop
        li      $t0, 2
        sb      $t0, 0($s7)

# ---- 03: byte and halfword access -----------------------------------------
        li      $t0, 0xA0020000
        li      $t1, 0xAABBCCDD
        sw      $t1, 0($t0)
        lbu     $t2, 0($t0)             # little endian: 0xDD
        nop
        li      $t3, 0xDD
        bne     $t2, $t3, fail
        nop
        lbu     $t2, 3($t0)
        nop
        li      $t3, 0xAA
        bne     $t2, $t3, fail
        nop
        lhu     $t2, 2($t0)
        nop
        li      $t3, 0xAABB
        bne     $t2, $t3, fail
        nop
        li      $t3, 0x11
        sb      $t3, 1($t0)
        lw      $t2, 0($t0)
        nop
        li      $t3, 0xAABB11DD
        bne     $t2, $t3, fail
        nop
        li      $t3, 0x2233
        sh      $t3, 2($t0)
        lw      $t2, 0($t0)
        nop
        li      $t3, 0x223311DD
        bne     $t2, $t3, fail
        nop
        lh      $t2, 0($t0)             # sign-extended 0x11DD
        nop
        li      $t3, 0x11DD
        bne     $t2, $t3, fail
        nop
        lb      $t2, 3($t0)             # sign-extended 0x22
        nop
        li      $t3, 0x22
        bne     $t2, $t3, fail
        nop
        li      $t0, 3
        sb      $t0, 0($s7)

# ---- 04: copy a routine into RAM and run it cached --------------------------
        la      $t0, ram_code
        la      $t1, ram_code_end
        li      $t2, 0xA0002000
copy:   lw      $t3, 0($t0)
        nop
        sw      $t3, 0($t2)
        addiu   $t0, $t0, 4
        addiu   $t2, $t2, 4
        bne     $t0, $t1, copy
        nop
        li      $t0, 0x80002000         # cached alias
        jalr    $t0
        nop
        li      $t1, 5050
        bne     $v0, $t1, fail
        nop
        li      $t0, 4
        sb      $t0, 0($s7)

# ---- 05: timer 3, polled ----------------------------------------------------
        li      $t0, 0x1F801480
        li      $t1, 2000
        sw      $t1, 8($t0)             # TARGET
        li      $t1, 0x0008             # reset on target, no IRQ
        sw      $t1, 4($t0)             # MODE (also zeroes COUNT)
poll:   lw      $t2, 4($t0)
        nop
        andi    $t2, $t2, 0x0800        # reached target
        beq     $t2, $zero, poll
        nop
        lw      $t2, 0($t0)             # COUNT must have wrapped to a small value
        nop
        sltiu   $t2, $t2, 2000
        beq     $t2, $zero, fail
        nop
        li      $t0, 5
        sb      $t0, 0($s7)

# ---- 06: timer 3 interrupt --------------------------------------------------
        li      $t0, 0xA0001000
        sw      $zero, 0($t0)           # flag
        li      $t1, 0x1F801070
        li      $t2, 0x00004000         # I_MASK: RTC3
        sw      $t2, 4($t1)
        sw      $zero, 0($t1)           # I_STAT: clear everything
        li      $t2, 1
        sw      $t2, 8($t1)             # I_CTRL: enable
        li      $t1, 0x1F801480
        li      $t2, 3000
        sw      $t2, 8($t1)             # TARGET
        li      $t2, 0x0058             # reset on target | IRQ on target | repeat
        sw      $t2, 4($t1)
        li      $t2, 0x00400401         # SR: BEV | IM2 | IEc.  BEV must stay set: the
        mtc0    $t2, $12                # vector is 0xBFC00180 only while it is (found in sim)
        nop
        li      $t3, 200000
wait:   lw      $t2, 0($t0)
        addiu   $t3, $t3, -1
        beq     $t3, $zero, fail
        nop
        beq     $t2, $zero, wait
        nop
        li      $t2, 0x00400000
        mtc0    $t2, $12                # interrupts off again, BEV kept
        nop
        li      $t0, 6
        sb      $t0, 0($s7)

# ---- done -----------------------------------------------------------------
        li      $t0, 0xAA
        sb      $t0, 0($s7)
halt:   b       halt
        nop

fail:   li      $t0, 0xEE
        sb      $t0, 0($s7)
fhalt:  b       fhalt
        nop

# ---- routine that runs from RAM: sum 1..100 in $v0 ----------------------------
.align 4
ram_code:
        move    $v0, $zero
        li      $a0, 100
sum:    addu    $v0, $v0, $a0
        addiu   $a0, $a0, -1
        bne     $a0, $zero, sum
        nop
        jr      $ra
        nop
ram_code_end:
        nop
