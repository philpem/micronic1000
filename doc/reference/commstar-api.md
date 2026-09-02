# Commstar application API

**Stability: Provisional.** The entry points and the calling convention are
verified in the emulator; the argument and result contract of individual
operations is not established.

A loaded COM or DIP program can drive the Commstar session directly. The
firmware publishes twenty fixed entry points in the transfer-vector table,
and they work when called from an application even though the firmware's own
UI reaches only nine of them.

This matters because the firmware alone only ever completes *Program
Reception*. Everything else the protocol can do — including sending collected
data back to a host — is reachable only this way.

**Start here if you are implementing a host.** The two sequences that are
demonstrated end to end are
[receiving a program](#receiving-a-program-the-whole-sequence) and
[uploading a file of records](#uploading-a-file-of-records) followed by
[ending the session cleanly](#ending-a-session-cleanly). Both run with the
session mode at **0**; you do not need to suppress validation for either.

## Entry points

Each entry is four bytes at a fixed address in battery-backed RAM. Call it
like an ordinary subroutine; see the calling convention below for the
important caveat.

| Address | Routine | Command dispatched | Session screen |
|---|---|---|---|
| `EE00` | `5469` | `C_ABORT` (16) | |
| `EE04` | `48BF` | `C-ANSWER` (2) | |
| `EE08` | `5034` | `C-BEGIN-FILE` (11) | Sending data |
| `EE0C` | `4AE0` | `C-COMMAND` (5) | |
| `EE10` | `47F6` | `C-DIAL` (1) | |
| `EE14` | `4A25` | `C-DROP-LINE` (4) | |
| `EE18` | `5179` | `C-END-FILE` (13) | |
| `EE1C` | `52A5` | `C-END-TX` (15) | |
| `EE20` | `4563` | `C-INIT-COMMS` (0) | |
| `EE24` | `46E9` | — *initialise session* | |
| `EE28` | `4974` | `C-MANUAL` (3) | |
| `EE2C` | `4F5A` | `C-RX-BLK` (10) | Receiving prog |
| `EE30` | `4D29` | — *message box* | |
| `EE34` | `4E6D` | `C-RX-REC` (9) | Receiving data |
| `EE38` | `5444` | — *solicit data block* | |
| `EE3C` | `4D75` | `C-SHUT-DOWN` (8) | |
| `EE40` | `51EC` | `C-TX-BLK` (14) | Sending prog |
| `EE44` | `50ED` | `C-TX-REC` (12) | |
| `EE48` | `4D4F` | — *message box* | |
| `EE4C` | `5428` | — *send data block* | |

**Each command appears exactly once.** The "command dispatched" column is
derived, not assumed: `SessionStartDataMode` (`ROM00:452D`) has fifteen call
sites in ROM00 and each pushes a distinct literal index, so the mapping from
slot to command is one-to-one and complete.

**Correction.** An earlier version of this table listed `C_ABORT` three times
and `C-SHUT-DOWN` three times, and said the duplicates "have not been told
apart". There are no duplicates — those labels were wrong. Five slots
dispatch no protocol command at all:

* `EE24` `46E9` initialises the session (below).
* `EE30` `4D29` and `EE48` `4D4F` are **message-box helpers**, calling
  `SessionMessageBox` with `"   not available"` / `"   in Workstation"`.
  They differ only in which buffer pair they use (`E278`/`E279` versus
  `E288`/`E289`).
* `EE38` `5444` forwards three arguments to `ROM00:5915` -> `62C7`, which
  sends wire states `0043` then `0044` — it **solicits a data block from the
  host**.
* `EE4C` `5428` forwards two arguments to `ROM00:58F9` -> `63CA` -> `612A`,
  wire state `0045` — it **sends a data block**.

The last two are the raw transfer primitives, below the command layer: they
never call `SessionStartDataMode`, so no state check applies to them at all.

The two commands with no entry point are `C-RX-CMD` (6) and `C-TX-REPLY` (7).
Neither has a stub slot and no routine in either ROM dispatches them.

`EE24` is not a protocol command. It initialises the session: it clears a
dozen session variables, sets `ram:E48D = 2`, and displays
`Comms in progress`. It does not return — it appears to run the session
rather than merely prepare it, so treat it as a session *runner* whose
contract is not yet established.

Note that `E48D = 2` **suppresses** per-command dispatch:
`SessionStartDataMode` runs the state machine when `E48D` is *not* 2. That is
not something a working session needs — see
[the session mode](../protocol/commstar.md#rame48d-the-session-mode) on the
protocol page, and [Suppressing validation](#suppressing-validation) below.

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
  result, and the sense is "keep going until 8":

  ```text
  ROM01:140E  LD   HL,(0D0FEh)
  ROM01:1411  LD   DE,0008h
  ROM01:1414  CALL 0E04Bh      ; equality test: returns NZ when equal
  ROM01:1417  JP   NZ,14BAh    ; D0FE == 8 already -> skip C-RX-BLK
  ```

  So a multi-step exchange is driven by testing `D0FE` between calls — that
  is the status mechanism, rather than a separate poll entry point. `0` and
  `8` are the two values treated as success; `8` is what the *last* block
  returns, and the same site still consumes that block's bytes
  (`ROM01:142A`–`1433` branches to the store at `143A` when the result is 8),
  so **status 8 can carry data**.

  **Correction.** An earlier revision of this page read the guard backwards
  and said `C-RX-BLK` "is only issued when `D0FE` already holds 8". `ram:E04B`
  sets the zero flag when its operands *differ*, so `JP NZ` means *equal*: the
  loop stops at 8, it does not start there.

!!! warning "Two comparison helpers, opposite conventions"
    The compiled session code calls two 16-bit comparison helpers that look
    interchangeable and are not. Both are byte-verified in `ram`:

    * **`ram:E04B` is `==`.** Equal → `HL = 1`, **NZ**. Different → `HL = 0`,
      **Z**.
    * **`ram:E05A` is `!=`.** Equal → `HL = 0`, **Z**. Different → `HL = 1`,
      **NZ**.

    They appear within nine instructions of each other at `ROM01:1414` and
    `ROM01:1430`, testing the same cell against the same constant, and the
    two branch senses are opposite. Every polarity error corrected on this
    page started here.

There is no separate "run" or "get status" entry point in the table. The
session advances one command at a time, each call returning its own result.

### Every buffer must live in unbanked RAM

**CONFIRMED, and it is the first thing to get right.** A pointer you pass to
any of these entry points must address the **fixed upper 32K**
(`0x8000`-`0xFFFF`). A buffer in the caller's own page — the obvious place, in
the space a CP/M-style COM has above its code — is **invisible to the
routine**.

The reason is the call mechanism. Each entry point is a four-byte thunk
`RST 10h ; db bank ; dw target`, and `RST 10h` (`ROM00:0010`) compares the
target bank against the current one:

```text
ROM00:0010  POP  HL            ; HL = the inline operands
ROM00:0011  LD   E,(HL)        ; target bank
ROM00:0012  LD   A,(0F791h)    ; current bank
ROM00:0015  CP   E
ROM00:0016  JP   NZ,0D74Bh     ; different -> the cross-bank path
```

`ram:D74B` saves the caller's context, switches the bank, calls, and puts
everything back:

```text
ram:D74D  LD   HL,(0E36Fh)   ; the shadow stack pointer
ram:D750  DEC HL / LD (HL),A ;   push the CALLER'S BANK
ram:D752  DEC HL / LD (HL),D
ram:D754  DEC HL / LD (HL),E ;   push the return address
ram:D756  LD   (0E36Fh),HL
ram:D75F  CALL 0D770h        ; switch bank and run the target
ram:D763  LD   HL,(0E36Fh)   ; on return, pop the frame back --
ram:D766  LD   E,(HL) / INC HL / LD D,(HL) / INC HL
ram:D76A  LD   A,(HL) / INC HL   ;   including the caller's bank
ram:D76C  LD   (0E36Fh),HL
```

**So the caller's bank is saved and restored** — a `RST 10h` call returns with
the paging exactly as it left it. What does *not* happen is the caller's page
being mapped **while the callee runs**: the lower 32K holds ROM00 for the
duration. That is what makes a banked buffer useless here, and it is a
separate matter from the paging being restored afterwards.

The firmware's own practice confirms it — **every buffer it passes is
unbanked**:

| Call site | Entry point | Buffer |
|---|---|---|
| `ROM01:141A` | `C-RX-BLK` | `ram:D39D` |
| `ROM01:1343` | `C-COMMAND` | `ram:D422` |
| `ROM01:12AD`-`12BD` | `C-INIT-COMMS` | `ram:ECAB`, `EC99`, `ECA2`, `EC8E`, `D120` |

Not one of them is below `0x8000`.

**So a driver COM must place its buffers in the upper 32K** — which means
finding space that the firmware is not already using. The loader's own limit
is a useful landmark: `ROM00:7052` (`21 81 D0 / 22 BD E3`) sets
`g_pProgramLoadCeiling = ram:D081`, and module B begins exactly there, so
`D081` is the top of the space a loaded program may occupy. That is not obvious by
inspection, and picking an address by guesswork has already caused one real
bug: the emulator harness staged upload chunks at `ram:E5C2` and ran over
live session state. See
[RE notes: unbanked RAM map](../re-notes/unbanked-ram-map.md) for what is
occupied and what is safe.

### An application-driven session, working

A loaded COM can hold a complete Commstar session. This was the first
sequence to get data out of a handheld:

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

!!! warning "Superseded — do not copy this sequence"
    The `LD A,2` line was a workaround for a misreading, not a requirement.
    It skips the `C-COMMAND` that tells the host *what the handheld is
    doing*, and it leaves the session at `CONNECTED`, from which `C-END-TX`
    cannot complete — so this sequence can only be abandoned, not closed.
    The correct sequence keeps the mode at 0 and issues `C-COMMAND` index 2
    `SEND` first, which is also what tells the host an upload is coming. See
    [Ending a session cleanly](#ending-a-session-cleanly).

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

**But a host must never send more than 126 bytes in one object.** The
handheld asks for 128 — that `0080h` reaches the wire as the `size` field of
its `0044` request — and then cannot take it.

**CONFIRMED by experiment, and the boundary is sharp**: serving the same
300-byte image in 126-byte blocks completes and displays `Program received`;
in 127-byte blocks every object is dropped without an acknowledgement, the
handheld re-requests, and the session ends `Abort pending` / `Session
aborted` with `C-RX-BLK` returning 4. `micronic.peer.MAX_OBJECT_DATA` is that
limit and `ProgramDownloadPolicy` caps itself at it.

The *mechanism* is not fully derived. `ROM00:620B` sets the `0044` receive
frame length to `86h` = 134 (`21 86 00 E5`, pushed to `SessionSetParams`),
and 134 − 8 = 126 is arithmetically consistent with an eight-byte preamble
ahead of the object body at `ram:E5C4`. But the RX frame struct at `ram:E5BA`
is 138 bytes with its data area at `+0Ah`, which would suggest a different
budget, and the two readings have not been reconciled. **Treat 126 as a
measured limit rather than a derived one** — it is reproduced by regression,
which is what matters for an implementation, but do not rely on the
explanation when reasoning about neighbouring cases.

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

#### Which path for binary data?

"Blocks are programs, records are data" is a statement about **framing, not
content.** Nothing in the firmware inspects what you hand it, and the two
labels come only from the display strings (`Sending prog` at `ROM00:6CE8`
versus `Sending data` at `6CDB`).

What *is* hard and fast is that **the record path is not 8-bit clean.**
`ROM00:3E14` walks the buffer and sends every byte raw — it contains no
comparison, no escape, no stuffing. So a record whose payload contains `1Eh`
or `1Ch` puts a byte on the wire that the host cannot distinguish from a
record separator or an end-of-file marker. There is no way to quote it.

The block path has no in-band markers at all, so it is 8-bit clean.

**So yes, you can have binary data files — send them as blocks.** The
firmware will call it a program on screen and the session will run in
`READY-TX-PROG` rather than `READY-TX-DATA`, but the bytes are unexamined and
arrive intact. The reverse also holds: a "program" whose bytes happen to
avoid `1Eh` and `1Ch` would survive the record path, though there would be no
reason to send it that way.

Note also that the handheld never *parses* separators. The only comparisons
against `1Eh`/`1Ch` anywhere in ROM00 are at `279B`, `018E` and `27BA`, none
of them in the session code. The separators exist purely so the **host** can
segment the stream, which means a Commstar server has to do that
segmentation itself.

### Receiving a program: the whole sequence

**CONFIRMED end to end.** A loaded application downloads a program with four
commands, and `micronic.peer.ProgramDownloadPolicy` is the host half:

```text
CALL 0EE20h   ; C-INIT-COMMS   ten args; slot 2 = link type 4, slot 4 = mode
CALL 0EE10h   ; C-DIAL         -> CONNECTED   (wire 0062 on an IR link)
CALL 0EE0Ch   ; C-COMMAND      index 3 "LOAD" -> READY-RX-PROG
loop:
CALL 0EE2Ch   ; C-RX-BLK       -> 0 keep going, 8 the last block
```

On the wire that is `0000`, `0006`, `0062`, `0064`, `0045`, then one `0044`
per block. What the host has to do at each point:

| Handheld sends | Host answers |
|---|---|
| `0000`, `0006`, `0062`, `0064` | a control ack (a single `00` payload byte) |
| `0045` with a 54-byte object | a control ack; **this is the command record** — read the operation name at object `+14` and the program name at `+42` |
| `0044`, `size = 00FFh` | the command's **reply**: an object holding `OK`, marker 1 |
| `0044`, `size = 0080h` | the next `<= 126` bytes of the image, marker 0, and marker 1 on the last |

**The two `0044` shapes are distinguishable two ways**, and both are the
ROM's own: the first one after a command is that command's reply
(`ROM00:4C3A` calls `3F20`, which asks for `00FFh` at `ROM00:3F39`), and
every later one is a block (`ROM00:3D59` asks for `0080h`). Order alone is
enough for a peer that tracks the session; the size field corroborates it.

**Marker 1 is what ends the stream, and it is not optional on the reply
either.** `ROM00:3D59` turns a marker-1 read into the end-of-stream flag
`ram:E44A`, which is what finally makes `C-RX-BLK` return 8; and the
command-reply classifier `ROM00:3FEC` only reaches its `OK`/`NO`/`DM`
comparison on status 8, so a marker-0 reply to a command is read as *no
reply at all*.

Measured, serving a 300-byte image in 126-byte blocks: three blocks of 126,
126 and 48; `C-RX-BLK` returns 0, 0, 8; the third call carries 48 bytes
*and* the end-of-data status; the 300 bytes reassemble by plain
concatenation, byte for byte; and the screen ends on `Program received`.

Regression: `CommstarProgramDownloadTest` in `analysis/test_boot_upload.py`,
driven by `boot_hw.py --commstar-peer --commstar-serve-program`.

### Ending a session cleanly

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

**Correction.** An earlier revision of this page was headed "why the session
cannot end cleanly" and concluded that neither disposition was available.
Both are, and **both end cleanly** — the argument path is not an abort path.
Its `OK` case, `ROM00:534D`, does exactly what `531C` does: display
`ram:E516` and commit `ram:E48C`.

What produced `Abort pending` in that demonstration was the **session state**,
not the disposition, and the two modes failed for different reasons:

* with `E48D = 2` the transition table is not consulted, so `C-END-TX`
  proceeded to the argument path at `533E` and sent an argument the test never
  meant to supply;
* with `E48D = 1` the table *is* consulted, and
  `table[CONNECTED][C-END-TX]` is `8Dh` — bit 7 set, illegal, next state
  `CRASHED` (byte-verified at `micron1.bin 0x695B`) — so
  `SessionStartDataMode` returned non-zero and `ROM00:52F8` exited before the
  completion path.

The fix is the same either way: be in a state from which `C-END-TX` is legal.

What the completion actually needs is a **session state from which
`C-END-TX` is legal** — `READY-TX-DATA`, `READY-TX-PROG`, `DATA-SET-TX` or
`BLOCK-TX`. `C-COMMAND` reaches one directly: index 2 `SEND` writes
`READY-TX-DATA` out of `tbl_sess_operations` without consulting the
transition matrix.

**CONFIRMED by experiment.** This sequence ends on `Data transmitted`, with
the session back at `CONNECTED`:

```text
CALL 0EE20h   ; C-INIT-COMMS   -> DISCONNECTED   (1)
CALL 0EE10h   ; C-DIAL         -> CONNECTED      (2)
CALL 0EE0Ch   ; C-COMMAND, index 2 "SEND" -> READY-TX-DATA (5)
CALL 0EE08h   ; C-BEGIN-FILE   -> RECORD-TX      (9)
CALL 0EE44h   ; C-TX-REC       -> RECORD-TX      (9)
CALL 0EE18h   ; C-END-FILE     -> DATA-SET-TX   (10)
CALL 0EE1Ch   ; C-END-TX       -> CONNECTED      (2)
```

Every step returns 0, the state sequence is `1 2 5 9 9 10 2` read back out of
`g_bSessionState` (`ram:E22D`), and the host receives one object,
`05 "STOCK" 1e "REC-ONE" 1c`. It works with the mode at **1** (the `531C`
branch) and with the mode at **0** (the `533E` branch), so the reachability
of states 4, 5 and 6 is now demonstrated and not merely inferred.

**One catch, and it is a real one for a host.** With `E48D = 1`,
`C-COMMAND` never transmits: `ROM00:4B40` tests the mode and, when it is 1,
falls through to `4B4F`, which sets the state from `ram:E491` and returns 0
without building or sending the 54-byte record. `C-SHUT-DOWN` (`ROM00:4D92`)
short-circuits the same way. So mode 1 buys a clean teardown at
the price of the host never learning what the handheld is doing. Mode 0
sends the command record *and* still finishes cleanly, so **mode 0 is what a
real session should use**; mode 1 is useful when there is no host to tell.

Regression: `CommstarCleanTeardownTest`.

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
| `C-COMMAND` `EE0C` | `4AE0` | `SP+0` operation index, `SP+2` 12-byte parameter, `SP+4` reply buffer |
| `C-DIAL` `EE10` | `47F6` | `SP+0` — the number buffer |
| `C-DROP-LINE` `EE14` | `4A25` | none |
| `C-END-FILE` `EE18` | `5179` | none |
| `C-END-TX` `EE1C` | `52A5` | `SP+0` disposition |
| `C-INIT-COMMS` `EE20` | `4563` | ten — see below |
| *initialise session* `EE24` | `46E9` | `SP+0`, `+2`, `+4`, `+6`, `+8` |
| `C-MANUAL` `EE28` | `4974` | none |
| `C-RX-BLK` `EE2C` | `4F5A` | `SP+0` — destination, ≥129 bytes |
| *message box* `EE30` | `4D29` | none |
| `C-RX-REC` `EE34` | `4E6D` | `SP+0` |
| *solicit data block* `EE38` | `5444` | `SP+0`, `+2`, `+4`, forwarded to `5915` |
| `C-SHUT-DOWN` `EE3C` | `4D75` | none |
| `C-TX-BLK` `EE40` | `51EC` | `SP+0` — `[u8 count][payload]` |
| `C-TX-REC` `EE44` | `50ED` | `SP+0` — `[u8 count][record]` |
| *message box* `EE48` | `4D4F` | none |
| *send data block* `EE4C` | `5428` | `SP+0`, `+2`, forwarded to `58F9` |

One thing this settles.

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

#### The command's reply, and `C-COMMAND`'s third argument

`C-COMMAND`'s `SP+4` is a **buffer the host's answer is read into**, and it
is not optional. After transmitting the record, `ROM00:4C32` pushes that
pointer and calls `ROM00:3F20`, which solicits a block (`58B8(arg+1, 00FFh,
arg)`, wire state `0044` with `size = 00FFh`) and leaves the answer as a
counted buffer:

```text
reply:  [u8 count][count bytes]        ; count up to 255
```

`ROM00:3F65` then compares the **first two bytes** against a three-entry
table copied to `ram:E22F`, `{char name[2]; u8 code}` at stride 4:

| Reply | Code | `C-COMMAND` result | Effect |
|---|---:|---:|---|
| `OK` | 0 | 0 | the operation's target state is committed (`ROM00:4C62`) |
| `NO` | 1 | 5 | back to `CONNECTED` |
| `DM` | 2 | 5 | back to `CONNECTED` |
| anything else | 3 | 6 | error `0x1F75` (8053), `Invalid reply` |

Byte-verified at `micron1.bin` `0x7303` (the source of `ram:E22F`):
`4F 4B 00 00 | 4E 4F 00 01 | 44 4D 00 02` — `OK`→0, `NO`→1, `DM`→2. The
firmware's own call site passes `ram:D422` as the buffer (`ROM01:1343`).
**A host that never answers a command record cannot advance the session**,
and it must send the answer with
marker 1, because `3FEC` only reaches this comparison on read status 8.

The firmware never inspects the bytes after the first two, so `OK` alone is
a valid answer; the traced Load/Run peer sends `OK` followed by four more
bytes and the firmware ignores them.

### `C-INIT-COMMS`

Ten arguments, all 16-bit slots. **CONFIRMED**: the firmware's own call site,
`ROM01:12AD`–`ROM01:1304`, pushes exactly ten words and cleans up with
`LD HL,0014h / ADD HL,SP / LD SP,HL` — twenty bytes.

| Slot | What the firmware passes | Destination | Record field |
|---|---|---|---|
| `SP+0` | a local | → `ROM00:5669` | — |
| `SP+2` | low byte of `(ram:D467)` | → `ROM00:5669` | — |
| `SP+4` | **0** | **`ram:E48D`**, the session mode | — |
| `SP+6` | the encoded line speed — the Linespeed field's table entry (`ram:D102 + index`), or the selected mode record's default when Linespeed holds its `FFh` sentinel | → `ROM00:5669` | — |
| `SP+8` | the constant **60** | → `ROM00:5669` | — |
| `SP+10` | `ram:ECAB` | `E6D0`, max 8 | `+0` |
| `SP+12` | `ram:D120` (a zero byte) | `E6E8`, max 6 | `+8`, always blank |
| `SP+14` | `ram:EC8E` | `E6EF`, max 8 | `+18` **workstation id** |
| `SP+16` | `ram:EC99` | `E6C4`, max 8 | `+26` |
| `SP+18` | `ram:ECA2` | `E6D9`, max 8 | `+34` |

The mode at `SP+4` is **0** here, which independently confirms the slot
arithmetic: `ram:E48D` measures 0 on the Load/Run path in every emulator run.

`C-INIT-COMMS` transmits nothing itself. It stores the session mode and
**latches five identity strings** that every later `C-COMMAND` sends. The
constant 60 at `SP+8` is **SUSPECTED** to be a timeout in seconds; nothing
confirms it.

#### Where the identity strings come from

`ram:EC97` is the V24 Log-on form's backing object. Its layout is a byte for
each of the two choice fields followed by four fixed 9-byte string fields:

| Offset | Address | Size | Form field |
|---|---|---|---|
| `+0` | `EC97` | 1 | Mode |
| `+1` | `EC98` | 1 | Linespeed |
| `+2` | `EC99` | 9 | *(string 1)* |
| `+11` | `ECA2` | 9 | *(string 2)* |
| `+20` | `ECAB` | 9 | *(string 3)* |
| `+29` | `ECB4` | 9 | *(string 4)* |

The form's field descriptors are at `ROM01:78E1`, four bytes each as
`{u16 index; u16 label_ptr}`, and they run in display order: Mode,
Linespeed, User id, Password, Group id, Telephone number.

**LIKELY, on the strength of the layout rather than a direct proof:** the
four string fields sit in the same order as the form displays them, so

| Form field | Buffer | Latched into | Record field |
|---|---|---|---|
| User id | `EC99` | `E6C4` | `+26` |
| Password | `ECA2` | `E6D9` | `+34` |
| Group id | `ECAB` | `E6D0` | `+0` |
| Telephone number | `ECB4` | — | *not sent* |

The stride is uniform at 9 bytes and the offsets (`+2`, `+11`, `+20`, `+29`)
are exactly regular, so a different ordering would have to be a coincidence.
It is still an inference: no table in either ROM pairs a field index with its
buffer — the form editor computes the address — so **the confirming
experiment is to type a distinct value into each of the four fields and read
back `E6C4`, `E6D9` and `E6D0`.**

Telephone is not passed to `C-INIT-COMMS` because it goes to the **connect
command** instead, and which connect command runs is itself table-driven.
`ram:D108` (from `micron2.bin` offset `0x7C52`) holds four 6-byte link-method
records, selected by the Mode field:

| Method | Type | Connect command | Baud | Number buffer |
|---|---|---|---|---|
| `LOCAL LINK` | 4 | `EE10` `C-DIAL` | `0Eh` = 9600 | `ECB4` |
| `MODEM A/ANS` | 6 | `EE04` `C-ANSWER` | `07h` = 1200 | — |
| `MODEM A/DIAL` | 6 | `EE10` `C-DIAL` | `07h` = 1200 | `ECB4` |
| `MODEM MAN/D` | 6 | `EE28` `C-MANUAL` | `07h` = 1200 | — |

`ROM01:131D`–`1330` pushes the record's number-buffer field and calls the
record's connect command indirectly through `ram:D828`:

```text
ROM01:131D  LD   HL,(0D467h)   ; the selected record
ROM01:1320  LD   DE,4 / ADD HL,DE
ROM01:1324  LD   E,(HL) / INC HL / LD D,(HL) / PUSH DE   ; record +4, the number
ROM01:1328  LD   HL,(0D467h) / INC HL
ROM01:132C  LD   E,(HL) / INC HL / LD D,(HL) / EX DE,HL  ; record +1, the command
ROM01:1330  CALL 0D828h        ; indirect call
```

**Correction.** An earlier note here said nothing in either ROM calls
`C-DIAL`, `C-ANSWER` or `C-MANUAL`. That was drawn from a scan for the direct
opcodes `CD 10 EE` and friends, which finds nothing because the call is
**indirect**. All three are reachable, and on `LOCAL LINK` — the IR path —
the connect command is `C-DIAL`, taking `ECB4` as its argument.

**Record field `+8` is always blank, and now we know why.** `ram:D120` is not
a credential buffer at all: it is the byte immediately after the four 6-byte
link-method records at `ram:D108` (`D108 + 4 x 6 = D120`), i.e. the table's
terminator. **It has exactly one reference in either ROM** — the
`C-INIT-COMMS` push at `ROM01:12B9` — and **nothing anywhere writes it**. So
the pointer passed for this slot addresses a zero byte, the bounded copy into
`E6E8` yields an empty string, and record `+8` is empty in every trace.

Treat it as a vestigial slot. A host should expect six bytes of nothing
there, and should not read meaning into it.

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

**This is a debugging escape hatch, not part of a session.** Nothing in
either ROM sets `E48D = 2`: its only writer is the session initialiser
`EE24`, which no image calls. Both demonstrated sequences on this page —
program download and record upload — run with the mode at **0**, with the
transition table validating every command. Use mode 2 only to reach a
command out of order deliberately, and expect the host to be told nothing
about it.

### Why a command blocks

Every command wrapper has the same shape: call `SessionStartDataMode`, treat
a **zero** result as *proceed*, and only then do the work.

```text
ROM00:5473  CALL 452Dh       ; SessionStartDataMode(C_ABORT)
ROM00:547A  LD   A,H / OR L
ROM00:547C  JP   NZ,54E1h    ; non-zero -> exit
ROM00:547F  CALL 593Ah       ; zero -> do the work
```

(Note the polarity: a rejected transition returns *non-zero*, and mode 2
returns *zero* — so suppressing validation makes every command proceed.)

`593A` reaches `SessionTxRunState65`, which prepares a frame header, sets the
session parameters with wire state `0x65`, sends the frame through service 33
and then waits in `SessionRxByteLoop`.

So these are not local calls that happen to block — **they are link
transactions**. The routine transmits and waits for the host to answer. A
call made with no peer attached cannot return, and that is the protocol
working, not a fault.

The practical consequence: exercising the API needs a responding peer, which
is exactly what a Commstar server is. `micronic.peer.CommstarPeer` is that
peer, and every sequence on this page runs against it.

In the original bare-COM test the link transmit counter never fired, so the
call blocked somewhere between entering `SessionTxRunState65` and reaching
the link driver — because no session had been opened. Opening one with
`C-INIT-COMMS` first, as the sequences above do, removes the problem.

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

* The full result vocabulary. `0` and `8` are success and are the only two
  values a caller must handle to complete a transfer. `5` (`C-COMMAND` got
  `NO` or `DM`) and `6` (`Invalid reply`) are decoded here; `4` and `9` are
  seen on error paths and are not. `ROM00:4E4E` gives explicit arms to
  `0`, `4`, `6`, `8` and `9` only, everything else falling to a
  `Line failure`.
* What the `C-INIT-COMMS` slots `SP+0`, `SP+2` and `SP+6` mean beyond where
  they are stored, and whether the constant 60 at `SP+8` is a timeout.
* Whether a real Commstar application used these entry points, or reached the
  same routines another way. Eleven of the twenty have no caller anywhere in
  ROM00, ROM01 or the dumped RAM — including every transmit primitive — which
  is the evidence for an application-facing API, but no historical
  application has been examined.

For the firmware evidence behind this page — the ROM source table, the
per-slot derivation, and the measurements — see
[RE notes: Commstar evidence](../re-notes/commstar-evidence.md) and
[Protocol reference: Commstar](../protocol/commstar.md#what-selects-the-operation).
