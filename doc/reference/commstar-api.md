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

Repeated `C-TX-REC` calls **append**, so the general form is:

```text
[u8 namelen][name]  (1Eh [record])*  1Ch
```

Two records under one name arrive as
`05 "STOCK" 1e "REC-ONE" 1e "REC-TWO" 1c`.

**LIKELY: these are the ASCII information separators.** `1Eh` is RS (record
separator) and `1Ch` is FS (file separator), and the firmware uses them
exactly as ASCII defines them — `1Eh` before each record, `1Ch` to end the
file. Only those two appear; GS (`1Dh`) and US (`1Fh`) are never sent.

Note the asymmetry: the **name** is sent with its count byte, the **record**
is not — `ROM00:3E14` sends `buffer[1..count]` only. The two marker bytes come
from `ROM00:3D9B` calls with literals: `1Eh` at `ROM00:5107` inside
`C-TX-REC`, `1Ch` at `ROM00:5193` inside `C-END-FILE`.

Regression: `CommstarRecordUploadTest`.

Passing a null pointer is what produced the meaningless `c3 03 01` prefix in
an earlier attempt: `C-BEGIN-FILE` read `mem[0]` — `C3h`, the first byte of
resident code — as its name length.

### Why the session cannot end cleanly

`C-END-TX` **does take a 16-bit argument**, at the same last-pushed slot as
`C-BEGIN-FILE` and `C-TX-REC`, and which of two dispositions it takes is
decided by the mode gate:

```text
530D  LD A,(0E48Dh)          ; the mode gate again
5316  CALL E04B              ; E48D == 1 ?
5319  JP Z,533Eh             ; not 1 -> the ARGUMENT path

531C  LD HL,(0E516h)         ; E48D == 1: the clean completion --
5324  CALL 41D9h             ;   display "Data transmitted"
5330  LD A,(0E48Ch) / CALL 3BF5h   ;   and commit the session state

533E  LD HL,000Ch / ADD HL,SP      ; otherwise: read the caller's argument
5346  CALL 3F20h                   ;   and send it, 58B8(arg+1, 00FFh, arg)
```

So there are two ways to finish, and with the session at `CONNECTED` neither
is available:

* `E48D = 2` — dispatch is suppressed, so `C-END-TX` takes the argument path
  and transmits. This is what the demonstration does, with an argument it
  never meant to supply, and it is why the screen ends at `Abort pending`.
* `E48D = 1` — dispatch runs, but `table[CONNECTED][C-END-TX]` is `8Dh`:
  illegal, next state `CRASHED`. `452D` returns non-zero and `52F8` exits
  before the completion path.

The clean finish at `531C` needs **both** `E48D = 1` **and** a state from
which `C-END-TX` is legal — `READY-TX-DATA`, `READY-TX-PROG`, `DATA-SET-TX`
or `BLOCK-TX`. Those are the states the transition table cannot reach, so a
clean teardown and the reachability question are the same question.

Also note `C-END-FILE` takes an argument (`ROM00:523F`, same slot) and
`C-INIT-COMMS` reads **three** (`4569`, `45D1`, `45EE`). Neither is
characterised; the demonstration supplies zeros.
