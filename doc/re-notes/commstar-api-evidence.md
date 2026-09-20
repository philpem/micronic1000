# Commstar API evidence

This page is the **firmware evidence record** for the
[Commstar application API](../reference/commstar-api.md). It carries ROM
addresses, emulator provenance, correction history and byte-level listings that
were formerly interleaved with the API contract. The normative contract is in
the reference page; this page is the proof behind it.

## Entry points

In the static image `ram:EE00-EE4F` holds twenty `LD HL,1; RET` no-op slots
(4 bytes each, `21 01 00 C9`), **not** `RST 10h` thunks. The computed-call
xrefs (e.g. `ram:EE04 -> ROM00:48BF`) describe intended routing, and the ROM
source table at `ROM00:7DFA` (20 words, slot *i* at `7DFA+2*i`) supplies those
targets.

**CORRECTED 2026-09-19 (CONFIRMED, byte-verified + emulator):** the ROM
populates the arena at boot by bulk copy (writer PCs `D6D6` ×80 and
`D736`/`D73B`/`D73E`/`D740` ×20 each) installing the no-op stubs — earlier
static scan missed the bulk copy (no per-address xref; source `ROM00:7DFA`
20 words copied en bloc). Only one ROM instruction references the arena
(`ROM01:11A4` calls `0xEE00`).

**`D7` (`RST 10h` thunk) patch RESOLVED/WITNESSED 2026-09-19 (CONFIRMED,
emulator `analysis/boot_hw.py`):** crafted COM writes thunk `D7 00 BF 48`
into `EE00`-`EE03` (`LD HL,EE00; LD (HL),D7; INC HL; LD (HL),00; INC HL;
LD (HL),BF; INC HL; LD (HL),48; LD A,A5; LD (0200),A; RET`) via `--upload`
with `--upload-marker 0200:A5` and `--watch-mem EE00:EE4F` — `execution entered
bank 2 at 0100`, `marker 0200=A5 observed`, `upload_status=succeeded`; arena
totals **164 writes** with `D6D6×80 D736×20 D73B×20 D73E×20 D740×20` (boot bulk
copy) **plus `0105×1 0108×1 010B×1 010E×1`** (COM's four stores into
`EE00`-`EE03`) (CONFIRMED). Earlier `0100:21` marker (COM's own `LD HL`
opcode `21h`) caused early return before COM execution — corrected to
`0200:A5`; `--watch-mem` **was** active (CORRECTION of the previous "watch not
active" conclusion). DIP type-0 `dest=EE00` (no range check at
`ROM01:0ED1`→`D36A`) or COM `LD (EE00),A`/`LDIR` at `0x0100` (`ROM01:0D3B`)
(CONFIRMED); type-1 only as `{D7,bank,addr}` stubs. Comment at `ram:EE00`.

**Each command appears exactly once.** The "command dispatched" column is
derived, not assumed: `Session_StartDataMode` (`ROM00:452D`) has fifteen call
sites in ROM00 and each pushes a distinct literal index, so the mapping from
slot to command is one-to-one and complete.

**Correction.** An earlier version of the table listed `C_ABORT` three times
and `C-SHUT-DOWN` three times, and said the duplicates "have not been told
apart". There are no duplicates — those labels were wrong. Five slots dispatch
no protocol command at all: `EE24` `46E9` initialises the session; `EE30`
`4D29` and `EE48` `4D4F` are message-box helpers calling
`Session_MessageBox` with `"   not available"` / `"   in Workstation"` (differ
only in buffer pair `E278`/`E279` vs `E288`/`E289`); `EE38` `5444` forwards
three arguments to `ROM00:5915 -> 62C7` (wire states `0043` then `0044`,
solicits a data block); `EE4C` `5428` forwards two arguments to
`ROM00:58F9 -> 63CA -> 612A` (wire state `0045`, sends a data block). The last
two never call `Session_StartDataMode`.

The two commands with no entry point are `C-RX-CMD` (6) and `C-TX-REPLY` (7).
Neither has a stub slot and no routine in either ROM dispatches them.

`EE24` initialises the session: it clears a dozen session variables, sets
`ram:E48D = 2`, and displays `Comms in progress`. It does not return.

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

