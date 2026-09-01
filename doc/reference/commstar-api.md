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
| `EE24` | *initialise session* (`Session_InitState`) | |
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

`EE24` is not a protocol command. It initialises the session: it clears a
dozen session variables, sets `ram:E48D = 2`, and displays
`Comms in progress`. It does not return — it appears to run the session
rather than merely prepare it, so treat it as a session *runner* whose
contract is not yet established.

Note that `E48D = 2` **suppresses** per-command dispatch:
`SessionStartDataMode` runs the state machine when `E48D` is *not* 2. See
the protocol page.

## Calling convention

Established from the firmware's own two call sites, `ROM01:1305` and
`ROM01:141E`:

```text
ROM01:141A  LD   HL,0D39Dh   ; argument
ROM01:141D  PUSH HL          ; arguments go on the stack
ROM01:141E  CALL 0EE2Ch      ; C-RX-BLK
ROM01:1421  POP  DE          ; the caller cleans up
ROM01:1422  LD   (0D0FEh),HL ; result comes back in HL
ROM01:1425  LD   A,H
            OR   L
ROM01:1427  JP   Z,143Ah     ; 0 -> continue
```

* **Arguments** are pushed on the stack; the caller removes them.
* **The result is returned in `HL`**, and the firmware keeps it in
  `ram:D0FE` as the session's last-result cell.
* **Results are sequenced.** The same site *guards* its call on the previous
  result: `C-RX-BLK` is only issued when `D0FE` already holds 8. So a
  multi-step exchange is driven by testing `D0FE` between calls — that is
  the status mechanism, rather than a separate poll entry point. `0` and `8`
  are the two values treated as success here; `8` is also what a stream's
  final block returns.

There is no separate "run" or "get status" entry point in the table. The
session advances one command at a time, each call returning its own result.

### The caveat: a call may not come back

The firmware's callers resume normally, and the mechanism is an ordinary
call: `ram:D837` is a stack-frame prologue that saves `IX`/`IY`, invokes the
body through `D836` (`JP (HL)`), and returns the result in `HL`. There is no
scheduler involved.

Calls made from a loaded COM have nonetheless not come back, and the reason
turns out to be mundane rather than structural: **the firmware stops to talk
to the user.** Calling `C_ABORT` from the boot state reaches an illegal
transition, which puts a message box on the screen and waits in
`SessionWaitContinue` for a keypress. `EE24` displays `Comms in progress` and
likewise does not return.

So an application must either drive a *legal* sequence of transitions, or be
prepared to satisfy the UI. Issuing a command that the state machine rejects
will hang a headless caller. This is the practical obstacle to sending data
back, and it is a sequencing problem rather than a calling-convention one.

## Worked example

This 16-byte COM initialises the session and proves the call took effect:

```text
0100  3E AA        LD   A,0AAh
0102  32 00 02     LD   (0200h),A   ; marker: reached the call
0105  CD 24 EE     CALL 0EE24h      ; initialise the session
0108  3E 55        LD   A,055h
010A  32 00 02     LD   (0200h),A   ; would mark a normal return
010D  C3 0D 01     JP   $
```

Running it in the emulator leaves the mode gate at 2 and its companion cell
at `0x37`, where a control program that does not make the call leaves both
at 0 — so the call reached the firmware and did its work. The marker holds
`AA`, never `55`, for the reason described above.

Regression: `CommstarApplicationApiTest` in `analysis/test_boot_upload.py`.

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
