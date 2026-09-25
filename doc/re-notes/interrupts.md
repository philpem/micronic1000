# Interrupts

## CPU interrupt mode

Both cold and warm boot paths execute `IM 1` (set at ROM00:0150 and
again at ROM00:186C before entering restored programs). Interrupts are
disabled (`DI`) during critical init sequences.

Under Z80 interrupt mode 1 the CPU ignores any daisy-chain vector and
always executes `RST 38h` for a maskable interrupt — so the RST7 slot
doubles as the IRQ entry.

All handler bodies live in the resident kernel, whose image is copied
from ROM00:369D → F180 by `Kernel_KernelToRam`; the ROM-side images
(RAM address minus 0xBAE3) are fully analysable. Handlers are created
as functions in Ghidra: `Kernel_HandlerImage` (ROM00:3B13), 
`Kernel_CommonHandlerImage` (ROM00:3B6A), `Kernel_WorkerPollPort5` (ROM00:230A).

## Maskable IRQ {#maskable-irq-fully-decoded}

Path: `INT → 0038 → stub F5F3` (`JP F64D`) → `Kernel_CommonHandlerImage`.
`0005 → F180` is the separate BDOS gate; `0008 → F5E1` is a restart
entry. The `0010` banked-call dispatcher is inline code.

**CONFIRMED, byte-verified 2026-09-20:** in the initial kernel image,
`RST 20h → F5EA → F64D` and `RST 38h → F5F3 → F64D` share this handler.
`RST 28h → F5ED → F57E` takes the diagnostic path, while
`RST 30h → F5F0 → Debug_MonitorHookStub` (formerly `Monitor_Enter`) reaches the returning stub.
The source bytes at `ROM00:3B07-3B12` are
`C3 4D F6 C3 7E F5 C3 13 35 C3 4D F6`. RAM vectors are mutable;
these initial targets do not establish their state at every invocation.

Common handler logic:

* Push AF/BC/DE/HL/IX/IY.
* Gate on `g_bIrqServiceArmed`:
  * `g_bIrqServiceArmed == 0` → DI, pop everything, RET — event silently
    dropped. The gate is armed by writing `g_bIrqServiceArmed=1`, e.g.
    FUN_22E9/2306 after
    loading the comms config table.
  * else → clear `g_bIrqServiceArmed` (in-service marker), DI, save current bank,
    switch to bank 0, call worker.
* Worker = `Kernel_WorkerPollPort5` (ROM00:230A):
  * Read port 05h; keep a copy in f785.
  * Bit 3 of inverted status: if clear, zero fda2/fda3 — tracks a
    carrier/link signal disappearing.
  * Enable mask = ~(p04_shadow | port5 raw).
  * Walk fd84 as 3-byte records `{mask, handler word}`, terminated by
    a byte ≥ 80h; invoke each handler whose mask bit matches.
* Restore bank, set `g_bIrqServiceArmed=1` (re-arm), pop regs, EI, RET.

The worker and every handler it invokes run before that final `EI`.
Consequently, `Comms_WorkItemSweep` and an expired work-item callback execute
with CPU maskable interrupts disabled on the RTC event path.

The fd84 table comes from ROM00:2352 (19 bytes ≈ 6 records + terminator),
loaded under port-04h mode bits E0h/FDh.