Results are sequenced. The same site guards its call on the previous result,
and the sense is "keep going until 8":

```text
ROM01:140E  LD   HL,(0D0FEh)
ROM01:1411  LD   DE,0008h
ROM01:1414  CALL 0E04Bh      ; equality test: returns NZ when equal
ROM01:1417  JP   NZ,14BAh    ; D0FE == 8 already -> skip C-RX-BLK
```

So a multi-step exchange is driven by testing `D0FE` between calls — that is
the status mechanism, rather than a separate poll entry point. `0` and `8` are
the two values treated as success; `8` is what the *last* block returns, and
the same site still consumes that block's bytes (`ROM01:142A`–`1433` branches
to the store at `143A` when the result is 8), so **status 8 can carry data**.

**Correction.** An earlier revision read the guard backwards and said
`C-RX-BLK` "is only issued when `D0FE` already holds 8". `ram:E04B` sets the
zero flag when its operands *differ*, so `JP NZ` means *equal*: the loop stops
at 8, it does not start there.

**Two comparison helpers, opposite conventions.** Byte-verified in `ram`:

* **`ram:E04B` is `==`.** Equal → `HL = 1`, **NZ**. Different → `HL = 0`, **Z**.
* **`ram:E05A` is `!=`.** Equal → `HL = 0`, **Z**. Different → `HL = 1`, **NZ**.

They appear within nine instructions of each other at `ROM01:1414` and
`ROM01:1430`, testing the same cell against the same constant, and the two
branch senses are opposite. Every polarity error corrected on the reference
page started here.

There is no separate "run" or "get status" entry point.

## Every buffer must live in unbanked RAM

**CONFIRMED.** The call mechanism explains the rule. At runtime each entry
point would be a four-byte thunk `RST 10h ; db bank ; dw target`, and `RST 10h`
(`ROM00:0010`) compares the target bank against the current one:

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

The caller's bank is saved and restored — a `RST 10h` call returns with the
paging exactly as it left it. What does *not* happen is the caller's page
being mapped **while the callee runs**: the lower 32K holds ROM00 for the
duration.

The firmware's own practice confirms it — every buffer it passes is unbanked:

| Call site | Entry point | Buffer |
|---|---|---|
| `ROM01:141A` | `C-RX-BLK` | `ram:D39D` |
| `ROM01:1343` | `C-COMMAND` | `ram:D422` |
| `ROM01:12AD`-`12BD` | `C-INIT-COMMS` | `ram:ECAB`, `EC99`, `ECA2`, `EC8E`, `D120` |

Not one is below `0x8000`.

**Thunk-patch and harness history.** Static image remains `LD HL,1; RET`
slots. The arena is a stub farm. `D7` thunk-patch was witnessed via
`analysis/boot_hw.py` with `--upload --upload-marker 0200:A5 --watch-mem
EE00:EE4F` (164 writes). **(i) DIP type-0:** destination from descriptor
bytes [4:5] (`ROM01:0ED1` → `D36A`) with no range check. **(ii) COM:** loaded
at `0x0100` (`ROM01:0D3B`) with full RAM access, now witnessed overwriting
`EE00`-`EE03`. Type-1 blocks only as `{D7,bank,addr}` stubs. The `RST 10h`
shape, when it occurs, is installed by loaded software, not by ROM.

**Buffer-placement bug.** The loader's own limit `ROM00:7052`
(`21 81 D0 / 22 BD E3`) sets `g_pProgramLoadCeiling = ram:D081`, and module B
begins exactly there. Picking an address by guesswork has already caused one
real bug: the emulator harness staged upload chunks at `ram:E5C2` and ran over
live session state. See [RE notes: unbanked RAM map](unbanked-ram-map.md).

## An application-driven session, working — superseded

A loaded COM held a complete Commstar session via this sequence:

```text
CALL 0EE20h   ; C-INIT-COMMS, mode 0   -> DISCONNECTED
CALL 0EE10h   ; C-DIAL                 -> CONNECTED
LD A,2 / LD (0E48Dh),A                 ; suppress validation
CALL 0EE08h   ; C-BEGIN-FILE
CALL 0EE44h   ; C-TX-REC               <- the handheld sends data
CALL 0EE18h   ; C-END-FILE
```

