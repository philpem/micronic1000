# Commstar application API

**Stability: Provisional.** The entry points and the calling convention are
verified in the emulator; the argument and result contract of individual
operations is not established.

A loaded COM or DIP program can drive the Commstar session directly. The
firmware publishes twenty fixed entry points in the transfer-vector table,
one per protocol command, and they work when called from an application even
though the firmware's own UI never uses most of them.

This matters because the firmware alone only ever performs *Program
Reception*. Everything else the protocol can do — including sending collected
data back to a host — is reachable only this way.

## Entry points

Each entry is four bytes at a fixed address in battery-backed RAM. Call it
like an ordinary subroutine; see the calling convention below for the
important caveat.

| Address | Command | Session screen |
|---|---|---|
| `EE00` | `C_ABORT` | |
| `EE04` | `C-ANSWER` | |
| `EE08` | `C-BEGIN-FILE` | Sending data |
| `EE0C` | `C-COMMAND` | |
| `EE10` | `C-DIAL` | |
| `EE14` | `C-DROP-LINE` | |
| `EE18` | `C-END-FILE` | |
| `EE1C` | `C-END-TX` | |
| `EE20` | `C-INIT-COMMS` | |
| `EE24` | *arms the session state machine* | |
| `EE28` | `C-MANUAL` | |
| `EE2C` | `C-RX-BLK` | Receiving prog |
| `EE30` | `C-SHUT-DOWN` | |
| `EE34` | `C-RX-REC` | Receiving data |
| `EE38` | `C_ABORT` | |
| `EE3C` | `C-SHUT-DOWN` | |
| `EE40` | `C-TX-BLK` | Sending prog |
| `EE44` | `C-TX-REC` | |
| `EE48` | `C-SHUT-DOWN` | |
| `EE4C` | `C_ABORT` | |

Fifteen of the protocol's seventeen commands are reachable. `C-RX-CMD` and
`C-TX-REPLY` have no entry point — no routine in either ROM issues them.
Several commands appear more than once; the duplicates are distinct wrapper
routines and have not been told apart.

`EE24` is not a protocol command. It sets the mode gate that makes the
firmware consult the session state machine at all; without it the
transition table is never used and only the states `NOT-STARTED`,
`CONNECTED` and `CRASHED` are reachable.

## Calling convention

**An entry point does not return.** Each is a banked-call thunk
(`RST 10h`, bank, target) onto a routine that begins by switching coroutine
context, so control passes to the session machinery and does not resume at
the instruction after your `CALL`.

Verified: a program that writes a marker before the call and a second marker
after it leaves only the first marker behind, while the call's side effects
are present in RAM.

Treat these as *transfer of control*, not as subroutine calls. An application
hands the session off; it does not drive it instruction by instruction.

Arguments are not established. `C-INIT-COMMS` (`EE20`) takes one byte from
the caller's stack, which it stores as the session mode; the rest have not
been characterised.

## Worked example

This 16-byte COM arms the state machine and proves the call took effect:

```text
0100  3E AA        LD   A,0AAh
0102  32 00 02     LD   (0200h),A   ; marker: reached the call
0105  CD 24 EE     CALL 0EE24h      ; arm the state machine
0108  3E 55        LD   A,055h
010A  32 00 02     LD   (0200h),A   ; would mark a normal return
010D  C3 0D 01     JP   $
```

Running it in the emulator leaves the mode gate at 2 and its companion cell
at `0x37`, where a control program that does not make the call leaves both
at 0. The marker at `0200h` holds `AA`, never `55` — the call did its work
and did not come back.

Regression: `test_commstar_application_api` in `analysis/test_boot_upload.py`.

## What this does not tell you

* The per-operation argument and result contract.
* How an application receives data back, or hands over a buffer.
* Whether a real Commstar application used these entry points, or reached the
  same routines another way. Nothing in the firmware calls fifteen of the
  twenty, which is the evidence for an application-facing API, but no
  historical application has been examined.

For the firmware evidence behind this page — the ROM source table, the
per-slot derivation, and the measurements — see
[RE notes: Commstar evidence](../re-notes/commstar-evidence.md) and
[Protocol reference: Commstar](../protocol/commstar.md#what-selects-the-operation).
