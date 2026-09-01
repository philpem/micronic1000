# Open questions

Single address for every `OPEN` item in the tree. Each entry states the
question, the current evidence, and the observation that would resolve it.
For prioritised work and the session log, see `research/TASKS.md` in the
source tree (not published here).

## Wire and electrical layer

* **IR modulation, bitrate, byte framing, timing, polarity** — No
  connector-facing capture exists. The M1000-facing latch order is known;
  the electrical serialisation downstream of `LINK_TXD`/`LINK_RXD` is not.
  *Resolve:* one synchronised bus capture on `4Dh/4Eh` versus the IR
  photodiode/LED pair, with both directions and the `4Ah/4Bh` latch states.

* **Does the controller-queue sync/trailer exist on the wire?** — The
  synthetic peer adds an uncounted `00` sync and two excluded trailing
  copies of type/sequence; their wire presence is open.
  *Resolve:* same physical capture — compare wire bytes to controller-queue
  bytes.

* **Electrical meanings of `LINK_CTRL`/`LINK_STATUS` bits** — Firmware
  polls `LINK_STATUS` bits 7/4/6 (TX) and 0-3 (RX) and drives `LINK_CTRL`
  bits 0/4/5 plus toggled bit 1. No electrical names are proven.
  *Resolve:* hardware trace correlating latch bits with IR activity and
  the adapter’s response timing.

* **Units and cadence of timeout loops and retry scheduler** — Loop counts
  `0x02DA`, `0x026C`, `0x06F9` and scheduler cells `fdd6`/`fdd8`
  (`32h/14h` and `6/3`) are firmware counts, not wall-clock deadlines.
  Cycle-account the verified loop path and any controller delay.
  *Resolve:* instruction-level accounting at the owner-supplied
  3.579545 MHz clock, plus a measured adapter response.

## Link identity and port selection

* **Which wire-id bit-5 value selects V24 ADAPTOR (top) vs PLINTH (back)?**
  — Firmware does `AND 0x20` and drives `LINK_CTRL` bit 1 via
  `LinkPortSelect`; which polarity maps to which physical connector is
  open.
  *Resolve:* hardware test with two known link ids differing only in bit 5.

* **Where does the EXT STORAGE ADAPTER attach?** — All `C:`+ storage I/O
  runs over the 4-wire byte transport, so it must use one of the two IR
  ports; defaults are `C:=0x73`, `D:=0x72` (both bit 5 = 1). The attachment
  point is not yet adjudicated.
  *Resolve:* owner confirmation or a captured storage transaction that
  identifies its link id and port.

* **Full eight-bit link id vs observable five bits** — Only `id & 1Fh`
  (bits 0-4) is wire-observable via the prelude; bits 5-7 are not.
  Two samples (`0x43`, `0x63`) both have bit 6 set, bit 7 clear — not a
  rule.
  *Resolve:* capture with `fdd4` recorded beside each frame.

* **Meaning of TX `0x7F` at frame offset +4** — `LinkFramePrefixWrite`
  writes `0x7F`; RX requires offset +4 to equal the active link id.
  Server-side meaning of the M1000’s `0x7F` is **SUSPECTED**, not
  confirmed.
  *Resolve:* capture a server-to-handheld frame and compare its offset +4
  to the prelude and `fdd4`.

* **Offset +5 never read by ROM link code** — May be writable by loaded
  code; do not assume unused.
  *Resolve:* inspect loaded-session usage of `+5`.

* **Identity of the two bytes excluded from `LinkBlockRx` `DE`** — On
  success `DE = bytes_read - 2`; bounded traces show they are copies of
  type (`+2`) and sequence (`+3`), but the controller-level reason is
  open.
  *Resolve:* hardware capture that shows whether those bytes exist on the
  wire.

## Frame, sequence, and session grammar

* **Sequence-number lifecycle** — Initial value `1` and per-link slot
  `FE43h + (idd4 & 3Fh)` are known; who advances it, when, and whether
  directions share a counter is open. Observed Mode-1 TX sequence `00`
  then `01` is not a proven increment rule.
  *Resolve:* a multi-frame capture with sequence values logged per link.

* **Complete session command table and payload formats** — No historical
  Commstar command dictionary, RECORD/BLOCK formats, reply envelope, or
  abort/retry/completion transitions are normative. State identifiers
  `61`, `64`, `45`, `44` are observed progression values, not command
  names. Payload grammar for `RECORD`/`BLOCK`/`C-COMMAND` remains open.
  *Resolve:* one synchronised capture of a genuine server login and small
  COM/DIP transfer, with `fdd4` and `E530-E5C8` / `FDE4-FE42` snapshots
  at each send/dispatch/completion.

