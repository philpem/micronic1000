# Interrupts

## CPU interrupt mode

Both cold and warm boot paths execute `IM 1` (set at ROM00:0150 and
again at ROM00:186C before entering restored programs). Interrupts are
disabled (`DI`) during critical init sequences.

Under Z80 interrupt mode 1 the CPU ignores any daisy-chain vector and
always executes `RST 38h` for a maskable interrupt — so the RST7 slot
doubles as the IRQ entry.

All handler bodies live in the resident kernel, whose image is copied
from ROM00:369D → F180 by `InstallKernelToRam`; the ROM-side images
(RAM address minus 0xBAE3) are fully analysable. Handlers are created
as functions in Ghidra: `NmiHandlerImage` (ROM00:3B13), 
`IrqCommonHandlerImage` (ROM00:3B6A), `IrqWorkerPollPort5` (ROM00:230A).

## Maskable IRQ — fully decoded

Path: `INT → 0038 → stub F5F3` (`JP F64D`) → `IrqCommonHandlerImage`.
`0008 → F180` is the BDOS gate and is separate; only `RST 20h`/`28h`/`30h`/
`38h` (`F5EA`/`F5ED`/`F5F0`/`F5F3` are `JP F64D`) share the common handler with
the hardware IRQ, so **those software RSTs and the IRQ share one entry point**
— they behave as "check for pending events" calls rather than distinct
syscalls (see caveat below). `0010 → F5E1` is the banked-call dispatcher and
does not join this row.

Common handler logic:

* Push AF/BC/DE/HL/IX/IY.
* Gate on semaphore `ffa8`:
  * `ffa8 == 0` → DI, pop everything, RET — event silently dropped.
    The gate is armed by writing `ffa8=1`, e.g. FUN_22E9/2306 after
    loading the comms config table.
  * else → clear `ffa8` (in-service marker), DI, save current bank,
    switch to bank 0, call worker.
* Worker = `IrqWorkerPollPort5` (ROM00:230A):
  * Read port 05h; keep a copy in f785.
  * Bit 3 of inverted status: if clear, zero fda2/fda3 — tracks a
    carrier/link signal disappearing.
  * Enable mask = ~(p04_shadow | port5 raw).
  * Walk fd84 as 3-byte records `{mask, handler word}`, terminated by
    a byte ≥ 80h; invoke each handler whose mask bit matches.
* Restore bank, set `ffa8=1` (re-arm), pop regs, EI, RET.

The fd84 table comes from ROM00:2352 (19 bytes ≈ 6 records + terminator),
loaded under port-04h mode bits E0h/FDh.

> Caveat on earlier interpretation: because the RST stubs funnel into
> this gated dispatcher, ROM01's frequent `RST 28h` sites may be
> scheduler/event-check points rather than classic syscalls — with the
> gate disarmed they return immediately without doing anything. The
> true syscall surface is CALL 0005h (BDOS). This supersedes the
> stronger claim made previously in os-diposb.md item on ABI layers;
> both readings are noted there.

## NMI — fully decoded

Path: NMI → 0066 → F5F6 (`NmiHandlerImage`, ROM00:3B13).

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
