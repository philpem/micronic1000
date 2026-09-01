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

### Sending and receiving blocks

A **block** is a program; a **record** is data. The two paths use the same
counted-buffer format in memory but differ on the wire.

**Send a block** — `C-TX-BLK`, `ram:EE40`:

```text
buffer:  [u8 count][count bytes]        ; count 0..255
PUSH buffer / CALL 0EE40h / POP DE      ; HL = result
```

The pointer goes to `ROM00:3E14`, the *same* counted-buffer walker
`C-TX-REC` uses. `C-TX-BLK` issues the state-`0064` "begin transmit" itself
on its first call, so no separate bracket command is needed; `C-END-TX`
flushes the tail.

**Receive a block** — `C-RX-BLK`, `ram:EE2C`:

```text
PUSH buffer / CALL 0EE2Ch / POP DE      ; buffer must be >= 129 bytes
```

On return `buffer[0]` is the count actually received and `buffer[1..count]`
the data. `HL` is the status: `0` continue, **`8` end of data** — at which
point the firmware displays `Program received` — and `4`/`9`/other are
errors. Loop until `8`.

The **129-byte minimum is not negotiable**: `ROM00:4FAD` pushes a hard-coded
maximum of `0080h` before calling `Session_ReadStreamChunk`, so a block is at
most 128 data bytes plus the count byte. Note the asymmetry — `C-TX-BLK`
will *send* up to 255 bytes in one call, resegmented into 128-byte wire
frames by the buffer underneath.

**The block path emits no separator bytes.** This is the substantive
difference from records. `ROM00:3D9B` is the byte injector, and it has
exactly four call sites in ROM00: `3E57` and `3F0D` (payload and filename
loops), `5107` (`C-TX-REC`, literal `1Eh`) and `5193` (`C-END-FILE`, literal
`1Ch`). `C-TX-BLK` has no equivalent instruction — its first action after the
command dispatch is the `3E14` call. `1Dh` GS is never pushed as an argument
anywhere in ROM00, and the single `1Fh` push (`ROM00:5FD7`) goes to a
different routine on the dial path.

That follows from what the two paths carry. Records are variable-length items
in one continuous byte stream, so they need RS between and FS at the end.
Blocks are framed by the transport itself — the payload-length field in the
frame header — so raw binary needs no in-band markers, and could not tolerate
them.

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

### Argument reference

Every entry point's arguments, swept from the ROM by
`analysis/commstar_args.py` and cross-checked against the firmware's own call
sites. A wrapper reads an argument with `LD HL,off / ADD HL,SP`, where `off`
is relative to **SP at that instant** — so argument marshalling, which pushes
as it goes, shifts it. The caller's slot is `off − 0Ch − depth`, `depth`
being how far SP has moved since the routine's `CALL D837` prologue. Reading
`off − 0Ch` alone misplaces any argument fetched with a push outstanding;
`C-RX-BLK` is the case that catches it.

| Entry point | Routine | Arguments |
|---|---|---|
| `C_ABORT` `EE00` | `5469` | none |
| `C-ANSWER` `EE04` | `48BF` | `SP+0` |
| `C-BEGIN-FILE` `EE08` | `5034` | `SP+0` — `[u8 len][name]` |
| `C-COMMAND` `EE0C` | `4AE0` | `SP+0` operation index, `SP+2` 12-byte parameter, `SP+4` |
| `C-DIAL` `EE10` | `47F6` | `SP+0` |
| `C-DROP-LINE` `EE14` | `4A25` | none |
| `C-END-FILE` `EE18` | `5179` | none |
| `C-END-TX` `EE1C` | `52A5` | `SP+0` disposition |
| `C-INIT-COMMS` `EE20` | `4563` | ten — see below |
| *initialise session* `EE24` | `46E9` | `SP+0`, `+2`, `+4`, `+6`, `+8` |
| `C-MANUAL` `EE28` | `4974` | none |
| `C-RX-BLK` `EE2C` | `4F5A` | `SP+0` — destination, ≥129 bytes |
| `C-SHUT-DOWN` `EE30` | `4D29` | none |
| `C-RX-REC` `EE34` | `4E6D` | `SP+0` |
| `C_ABORT` `EE38` | `5444` | `SP+0`, `+2`, `+4` |
| `C-SHUT-DOWN` `EE3C` | `4D75` | none |
| `C-TX-BLK` `EE40` | `51EC` | `SP+0` — `[u8 count][payload]` |
| `C-TX-REC` `EE44` | `50ED` | `SP+0` — `[u8 count][record]` |
| `C-SHUT-DOWN` `EE48` | `4D4F` | none |
| `C_ABORT` `EE4C` | `5428` | `SP+0`, `+2` |