* <a id="state-45-payload-structure"></a>**State-45 object interior** — The
  object layout is now measured: `LOAD` at object +14, the workstation number
  at +18 (right-justified, space-padded), and the program name at +42
  (left-justified, NUL-padded). See the layout table in
  [Protocol reference](../protocol/commstar.md#state-45-object-layout).
  What remains open is the 34 bytes that are zero in every capture, what
  `arg`=1 selects, and whether `LOAD` is an operation name that other
  Commstar operations replace.
  *Resolve:* the remaining zero runs are sized like the V24 logon fields
  (User id, Password, Group id are 9 bytes each); populate those form fields
  and re-capture to see whether they land in the object. `LOAD` needs a
  second reachable Commstar operation to vary.

* **Wire values versus the named states and commands** — `ROM00:6A4A` names
  16 session states (`NOT-STARTED` … `REPLY-END`) and `ROM00:6B67` names 17
  commands (`C-INIT-COMMS` … `C_ABORT`), but the wire carries `00`, `06`,
  `44`, `45`, `61`, `64`. Neither table has a static xref — the RAM-resident
  session module supplies both indices. Load/Run **is** the Commstar session
  screen (owner-confirmed), so the traced session is a Commstar session — but
  it displays the user-facing operation strings at `ROM00:6C8E`
  (`Receiving prog`, `Program received`) rather than the internal state or
  command names, confirmed by scanning the LCD through a full traced session.
  *Resolve:* breakpoint the writer of either display index during a traced
  session and correlate it with the wire state in the same exchange. The
  internal names are most likely diagnostic vocabulary; `Diagnostics` on the
  Main Menu is the other place to look for a screen that renders them.

* **Third `u16` of the request header** — It equals the trailing object
  length for states `00`, `45`, `61`, `64`, but is `0x0080` for state `06`
  (which carries a nine-byte object) and `0x00FF` for state `44` (which
  carries none). A requested-maximum reading fits the latter two but is
  unproven, and the state-`06` object is unexplained under it.
  *Resolve:* vary the solicited object size and see whether either value
  tracks it.

* **What selects the Commstar operation** — Narrowed. The state machine at
  `ROM00:692A` shows that `READY-RX-PROG`, `READY-TX-DATA` and
  `READY-TX-PROG` have no incoming legal transition: the only exit from
  `CONNECTED` is `C-COMMAND`, which leads to `READY-RX-DATA`. So the
  operation is chosen by whatever moves the session into one of those three
  states, not by the handheld walking the table.
  Narrowed to one question. `Session_SetState` holds the only write
  instruction for `g_bSessionState`, but it has **46 callers** — an earlier
  note wrongly inferred from the single instruction that the state could only
  be set through the transition table. 26 callers pass a literal (only `0`,
  `2` or `13`); 17 pass `(ram:E48C)`, the cell the dispatcher stages the next
  state into. No literal site sets `READY-RX-PROG`, `READY-TX-DATA` or
  `READY-TX-PROG`, so those are reachable only when the table actually runs —
  which needs the mode gate `ram:E48D` to be 2. A full V24 mode-1 trace ends
  with `E48D = 0`, so Load/Run never arms it. `E48D` has two writers, both
  runtime-stub slots: `ROM00:4563` (slot 65) and `Session_EnableStateMachine`
  (`ROM00:46E9`, slot 66, stores the literal 2).
  *Resolve:* find what makes the loaded session module call stub slot 66
  (`ram:EE24`, `Session_InitState`). That single call arms the state machine,
  and with it the three ready states and the handheld-to-host operations. An
  application can make the call itself (see
  [Commstar application API](../reference/commstar-api.md)), but cannot yet
  issue a *sequence* of commands — see the next item.

* **Answered — why a bare COM does not resume.** Not a calling-convention
  problem. `ram:D837` is an ordinary stack-frame prologue (saves `IX`/`IY`,
  invokes the body via `D836` = `JP (HL)`, returns the result in `HL`); no
  scheduler is involved. The firmware simply **stops to talk to the user**:
  `C_ABORT` from the boot state is an illegal transition, so it raises a
  message box and waits in `SessionWaitContinue` for a keypress that a
  headless caller never sends. `Session_InitState` likewise displays
  `Comms in progress` and does not return.
  *Resolved as far as static work can take it.* There is no legal command
  order reaching `RECORD-TX` — breadth-first search shows states 4, 5, 6, 8,
  9, 10 and 11 unreachable, and no cell anywhere yields 4, 5 or 6 — so
  validation must be suppressed (`ram:E48D = 2`), which is confirmed to
  remove the message box. A call does not return because the operation is a
  **link transaction**: it transmits and waits for the host. An application
  driving `C-INIT-COMMS` with the correct argument layout reaches
  `Comms in progress` and waits there.
  *What remains is an emulator task, not an analysis one:* attach a
  responding peer to an application-driven session. The harness has one for
  the Load/Run route but it is wired to that trace's phases; generalising it
  would let the whole upload sequence be exercised.

* **Watch: anything that writes `ram:E48D`** — The mode gate decides whether a
  command is validated against the transition table (`!= 2`) or bypasses it
  entirely (`== 2`), so any writer changes the meaning of every subsequent
  command. Only two are known — `Session_InitCommsCmd` (`ROM00:4563`, from
  its stack argument) and `Session_InitState` (`ROM00:46E9`, the literal 2) —
  and both are reachable only as runtime-stub slots, so a loaded application
  can set it too, as this project's own test COMs do.
  *Watch for:* any further writer found in RAM-resident module code, a loaded
  application, or a banked page not yet dumped; and any path that leaves it
  at 2 across a session boundary, which would silently disable validation for
  everything that follows.

* **State-44 payload maximum** — 126 bytes succeeds, 128 bytes reaches
  `0x1FAE` Line failure; whether 127 succeeds is open.
  *Resolve:* bisect 127 and pin as a regression.

* **`5C1F`/`5D05` builder preflight** — Every current Load/Run builder
  trace forces its return to success; the condition a real peer must
  satisfy is open.
  *Resolve:* characterise the preflight without forcing `HL=0`.

* **Fresh program-receive arm visibility** — The synthetic peer waits for
  RAM/PC state (`FDDC=FE0E`, `FDD5=01`, `FDC5=E530`, `FDC7=E5BA`,
  `FDD2=2E85`); whether a wire event signals that arm or a real peer
  must retry is open.
  *Resolve:* capture that shows a controller/wire event coinciding with
  the arm, or repeated blind retries.

* **`OK`/`NO`/`DM` tokens beyond the control classifier** — Confirmed only
  in the state-44 control-object classifier; not established as general
  server responses.
  *Resolve:* capture a non-control reply that carries or omits these
  tokens.

## Storage and program loading

* **Upstream physical/session provider for the runtime loader** —
  `ram:D370` is a coroutine continuation (`Coroutine_SwapContinuation`),
  not a provider pointer; the complete Commstar provider path around
  `ROM01:0C12/0CE7` remains open.
  *Resolve:* trace the loaded-session provider bridge (`ROM01:0741` /
  `07EE`) to its service-33 linkage.

* **Banked-RAM retention and allocation policy** — Battery RAM retention
  across power-off and the banked-RAM allocation for `A:`/`B:` are not
  frozen beyond the `8000-FFFF` window.
  *Resolve:* hardware test of the configured machine’s `FE93`/`FE83`
  mapping and a banked-RAM dump (`--dump-bank`).

## RTC

* **`g_bRtcRecordMetadata` byte +0 exact meaning** — Mechanics confirmed
  (FC copied/RTC ignored, FD from init `13h`, FF copied unused); **LIKELY
  century `19`**, exact value open.
  *Resolve:* correlate the stored value with displayed century or
  filesystem datestamps across century boundaries.

* **Day-of-week convention for RTC reg `06h`** — **LIKELY `0=Sunday`**
  from default `1984-01-01` (Sunday); no handler enforces it.
  *Resolve:* set `06h` to each value and observe displayed weekday.

* **Firmware range validation on RTC fields** — Firmware performs no
  conversion or validation; whether out-of-range values are accepted by
  the RTC is open.
  *Resolve:* program each register with an out-of-range value and read
  back.

## UI and input

* **Factory provenance of patch-slot contents** — Whether the
  `EE00-EF37` and `F100-F17F` stub farms ship as `LD HL,1 / RET` or are
  patched at factory is not knowable from ROM.
  *Resolve:* hardware dump of the resident farms.

* **Value-cycle key identity** — ROM maps next/prev to `YES/NO` (`06h`/
  `01h`); operator report that `N/Z` cycles the value remains open.
  *Resolve:* hardware test on the Load/Run form.

## Naming and annotation

* **Should `ram:D837` keep the name `CoroutineTaskSwitch`?** — The bytes at
  `D836`-`D857` are the C compiler's frame-setup helper: it pops its own
  return address, adds `DE` (the local frame size) to SP, saves IX/IY, and
  re-enters the popped address via `CALL D836` = `JP (HL)`. That is
  CONFIRMED and it is what makes `LD DE,nnnn / CALL D837` the entry sequence
  of all 348 compiled routines — see the
  [listing-repair script](ghidra-repair-script.md) pass 1. The "coroutine
  task switch" reading is not supported by those bytes. The symbol has not
  been renamed, because a rename is the symbol plus its plate plus every doc
  mention plus a `TASKS.md` entry, in one pass, and this one is the owner's
  call. The plate at `D837` records both readings and flags the identity as
  under review.
  *Resolve:* owner decides the replacement name (`Lib_FrameEnter` and
  `Compiler_FrameSetup` are the obvious candidates), then one rename pass.

## How to add a new OPEN item

Add the question, the one-sentence evidence, and the discriminating
observation to this page, link to the RE note that carries the bytes, and
file a prioritised task in `research/TASKS.md`. Do not resolve the
contradiction by inventing a mechanism — report both sides.