Observed: ten request/reply exchanges, session state reaching `CONNECTED`,
and three objects sent by the handheld — 9 bytes at state `0006`, then 128
and 72 bytes at state `0045`.

Two harness bugs had to be fixed first: the emulator has to keep the RTC
running while a loaded program executes, or no periodic interrupt fires and the
receive path never runs; and the peer has to be pumped from the same loop.

This sequence is **superseded — do not copy**. The `LD A,2` line was a
workaround for a misreading, not a requirement. It skips the `C-COMMAND` that
tells the host what the handheld is doing, and it leaves the session at
`CONNECTED`, from which `C-END-TX` cannot complete. The correct sequence keeps
mode 0 and issues `C-COMMAND` index 2 `SEND` first. See the reference page's
[Ending a session cleanly](../reference/commstar-api.md#ending-a-session-cleanly).

## Uploading a file of records

**Buffer format and stream grammar** are on the reference page. Additional
evidence:

* Unlike the other entry points, `C-BEGIN-FILE` and `C-TX-REC` read the
  **last** word pushed (caller `SP+0`), not the third down.
* The two marker bytes come from `ROM00:3D9B` calls with literals: `1Eh` at
  `ROM00:5107` inside `C-TX-REC`, `1Ch` at `ROM00:5193` inside `C-END-FILE`.
  `ROM00:3E14` sends `buffer[1..count]` only (name count byte sent, record
  count stripped).
* Regression: `CommstarRecordUploadTest`. Passing a null pointer produced the
  meaningless `c3 03 01` prefix in an earlier attempt: `C-BEGIN-FILE` read
  `mem[0]` (`C3h`) as its name length.

## Sending and receiving blocks

**Send a block** (`C-TX-BLK`, `ram:EE40`): pointer to `[u8 count][count bytes]`
to `ROM00:3E14`, the same counted-buffer walker `C-TX-REC` uses. `C-TX-BLK`
issues state `0064` "begin transmit" itself on its first call; `C-END-TX`
flushes the tail.

**Receive a block** (`C-RX-BLK`, `ram:EE2C`): `PUSH buffer / CALL 0EE2Ch`
requires ≥129 bytes. `ROM00:4FAD` pushes hard-coded maximum `0080h` before
calling `Session_ReadStreamChunk`.

**The 129-byte minimum and the 126-byte host limit.** `C-TX-BLK` will send up
to 255 bytes in one call, resegmented into 128-byte wire frames. On receive,
the `0080h` reaches the wire as the `size` field of the `0044` request. The
**measured** limit is 126: serving a 300-byte image in 126-byte blocks
completes and displays `Program received`; in 127-byte blocks every object is
dropped without acknowledgement. `micronic.peer.MAX_OBJECT_DATA` caps at 126
via `ProgramDownloadPolicy`.

The mechanism is not fully derived. `ROM00:620B` sets the `0044` receive frame
length to `86h` = 134 (`21 86 00 E5` to `Session_SetParams`), and 134 − 8 = 126
is arithmetically consistent with an eight-byte preamble ahead of the object
body at `ram:E5C4`. But the RX frame struct at `ram:E5BA` is 138 bytes with
its data area at `+0Ah`, which would suggest a different budget. **Treat 126
as a measured limit rather than a derived one.**

**The block path emits no separator bytes.** `ROM00:3D9B` has exactly four
call sites: `3E57` and `3F0D` (payload and filename loops), `5107`
(`C-TX-REC`, literal `1Eh`) and `5193` (`C-END-FILE`, literal `1Ch`).
`C-TX-BLK` has no equivalent. `1Dh` GS is never pushed; the single `1Fh` push
(`ROM00:5FD7`) goes to a different routine on the dial path. Records are
variable-length items in one continuous stream needing RS/FS; blocks are
framed by the transport length field.

## Which path for binary data?

"Blocks are programs, records are data" is a statement about framing, not
content. The two labels come only from display strings (`Sending prog` at
`ROM00:6CE8` versus `Sending data` at `6CDB`). Nothing inspects what you hand
it.

The record path is not 8-bit clean (`ROM00:3E14` walks the buffer with no
comparison, escape or stuffing). The block path has no in-band markers and is
8-bit clean, so binary data files should be sent as blocks. The handheld
never parses separators: the only comparisons against `1Eh`/`1Ch` in ROM00 are
at `279B`, `018E` and `27BA`, none in the session code — separators exist so
the host can segment the stream.

## Receiving a program: the whole sequence

**CONFIRMED end to end.** The four-call recipe and host-response table are on
the reference page. Additional evidence:

* The firmware's own Load/Run path uses the same shape: `ROM01:1343` for
  `C-COMMAND`, `ROM01:141E` for `C-RX-BLK`.
* The two `0044` shapes are distinguishable by ROM routine: the first after a
  command is that command's reply (`ROM00:4C3A` calls `3F20` which asks for
  `00FFh` at `ROM00:3F39`); every later one is a block (`ROM00:3D59` asks for
  `0080h`). Order alone suffices for a tracking peer; the size field
  corroborates it.