The earlier interpretation of `RST 28h` as an IRQ-style event-poll call
is withdrawn: its initial vector does not target this handler. Its
diagnostic mode and subsequent vector changes must be considered
separately; see [DIPOS-B extensions](../reference/extensions.md#other-extensions).

## NMI {#nmi-fully-decoded}

Path: NMI → 0066 → F5F6 (`Kernel_HandlerImage`, ROM00:3B13).

Behaviour keyed on fbd5:

* `fbd5 == 0` (normal operation):
  * save ffa8 and zero it (block further IRQ processing)
  * save bank, switch to bank 0, `CALL F54E` (kernel notify)
  * save port-02h shadow f782, force bit 40h, OUT (2)
  * `CALL 1721` — wake/abort worker near reset-flow code
  * restore shadow + latch, restore bank, `CALL F54E` again
  * IM 1, restore ffa8 (EI only if it was armed), RET

  ⇒ NMI aborts/wakes whatever is running in a controlled way.
* `fbd5 == 1`: POP AF; RET — ignored during restart processing.
* other values: force f782=40h and JP 1758 — re-enter the reset/
  restart flow (controlled restart via NMI).

Physical NMI source still unknown — candidates are the power button or
an alarm; the keyboard-latch bit-40h manipulation suggests it wakes the
unit or simulates a key event.

## Banked-call mechanics (RST 10h)

Unaffected by the above: RST 10h is a true inter-bank call instruction.

```
0010  POP HL          ; HL = address of embedded operand table
      LD E,(HL)       ; E = requested bank (first embedded operand byte)
      LD A,(F791)     ; current bank number
      CP E            ; E = requested bank (from stack operand)
      JP NZ,d74b      ; wrong bank -> inter-bank switch path
      LD A,(HL) / INC HL / LD H,(HL) / LD L,A
      JP (HL)         ; same bank: jump to embedded target
0040  tail (wrong-bank path): OUT(47h),0 ; JP <bank-0 handler>
```

Call sites look like:

```
RST 10h
DB  <target bank>
DW  <target address>
```

## Sleep confirms bit 0 is the keypad {#sleep-wake}

**CONFIRMED, and it is the cleanest evidence in this table.** Entering sleep
(`ROM00:1775`-`177F`) selects one of three masks and writes it to `04h`:

| | value | enabled (active low) |
|---|---|---|
| `1775` | `F8h` | 0, 1, 2 |
| `1779` | `FAh` | 0, 2 |
| `177D` | `D8h` | 0, 1, 2, 5 |

**Bit 0 is enabled in all three**, because it is what wakes the machine. The
same sequence prepares the matrix for it: `ROM00:1766` writes `48h` to the
keyboard drive rather than the usual `3Fh` — one column held down plus the
bit 6 mode flag — so a key in that column pulls a sense line while everything
else is quiet, and the wake path at `17D5` restores `3Fh` (`AND 3Fh`) on the
way back out. Sleep itself is a spin loop at `1793`, not a `HALT`.

So the keypad is a genuine interrupt source, not something the firmware
discovers by polling; `Kbd_ScanMain` at `18F0` is its *handler*. Note the
`FAh` case is exactly bits 0 and 2 — keypad and link — which is the mask
`analysis/rom_exerciser` uses, arrived at independently and then found to be
one the firmware itself uses.

## The link interrupt {#link-interrupt}

Worth stating separately, because it changes the picture of how the link is
meant to be driven. `ROM00:31B6` is:

```
31B6  CALL 34D2      ; LINK_CTRL bits 6 and 7 low
31B9  CALL 34E7      ; IN A,(4Bh); AND 10h  -- LINK_STATUS bit 4
31BC  JR Z,31C2
31BE  CALL 2FBD      ; -> Link_BlockRx (ROM00:3378)
31C1  RET
31C2  CALL 34BD      ; LINK_CTRL bits 6 and 7 high
```

So **`LINK_STATUS` bit 4 is "receive pending"**: it is the bit that decides
whether the interrupt enters `Link_BlockRx` at all. That is a different job
from bit 0, which gates the `INI` loop *inside* a block read (`ROM00:33CF`),
and it means the receive path is normally **interrupt-driven**, not polled —
the polling in `Link_BlockRx` only runs once the interrupt has decided a frame
is there. `LINK_CTRL` bits 6 and 7 are raised when there is nothing to receive
and lowered while receiving, which is consistent with an interrupt
enable/acknowledge pair on the controller.

`analysis/rom_exerciser` installs its own IM-1 handler, enables sources 0 and
2, and records both `LINK_STATUS` and the complemented port-`05h` source mask
at interrupt time. It does not call the firmware receive handler; the point is
to observe whether the controller raises source 2 without consuming a frame.

See also: [Memory and I/O map — interrupt sources](../reference/memory-map.md#interrupt-sources).
