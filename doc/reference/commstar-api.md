# Commstar application API

**Stability: Provisional.** The entry points and the calling convention are
verified in the emulator; the argument and result contract of individual
operations is not established.

A loaded COM or DIP program can drive the Commstar session directly. The
firmware publishes twenty fixed entry points in the transfer-vector table at
`ram:EE00-EE4F`.

**Start here if you are implementing a host.** The two sequences that are
demonstrated end to end are
[receiving a program](#receiving-a-program-the-whole-sequence) and
[uploading a file of records](#uploading-a-file-of-records) followed by
[ending the session cleanly](#ending-a-session-cleanly). Both run with the
session mode at **0**.

## Entry points

Each entry occupies four bytes at a fixed address in battery-backed RAM.
Call it like an ordinary subroutine; see the calling convention below.

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

**Each command appears exactly once.** Five slots dispatch no protocol
command: `EE24` initialises the session, `EE30`/`EE48` are message-box helpers,
and `EE38`/`EE4C` are raw transfer primitives that never call
`Session_StartDataMode`. The two commands with no entry point are `C-RX-CMD`
(6) and `C-TX-REPLY` (7).

`EE24` is not a protocol command. It clears session variables, sets
`ram:E48D = 2`, and displays `Comms in progress`. It does not return — treat
it as a session *runner* whose contract is not yet established.

> Derivation and byte-level evidence: see
> [`re-notes/commstar-api-evidence.md#entry-points`](../re-notes/commstar-api-evidence.md#entry-points).

## Calling convention

* **Arguments** are pushed on the stack; the caller removes them.
* **The result is returned in `HL`**, and the firmware keeps it in
  `ram:D0FE` as the session's last-result cell.
* **Results are sequenced.** A multi-step exchange is driven by testing `D0FE`
  between calls — `0` continue, `8` last block (which still carries data).
  There is no separate "run" or "get status" entry point.

Example — the firmware's own `C-RX-BLK` call at `ROM01:141E`:

```text
LD   HL,0D39Dh   ; argument
PUSH HL
CALL 0EE2Ch      ; C-RX-BLK
POP  DE          ; caller cleans up
LD   (0D0FEh),HL ; result in HL -> D0FE
```

!!! warning "Two comparison helpers, opposite conventions"
    Both are byte-verified in `ram`:

    * **`ram:E04B` is `==`.** Equal → `HL = 1`, **NZ**. Different → `HL = 0`, **Z**.
    * **`ram:E05A` is `!=`.** Equal → `HL = 0`, **Z**. Different → `HL = 1`, **NZ**.

> Derivation and correction history: see
> [`re-notes/commstar-api-evidence.md#calling-convention`](../re-notes/commstar-api-evidence.md#calling-convention).

## Every buffer must live in unbanked RAM

**A pointer you pass to any entry point must address the fixed upper 32K
(`0x8000`-`0xFFFF`).** A buffer in the caller's own page — the space a CP/M-style
COM has above its code — is invisible to the routine.

The `RST 10h` banked-call mechanism saves and restores the caller's bank, but
the lower 32K holds ROM00 for the duration of the call. A driver COM must
therefore find space in the upper 32K not already in use. The loader ceiling
`ram:D081` (set at `ROM00:7052`) marks the top of what a loaded program may
occupy. See [RE notes: unbanked RAM map](../re-notes/unbanked-ram-map.md)
for what is occupied and what is safe.

> ROM listings, bank-switch mechanics and harness-overwrite history: see
> [`re-notes/commstar-api-evidence.md#every-buffer-must-live-in-unbanked-ram`](../re-notes/commstar-api-evidence.md#every-buffer-must-live-in-unbanked-ram).

## Uploading a file of records

Both `C-BEGIN-FILE` and `C-TX-REC` take a **pointer** to a counted buffer
(caller `SP+0`):

```text
buffer:  [u8 count][bytes ... count of them]
```

`C-BEGIN-FILE` names the file, `C-TX-REC` supplies a record, `C-END-FILE`
closes it, `C-END-TX` flushes. What reaches the host is one object:

```text
06 4d 59 46 49 4c 45  1e  53 43 41 4e ... 54  1c
^^ ^^^^^^^^^^^^^^^^^  ^^  ^^^^^^^^^^^^^^^^^  ^^
 |  "MYFILE"          |   "SCAN:0042:WIDGET"  |
 count, from          |   record payload     C-END-FILE's
 C-BEGIN-FILE         C-TX-REC's marker      terminator
```

Repeated `C-TX-REC` calls **append**, so the general form is:

```text
[u8 namelen][name]  (1Eh [record])*  1Ch
```

**LIKELY: `1Eh` is RS (record separator) and `1Ch` is FS (file separator).**
Only those two appear; `1Dh`/`1Fh` are never sent. The name is sent with its
count byte, the record is not. The two marker bytes come from `C-TX-REC`
(`1Eh`) and `C-END-FILE` (`1Ch`).

> ROM sites, regression name and null-pointer failure history: see
> [`re-notes/commstar-api-evidence.md#uploading-a-file-of-records`](../re-notes/commstar-api-evidence.md#uploading-a-file-of-records).

## Sending and receiving blocks

A **block** is a program; a **record** is data. Both use the counted-buffer
format in memory but differ on the wire.

**Send a block** — `C-TX-BLK`, `ram:EE40`:

```text
buffer:  [u8 count][count bytes]        ; count 0..255
PUSH buffer / CALL 0EE40h / POP DE      ; HL = result
```

`C-TX-BLK` issues the beginning of transmission itself on its first call; no
separate bracket command is needed. `C-END-TX` flushes the tail.

**Receive a block** — `C-RX-BLK`, `ram:EE2C`:

```text
PUSH buffer / CALL 0EE2Ch / POP DE      ; buffer must be >= 129 bytes
```

On return `buffer[0]` is the count received and `buffer[1..count]` the data.
`HL` is the status: `0` continue, **`8` end of data** — the firmware displays
`Program received` — and `4`/`9`/other are errors. Loop until `8`.

The **129-byte minimum** is required: a block is at most 128 data bytes plus
the count byte. `C-TX-BLK` will send up to 255 bytes in one call, resegmented
into 128-byte wire frames underneath.

**A host must never send more than 126 bytes in one object.** The handheld
asks for 128 and then cannot take it. Serving the same image in 126-byte
blocks completes; in 127-byte blocks every object is dropped, the handheld
re-requests, and the session ends `Abort pending` / `Session aborted` with
`C-RX-BLK` returning 4. Treat **126 as a measured limit** — reproduced by
regression, not derived from the RX frame budget.

**The block path emits no separator bytes.** Records are delimited by `1Eh`/`1Ch`;
blocks are framed by the transport length field, so raw binary needs no
in-band markers.

> Call-chain proof and envelope-budget discussion: see
> [`re-notes/commstar-api-evidence.md#sending-and-receiving-blocks`](../re-notes/commstar-api-evidence.md#sending-and-receiving-blocks).

### Which path for binary data?

**The record path is not 8-bit clean.** A record whose payload contains `1Eh`
or `1Ch` puts a byte on the wire indistinguishable from a separator. There is
no quoting.

The block path has no in-band markers, so it is 8-bit clean.

**Send binary data files as blocks.** The firmware will display `Sending prog`
and the session will run in `READY-TX-PROG` rather than `READY-TX-DATA`, but
the bytes arrive intact. The handheld never parses separators itself — they
exist so the host can segment the stream.

> Display-string provenance: see
> [`re-notes/commstar-api-evidence.md#which-path-for-binary-data`](../re-notes/commstar-api-evidence.md#which-path-for-binary-data).

## Receiving a program: the whole sequence

**CONFIRMED end to end.** `micronic.peer.ProgramDownloadPolicy` is the host
half:

```text
CALL 0EE20h   ; C-INIT-COMMS   ten args; slot 2 = link type 4, slot 4 = mode
CALL 0EE10h   ; C-DIAL         -> CONNECTED   (wire 0062 on an IR link)
CALL 0EE0Ch   ; C-COMMAND      index 3 "LOAD" -> READY-RX-PROG
loop:
CALL 0EE2Ch   ; C-RX-BLK       -> 0 keep going, 8 the last block
```

On the wire that is `LINK-INIT` (`0000`), `LINK-CONFIG` (`0006`), `CONNECT-DIRECT` (`0062`), `BEGIN-TX` (`0064`), `BLOCK-OUT` (`0045`), then one `BLOCK-IN` (`0044`)
per block. What the host does at each point:

| Handheld sends | Host answers |
|---|---|
| `LINK-INIT` (`0000`), `LINK-CONFIG` (`0006`), `CONNECT-DIRECT` (`0062`), `BEGIN-TX` (`0064`) | a control ack (single `00` payload byte) |
| `BLOCK-OUT` (`0045`) with a 54-byte object | a control ack; the **command record** — operation name at object `+14`, program name at `+42` |
| `BLOCK-IN` (`0044`), `size = 00FFh` | the command's **reply**: an object holding `OK`, marker 1 |
| `BLOCK-IN` (`0044`), `size = 0080h` | the next `<= 126` bytes of the image, marker 0, and marker 1 on the last |

**The two `BLOCK-IN` shapes are distinguishable by order** (the first after a
command is the reply, every later one is a block) and corroborated by the
`size` field. **Marker 1 is what ends the stream** — it is required on the
reply and on the last data object; `C-RX-BLK` returns 8 only on marker 1.

Measured: a 300-byte image in 126-byte blocks is three blocks of 126, 126 and
48; `C-RX-BLK` returns 0, 0, 8; the third call carries 48 bytes *and* the
end-of-data status; the 300 bytes reassemble by concatenation.

> ROM call sites and regression provenance: see
> [`re-notes/commstar-api-evidence.md#receiving-a-program-the-whole-sequence`](../re-notes/commstar-api-evidence.md#receiving-a-program-the-whole-sequence).

## Ending a session cleanly

`C-END-TX` takes a 16-bit argument at the same last-pushed slot as
`C-BEGIN-FILE` and `C-TX-REC`. Which disposition it takes is decided by the
mode gate at `ram:E48D`:

* **mode 0 and mode 2** — reads the caller's argument and sends it via wire
  state `END-TX` (`0x65`); on `OK` displays `Data transmitted` and commits `ram:E48C`.
* **mode 1** — takes the clean completion without the caller's argument,
  displaying `Data transmitted` and committing `ram:E48C` directly.

Both dispositions end cleanly when the session is in a legal state. The valid
states for `C-END-TX` are `READY-TX-DATA`, `READY-TX-PROG`, `DATA-SET-TX` and
`BLOCK-TX`. `C-COMMAND` index 2 `SEND` reaches `READY-TX-DATA` directly.

**Valid mode-0 teardown (CONFIRMED):**

```text
CALL 0EE20h   ; C-INIT-COMMS   -> DISCONNECTED   (1)
CALL 0EE10h   ; C-DIAL         -> CONNECTED      (2)
CALL 0EE0Ch   ; C-COMMAND, index 2 "SEND" -> READY-TX-DATA (5)
CALL 0EE08h   ; C-BEGIN-FILE   -> RECORD-TX      (9)
CALL 0EE44h   ; C-TX-REC       -> RECORD-TX      (9)
CALL 0EE18h   ; C-END-FILE     -> DATA-SET-TX   (10)
CALL 0EE1Ch   ; C-END-TX       -> CONNECTED      (2)
```

Every step returns 0, the session-state sequence
`DISCONNECTED → CONNECTED → READY-TX-DATA → RECORD-TX → RECORD-TX →
DATA-SET-TX → CONNECTED` (indices `1 2 5 9 9 10 2`) is read from
`g_bSessionState` (`ram:E22D`), and the host receives `05 "STOCK" 1e "REC-ONE" 1c`.
It works with mode 0 and mode 1.

With `E48D = 1`, `C-COMMAND` and `C-SHUT-DOWN` advance the handheld's state
without transmitting — mode 1 buys a clean teardown at the price of the host
never learning what the handheld is doing. **Mode 0 is what a real session
should use.**

> Disassembly and correction history: see
> [`re-notes/commstar-api-evidence.md#ending-a-session-cleanly`](../re-notes/commstar-api-evidence.md#ending-a-session-cleanly).

## Argument reference

Every entry point's argument slots, swept from the ROM. A wrapper reads an
argument with `LD HL,off / ADD HL,SP`, so the caller's slot is `off − 0Ch − depth`
where `depth` is how far `SP` has moved since the prologue.

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

`C-END-TX` takes one argument; `C-END-FILE` takes none.

> Sweep algorithm and swallowed-extent correction: see
> [`re-notes/commstar-api-evidence.md#argument-reference`](../re-notes/commstar-api-evidence.md#argument-reference).

## The command record

`C-COMMAND` assembles a **54-byte record at `ram:E492`** and transmits it whole
(wire state `BLOCK-OUT` (`0x45`)). The canonical field layout is defined in
[Protocol: Commstar transport](../protocol/commstar.md#state-45-object-layout):

| Offset | Size | Field |
|---|---|---|
| `+0` | 8 | identity |
| `+8` | 6 | identity (always blank in traces) |
| `+14` | 4 | **operation name** — from `C-COMMAND`'s first argument |
| `+18` | 8 | **workstation id** — right-justified, space-padded |
| `+26` | 8 | identity |
| `+34` | 8 | identity |
| `+42` | 12 | **per-command parameter** — from `C-COMMAND` `SP+2`, left-justified, NUL-padded |

`C-COMMAND`'s first argument selects both the operation name sent at `+14`
and the session state entered on success.

> Assembly and trace corroboration: see
> [`re-notes/commstar-api-evidence.md#the-command-record`](../re-notes/commstar-api-evidence.md#the-command-record).

### The command's reply, and `C-COMMAND`'s third argument

`C-COMMAND`'s `SP+4` is a **buffer the host's answer is read into**.

```text
reply:  [u8 count][count bytes]        ; count up to 255
```

The firmware compares the first two bytes against `{OK, NO, DM}`:

| Reply | `C-COMMAND` result | Effect |
|---|---|---|
| `OK` | 0 | target state is committed |
| `NO` | 5 | back to `CONNECTED` |
| `DM` | 5 | back to `CONNECTED` |
| anything else | 6 | error `0x1F75` (8053), `Invalid reply` |

The firmware never inspects bytes after the first two. A host must answer with
**marker 1**; a marker-0 reply is treated as no reply at all.

> Byte dump and call-site observations: see
> [`re-notes/commstar-api-evidence.md#the-commands-reply-and-c-commands-third-argument`](../re-notes/commstar-api-evidence.md#the-commands-reply-and-c-commands-third-argument).

## `C-INIT-COMMS`

Ten 16-bit argument slots. The firmware pushes exactly ten words (`20` bytes).

| Slot | What the firmware passes | Destination | Record field |
|---|---|---|---|
| `SP+0` | a local | → `ROM00:5669` | — |
| `SP+2` | low byte of `(ram:D467)` | → `ROM00:5669` | — |
| `SP+4` | **0** | **`ram:E48D`**, the session mode | — |
| `SP+6` | encoded line speed | → `ROM00:5669` | — |
| `SP+8` | constant **60** | → `ROM00:5669` | — |
| `SP+10` | `ram:ECAB` | `E6D0`, max 8 | `+0` |
| `SP+12` | `ram:D120` (zero byte) | `E6E8`, max 6 | `+8`, always blank |
| `SP+14` | `ram:EC8E` | `E6EF`, max 8 | `+18` **workstation id** |
| `SP+16` | `ram:EC99` | `E6C4`, max 8 | `+26` |
| `SP+18` | `ram:ECA2` | `E6D9`, max 8 | `+34` |

`C-INIT-COMMS` transmits nothing itself. It stores the session mode and
**latches five identity strings** that every later `C-COMMAND` sends. The
constant 60 at `SP+8` is **SUSPECTED** to be a timeout in seconds.

> Call-site proof and emulator corroboration: see
> [`re-notes/commstar-api-evidence.md#c-init-comms`](../re-notes/commstar-api-evidence.md#c-init-comms).

### Where the identity strings come from

`ram:EC97` backs the V24 Log-on form. The five identity slots latched by
`C-INIT-COMMS` and the connect method are, as needed by a caller:

| Latched field | Source buffer | Notes |
|---|---|---|
| `+0` (8 bytes) | `ECAB` (Group id) | |
| `+8` (6 bytes) | `D120` (always blank — table terminator) | treat as vestigial; host should expect zeroes |
| `+18` (8 bytes) | `EC8E` (Workstation id) | |
| `+26` (8 bytes) | `EC99` (User id) | LIKELY — layout inference, see evidence |
| `+34` (8 bytes) | `ECA2` (Password) | LIKELY — layout inference, see evidence |

The V24 Log-on form's own field labels (`micron2.bin` ROM01:7BA0-7BC8) are
`User id`, `Password`, `Group id`, `Telephone number` — so `EC99`/`ECA2`/`ECAB`
are the form's User/Password/Group buffers, and *Telephone number* is a
**separate** buffer (`ram:ECB4`). `+18`/`EC8E` is therefore the **workstation
id**, not the telephone: the cold-boot prompt is "Enter the Workstation", and a
dynamic run puts the entered serial there. The earlier "Telephone / workstation
id" wording conflated the two and has been dropped.

`+8`/`ram:D120` is a single zero byte immediately before the link-method
callback table at `ram:D121`; nothing in the image writes it, so `+8` is
always blank (vestigial).

Telephone (`ECB4`) goes to the **connect command**, not `C-INIT-COMMS`. Which
connect command runs is table-driven from `ram:D108` by the Mode field:

| Method | Type | Connect command | Baud | Number buffer |
|---|---|---|---|---|
| `LOCAL LINK` | 4 | `EE10` `C-DIAL` | `0Eh` = 9600 | `ECB4` |
| `MODEM A/ANS` | 6 | `EE04` `C-ANSWER` | `07h` = 1200 | — |
| `MODEM A/DIAL` | 6 | `EE10` `C-DIAL` | `07h` = 1200 | `ECB4` |
| `MODEM MAN/D` | 6 | `EE28` `C-MANUAL` | `07h` = 1200 | — |

An IR link is type 4 and uses `C-DIAL` with `ECB4` as its number buffer.

**CONFIRMED dynamically (2026-09-20).** With `MICRONIC_LOGON_POKE=1` the
harness seeds `ECAB`/`EC99`/`ECA2` just before the V24 Log-on screen is
accepted (`boot_hw.py`, logon step), then runs the synthetic Load/Run. The
resulting `ram:E492` record carried `+0="GRP1"`, `+26="USER1"`, `+34="PASS1"`,
`+18="12345678"` (the banner serial) and `+8` blank — so the cell → offset
mapping is now **proven**, not only inferred. The `Group id`/`User id`/
`Password` names are the ROM's own labels (`g_acLogonGroupId`,
`g_acLogonUserId`, `g_acLogonPassword`), so they are **CONFIRMED**; the mapping
does not depend on interpretation.

> Form-layout derivation, proposed experiment and correction history: see
> [`re-notes/commstar-api-evidence.md#where-the-identity-strings-come-from`](../re-notes/commstar-api-evidence.md#where-the-identity-strings-come-from).

## Suppressing validation

Set `ram:E48D = 2` before issuing commands to bypass the transition table. A
command then runs regardless of current state. This is a debugging escape
hatch; no ROM image sets `E48D = 2` except the unused session initialiser
`EE24`. Both demonstrated sequences on this page run with mode **0**.

> Experiment and reachability proof: see
> [`re-notes/commstar-api-evidence.md#suppressing-validation`](../re-notes/commstar-api-evidence.md#suppressing-validation).

## Why a command blocks

Every command wrapper calls `Session_StartDataMode` and treats zero as
*proceed*; only then does it transmit and wait in `Session_RxByteLoop`. These
are link transactions — the routine transmits and waits for the host to
answer. A call with no peer attached cannot return. A session must be opened
with `C-INIT-COMMS` first, and a responding peer (`micronic.peer.CommstarPeer`
in the emulator) must pump the link.

> Wrapper listing and bare-COM harness incident: see
> [`re-notes/commstar-api-evidence.md#why-a-command-blocks`](../re-notes/commstar-api-evidence.md#why-a-command-blocks).

## What this does not tell you

* The full result vocabulary. `0` and `8` are success; `5` (`NO`/`DM`) and `6`
  (`Invalid reply`) are decoded here; `4` and `9` appear on error paths and are
  not fully decoded. Everything else falls to `Line failure`.
* What the `C-INIT-COMMS` slots `SP+0`, `SP+2` and `SP+6` mean beyond where
  they are stored, and whether the constant 60 at `SP+8` is a timeout.
* Whether a real Commstar application used these entry points. Eleven of the
  twenty have no caller in ROM00, ROM01 or dumped live RAM — including every
  transmit primitive — which is the evidence for an application-facing API, but
  no historical application has been examined.

For the firmware evidence behind this page — the ROM source table, the
per-slot derivation, and the measurements — see
[RE notes: Commstar API evidence](../re-notes/commstar-api-evidence.md).