* Marker 1 is not optional on the reply either: `ROM00:3D59` turns marker-1
  into end-of-stream flag `ram:E44A`, which makes `C-RX-BLK` return 8; and
  the command-reply classifier `ROM00:3FEC` only reaches its `OK`/`NO`/`DM`
  comparison on status 8.
* Regression: `CommstarProgramDownloadTest` in `analysis/test_boot_upload.py`,
  driven by `boot_hw.py --commstar-peer --commstar-serve-program`.

## Ending a session cleanly

`C-END-TX` takes a 16-bit argument at the last-pushed slot. Which disposition
it takes is decided by the mode gate:

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

**Correction.** An earlier revision was headed "why the session cannot end
cleanly" and concluded neither disposition was available. Both end cleanly.

What produced `Abort pending` in that demonstration was the **session state**,
not the disposition:

* with `E48D = 2` the transition table is not consulted, so `C-END-TX`
  proceeded to the argument path at `533E` and sent an argument the test never
  meant to supply;
* with `E48D = 1` the table *is* consulted, and `table[CONNECTED][C-END-TX]`
  is `8Dh` — bit 7 set, illegal, next state `CRASHED` (byte-verified at
  `micron1.bin 0x695B`) — so `Session_StartDataMode` returned non-zero and
  `ROM00:52F8` exited before the completion path.

The fix: be in a state from which `C-END-TX` is legal
(`READY-TX-DATA`, `READY-TX-PROG`, `DATA-SET-TX` or `BLOCK-TX`). `C-COMMAND`
index 2 `SEND` reaches `READY-TX-DATA` without consulting the matrix.

With `E48D = 1`, `C-COMMAND` never transmits: `ROM00:4B40` tests the mode and,
when it is 1, falls through to `4B4F`, which sets the state from `ram:E491`
and returns without building or sending the 54-byte record. `C-SHUT-DOWN`
(`ROM00:4D92`) short-circuits the same way. So mode 1 buys a clean teardown
at the price of the host never learning what the handheld is doing.

Regression: `CommstarCleanTeardownTest`. Valid teardown was confirmed by
reading `g_bSessionState` (`ram:E22D`) as `1 2 5 9 9 10 2`.

## Argument reference

Every entry point's arguments, swept from the ROM by
`analysis/commstar_args.py` and cross-checked against the firmware's own call
sites. A wrapper reads an argument with `LD HL,off / ADD HL,SP`, where `off`
is relative to **SP at that instant** — so argument marshalling, which pushes
as it goes, shifts it. The caller's slot is `off − 0Ch − depth`, `depth`
being how far SP has moved since the routine's `CALL D837` prologue. Reading
`off − 0Ch` alone misplaces any argument fetched with a push outstanding;
`C-RX-BLK` is the case that catches it.

One thing this settles: **`C-END-TX` takes one argument, `C-END-FILE` none.**
This corrects the note committed in `c840242`, which attributed the read at
`ROM00:523F` to `C-END-FILE`. `523F` is inside `C-TX-BLK` (`51EC`–`52A4`);
`C-END-FILE` is `5179`–`51EB` and contains no stack read at all. The earlier
scan used an extent that swallowed the following routine.

## The command record

`C-COMMAND` assembles a **54-byte record at `ram:E492`**:

```text
ROM00:4C11  LD   HL,0036h    ; 54 bytes
ROM00:4C14  PUSH HL
ROM00:4C15  LD   HL,0E492h
ROM00:4C18  PUSH HL
ROM00:4C19  CALL 5880h       ; -> 612A, wire state 45h
```

Fields are copied at `ROM00:4B84`–`4C05` through bounded string copy
`ram:DB89(dst, src, maxlen)`. Destinations are contiguous and their maxima
tile the record exactly:

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
object at wire state `0045`, with `"LOAD"` at object `+14` and the workstation
serial at `+18` — the two fields decoded above, at the offsets this layout
predicts. The remaining fields are blank in those traces, which is consistent:
Load/Run asks the operator for no credentials.

`E48F` holds a pointer into the operation table, set at `ROM00:4B26` from
`E247 + 6 × index` — so **`C-COMMAND`'s first argument selects both the
operation name sent at `+14` and the session state entered on success.** See
the protocol page for the operation table itself.

## The command's reply, and `C-COMMAND`'s third argument

`C-COMMAND`'s `SP+4` is a buffer the host's answer is read into, and it is
not optional. After transmitting the record, `ROM00:4C32` pushes that pointer
and calls `ROM00:3F20`, which solicits a block (`58B8(arg+1, 00FFh, arg)`,
wire state `0044` with `size = 00FFh`) and leaves the answer as a counted
buffer:

```text
reply:  [u8 count][count bytes]        ; count up to 255
```

`ROM00:3F65` compares the first two bytes against a three-entry table copied
to `ram:E22F`, `{char name[2]; u8 code}` at stride 4. Byte-verified at
`micron1.bin` `0x7303`: `4F 4B 00 00 | 4E 4F 00 01 | 44 4D 00 02` — `OK`→0,
`NO`→1, `DM`→2. Firmware's own call site passes `ram:D422` (`ROM01:1343`).
A host that never answers cannot advance the session, and it must send the
answer with marker 1, because `3FEC` only reaches this comparison on read
status 8.

The firmware never inspects bytes after the first two, so `OK` alone is valid;
the traced Load/Run peer sends `OK` followed by four more bytes and the
firmware ignores them.

## `C-INIT-COMMS`

Ten arguments, all 16-bit slots. **CONFIRMED**: the firmware's own call site
`ROM01:12AD`–`1304` pushes exactly ten words and cleans up with
`LD HL,0014h / ADD HL,SP / LD SP,HL` (20 bytes).

The mode at `SP+4` is **0** here, which independently confirms the slot
arithmetic: `ram:E48D` measures 0 on the Load/Run path in every emulator run.

`C-INIT-COMMS` transmits nothing itself. It stores the session mode and
latches five identity strings that every later `C-COMMAND` sends. The constant
60 at `SP+8` is **SUSPECTED** to be a timeout in seconds; nothing confirms it.

Call-site proof and emulator corroboration are as above.

## Where the identity strings come from

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

Form field descriptors at `ROM01:78E1` (4 bytes each as `{u16 index; u16
label_ptr}`) run in display order: Mode, Linespeed, User id, Password, Group
id, Telephone number.

**LIKELY, on the strength of the layout rather than a direct proof:** the four
string fields sit in the same order as the form displays them, so

| Form field | Buffer | Latched into | Record field |
|---|---|---|---|
| User id | `EC99` | `E6C4` | `+26` |
| Password | `ECA2` | `E6D9` | `+34` |
| Group id | `ECAB` | `E6D0` | `+0` |
| Telephone number | `ECB4` | — | *not sent* |

The stride is uniform at 9 bytes and offsets (`+2`, `+11`, `+20`, `+29`) are
exactly regular, so a different ordering would be a coincidence. It is still an
inference: no table pairs a field index with its buffer — the form editor
computes the address — so **the confirming experiment is to type a distinct
value into each field and read back `E6C4`, `E6D9` and `E6D0`.**

Telephone is not passed to `C-INIT-COMMS` because it goes to the connect
command instead. `ram:D108` (from `micron2.bin` offset `0x7C52`) holds four
6-byte link-method records, selected by the Mode field:

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

