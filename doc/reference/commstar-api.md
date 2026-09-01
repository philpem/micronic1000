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

### An application-driven session, working

A loaded COM can hold a complete Commstar session. This sequence, with the
argument layout above, gets through five commands and uploads data to the
host:

```text
CALL 0EE20h   ; C-INIT-COMMS, mode 0   -> DISCONNECTED
CALL 0EE10h   ; C-DIAL                 -> CONNECTED
LD A,2 / LD (0E48Dh),A                 ; suppress validation
CALL 0EE08h   ; C-BEGIN-FILE
CALL 0EE44h   ; C-TX-REC               <- the handheld sends data
CALL 0EE18h   ; C-END-FILE
```

Observed: ten request/reply exchanges, the session state reaching
`CONNECTED`, and **three objects sent by the handheld to the host** — 9 bytes
at state `0006`, then 128 and 72 bytes at state `0045`.

Each command returns, so an application really can drive a sequence. Two
things had to be true first, and both were harness bugs rather than protocol
obstacles: the emulator has to keep the RTC running while a loaded program
executes, or no periodic interrupt fires and the receive path never runs; and
the peer has to be pumped from the same loop.

### Uploading a file of records

Both `C-BEGIN-FILE` and `C-TX-REC` take a **pointer** to a counted buffer,
and unlike the other entry points they read the **last** word pushed (caller
`SP+0`), not the third down:

```text
buffer:  [u8 count][bytes ... count of them]
```

`C-BEGIN-FILE` names the file, `C-TX-REC` supplies a record, `C-END-FILE`
closes it, `C-END-TX` flushes. What reaches the host is one object:

```text
06 4d 59 46 49 4c 45  1e  53 43 41 4e ... 54  1c
^^ ^^^^^^^^^^^^^^^^^  ^^  ^^^^^^^^^^^^^^^^^  ^^
 |  "MYFILE"          |   "SCAN:0042:WIDGET"  |
 count, from          |   the record payload  C-END-FILE's
 C-BEGIN-FILE         C-TX-REC's marker       terminator
```

So the stream format is:

```text
[u8 namelen][name]  1Eh [record]  1Ch
```

Note the asymmetry: the **name** is sent with its count byte, the **record**
is not — `ROM00:3E14` sends `buffer[1..count]` only. The two marker bytes come
from `ROM00:3D9B` calls with literals: `1Eh` at `ROM00:5107` inside
`C-TX-REC`, `1Ch` at `ROM00:5193` inside `C-END-FILE`.

Regression: `CommstarRecordUploadTest`.

Passing a null pointer is what produced the meaningless `c3 03 01` prefix in
an earlier attempt: `C-BEGIN-FILE` read `mem[0]` — `C3h`, the first byte of
resident code — as its name length.

### Suppressing validation

Set `ram:E48D = 2` before issuing commands:

```text
3E 02        LD   A,2
32 8D E4     LD   (0E48Dh),A
```

`SessionStartDataMode` then returns without consulting the transition table,
so an operation runs whatever the current state. **CONFIRMED:** with this in
place, `C_ABORT` from `NOT-STARTED` raises no message box and leaves
`ram:E512 = 0`, the early-return marker; the identical call without it raises
the illegal-transition box.

This is not a trick — it is how the firmware itself reaches operations the
table cannot: only the `RECORD-RX` path is legally reachable, so Program
Reception and everything on the transmit side must run with validation off.

**A call still does not return, and now the reason is visible.** With
validation suppressed, `SessionStartDataMode` returns 0, and the operation
wrapper reads 0 as *proceed*:

```text
ROM00:5473  CALL 452Dh       ; SessionStartDataMode(C_ABORT)
ROM00:547A  LD   A,H / OR L
ROM00:547C  JP   NZ,54E1h    ; non-zero -> exit
ROM00:547F  CALL 593Ah       ; zero -> do the work
```

`593A` reaches `SessionTxRunState65`, which prepares a frame header, sets the
session parameters with wire state `0x65`, sends the frame through service 33
and then waits in `SessionRxByteLoop`.

So these are not local calls that happen to block — **they are link
transactions**. The routine transmits and waits for the host to answer. A
call made with no peer attached cannot return, and that is the protocol
working, not a fault.

The practical consequence: exercising the API needs a responding peer, which
is exactly what a Commstar server is. The emulator's synthetic peer already
does this for the Load/Run path; pointing it at an application-driven session
is the next step.

In the bare-COM test the link transmit counter never fired, so it blocks
somewhere between entering `SessionTxRunState65` and reaching the link
driver — plausibly because no session was ever opened. `C-INIT-COMMS` is the
legal first command from `NOT-STARTED`, and driving that first is the
obvious next experiment.

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