Two things this settles.

**The duplicate wrappers differ in arity.** `C_ABORT` appears three times
and each takes a different number of arguments — none, three, two — so they
are genuinely distinct routines, not aliases. The three `C-SHUT-DOWN`
wrappers all take none.

**`C-END-TX` takes one argument, `C-END-FILE` none.** This corrects the note
committed in `c840242`, which attributed the read at `ROM00:523F` to
`C-END-FILE`. `523F` is inside `C-TX-BLK` (`51EC`–`52A4`); `C-END-FILE` is
`5179`–`51EB` and contains no stack read at all. The earlier scan used an
extent that swallowed the following routine.

### The command record

`C-COMMAND` assembles a **54-byte record at `ram:E492`** and transmits it
whole:

```text
ROM00:4C11  LD   HL,0036h    ; 54 bytes
ROM00:4C14  PUSH HL
ROM00:4C15  LD   HL,0E492h
ROM00:4C18  PUSH HL
ROM00:4C19  CALL 5880h       ; -> 612A, wire state 45h
```

The fields are copied in one by one at `ROM00:4B84`–`4C05`, each through the
bounded string copy `ram:DB89(dst, src, maxlen)`. The destinations are
contiguous and their maxima tile the record exactly:

| Offset | Size | Copied from | Field |
|---|---|---|---|
| `+0` | 8 | `E6D0` | *(unidentified)* |
| `+8` | 6 | `E6E8` | *(unidentified)* |
| `+14` | 4 | `*(E48F)` | **operation name** |
| `+18` | 8 | `E6EF` | **workstation id** |
| `+26` | 8 | `E6C4` | *(unidentified)* |
| `+34` | 8 | `E6D9` | *(unidentified)* |
| `+42` | 12 | `C-COMMAND` `SP+2` | per-command parameter |

**CONFIRMED against the traces.** Every Load/Run capture carries a 54-byte
object at wire state `0045`, with `"LOAD"` at object `+14` and the
workstation serial at `+18` — the two fields decoded above, at the offsets
this layout predicts. The remaining fields are blank in those traces, which
is consistent: Load/Run asks the operator for no credentials.

`E48F` holds a pointer into the operation table, set at `ROM00:4B26` from
`E247 + 6 × index` — so **`C-COMMAND`'s first argument selects both the
operation name sent at `+14` and the session state entered on success.**
See the protocol page for the operation table itself.

### `C-INIT-COMMS`

Ten arguments, all 16-bit slots:

| Slot | Kind | Purpose |
|---|---|---|
| `SP+0` | byte | passed to `ROM00:5669` |
| `SP+2` | byte | passed to `ROM00:5669` |
| `SP+4` | byte | **session mode**, stored to `ram:E48D` (`ROM00:4570`) |
| `SP+6` | byte | passed to `ROM00:5669` |
| `SP+8` | pointer | passed to `ROM00:5669` |
| `SP+10` | pointer | string → `E6D0`, max 8 → record `+0` |
| `SP+12` | pointer | string → `E6E8`, max 6 → record `+8` |
| `SP+14` | pointer | string → `E6EF`, max 8 → record `+18`, **workstation id** |
| `SP+16` | pointer | string → `E6C4`, max 8 → record `+26` |
| `SP+18` | pointer | string → `E6D9`, max 8 → record `+34` |

So `C-INIT-COMMS` does not send anything itself: it **latches five identity
strings** that every later `C-COMMAND` transmits. Only the third is pinned
by evidence. **LIKELY the other four are the V24 Log-on form's credentials**
— that form collects User id, Password, Group id and Telephone, four string
fields for four unidentified slots — but which slot takes which field is not
established, and the 6-character maximum on `SP+12` is the only distinguishing
clue.

`ROM00:5669` receives the remaining four and latches `ram:E520`, the link
type, at `ROM00:5676`.

The demonstration in this page passes four words and works, because the path
it takes never reads the identity slots. An application talking to a real
host must supply all ten.

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