**Correction.** An earlier note said nothing in either ROM calls `C-DIAL`,
`C-ANSWER` or `C-MANUAL`. That was drawn from a scan for direct opcodes
`CD 10 EE` and friends, which finds nothing because the call is **indirect**.
All three are reachable, and on `LOCAL LINK` (the IR path) the connect
command is `C-DIAL`, taking `ECB4` as its argument.

**Record field `+8` is always blank.** `ram:D120` is not a credential buffer:
it is the byte immediately after the four 6-byte link-method records at
`ram:D108` (`D108 + 4×6 = D120`), i.e. the table's terminator. It has exactly
one reference in either ROM — the `C-INIT-COMMS` push at `ROM01:12B9` — and
nothing anywhere writes it. So the pointer passed for this slot addresses a
zero byte, the bounded copy into `E6E8` yields an empty string, and record
`+8` is empty in every trace. Treat it as a vestigial slot.

## Suppressing validation

Set `ram:E48D = 2` before issuing commands:

```text
3E 02        LD   A,2
32 8D E4     LD   (0E48Dh),A
```

`Session_StartDataMode` then returns without consulting the transition table,
so an operation runs whatever the current state. **CONFIRMED:** with this in
place, `C_ABORT` from `NOT-STARTED` raises no message box and leaves
`ram:E512 = 0`, the early-return marker; the identical call without it raises
the illegal-transition box.

This is a debugging escape hatch. Nothing in either ROM sets `E48D = 2`
except the session initialiser `EE24`, which no image calls. Both demonstrated
sequences on the reference page run with the mode at **0**.

## Why a command blocks

Every command wrapper has the same shape: call `Session_StartDataMode`, treat
zero as *proceed*, non-zero as exit:

```text
ROM00:5473  CALL 452Dh       ; Session_StartDataMode(C_ABORT)
ROM00:547A  LD   A,H / OR L
ROM00:547C  JP   NZ,54E1h    ; non-zero -> exit
ROM00:547F  CALL 593Ah       ; zero -> do the work
```

(Note polarity: rejected transition returns non-zero, mode 2 returns zero.)

`593A` reaches `Session_TxRunState65`, which prepares a frame header, sets the
session parameters with wire state `0x65`, sends the frame through service 33
and then waits in `Session_RxByteLoop`.

So these are link transactions. The routine transmits and waits for the host
to answer. A call with no peer cannot return. `micronic.peer.CommstarPeer` is
that peer. In the original bare-COM test the link transmit counter never
fired, so the call blocked between entering `Session_TxRunState65` and
reaching the link driver — because no session had been opened.

## Worked example — emulator proof

This 16-byte COM initialises the session and proves the call took effect.
It is an emulator proof using the non-returning `EE24` slot, not a recommended
functional API example:

```text
0100  3E AA        LD   A,0AAh
0102  32 00 02     LD   (0200h),A   ; marker: reached the call
0105  CD 24 EE     CALL 0EE24h      ; initialise the session
0108  3E 55        LD   A,055h
010A  32 00 02     LD   (0200h),A   ; would mark a normal return
010D  C3 0D 01     JP   $
```

Running it leaves the mode gate at 2 and its companion cell at `0x37`, where a
control program that does not make the call leaves both at 0 — so the call
reached the firmware. The marker holds `AA`, never `55`. Regression:
`CommstarApplicationApiTest` in `analysis/test_boot_upload.py`.

## What this does not tell you — open limits

* The full result vocabulary (`0`/`8` success; `5`/`6` decoded; `4`/`9` on
  error paths not fully decoded; `ROM00:4E4E` arms `0`, `4`, `6`, `8`, `9`
  only, default → `Line failure`).
* What the `C-INIT-COMMS` slots `SP+0`, `SP+2` and `SP+6` mean beyond where
  they are stored, and whether constant 60 at `SP+8` is a timeout.
* Whether a real Commstar application used these entry points — eleven of the
  twenty have no caller anywhere in ROM00, ROM01 or dumped RAM, including
  every transmit primitive, which is the evidence for an application-facing
  API, but no historical application has been examined.

Full argument: image-search across ROM00, ROM01, upper live RAM and banked RAM
found no caller for those eleven; the transfer-vector table at `ED1C`-`F17F`
is the documented mechanism for loaded code.
