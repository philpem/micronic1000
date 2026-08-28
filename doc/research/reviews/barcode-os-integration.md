# Review: external device capture pipeline ↔ OS integration

> **Correction (2026-08-24):** This review's *mechanics* (call chain,
> the `fbc2` decode hook, BDOS fn 03 = `BdosReaderInChar`, routing via
> `fdca` wire-id) have been re-verified and are correct. Its
> *semantics* — calling the device a "barcode reader / wand / scanner,
> 0x2B wand, 0x2A scanner" — are **not proven**: the default FE83 wire
> table makes wire **0x2B** the **EXT STORAGE ADAPTER**, no firmware
> strings name a barcode/pen, and A:/B: RAM drives never touch the bus.
> The handler is the **external-device edge-capture front end with a
> user decode hook at `fbc2`**. Renames applied: `Reader*` → `ExtBus*`,
> `SessionWireStateInit` → `ExtDecodeHookInstall` (156E),
> `ReaderDecodeHookDefault` → `ExtDecodeHookDiscard` (1567). Where this
> doc says "wand"/"scanner"/"barcode", read "external-device wire-2B/
> 2A edge front end" and treat the light-pen reading as a hypothesis.

*Written by a second analysis agent, 2026-08-24. Read-only review — no
changes were made to the Ghidra database or to the existing documents.
All addresses below were re-verified directly against `micron1.bin`
(ROM00/ROM01 overlays) via the Ghidra MCP.*

> **Follow-up status (2026-08-24, main agent):** §6.2 resolved — the
> reader-completion event bit is `fbc9` bit0, posted by
> `ExtBusComplete`(14A3)→`LinkResetSession`(30BD). §6.1 renames/labels
> applied (ExtBus*, `ExtDecodeHookInstall` 156E, `ExtDecodeHookDiscard`
> 1567, fbc0/fbc1/fbc2 + F958/F95C/F95E labels, BdosReaderInChar
> plate). §6.3 (ROM01 fbc5/fbc2 writers) and §6.4 (fbc7/fbc8
> consumers) remain open. §5 fixes all reflected in the docs.

**Scope:** answer the question *"how would a program developed for the
Micronic 1000 install a barcode symbology decoder (COM or DIP) and use
the wand / wand-emulating CCD gun?"*, verify the existing barcode
analysis, and flag mistakes.

---

## 1. Executive summary

The existing analysis correctly identified the low-level capture engine
(`ReaderArmRoute` 1221, `ReaderEdgeDecode` 13B8, port 2Dh
`READER_EDGE`), but it **missed the actual application-facing API and
the designed-in decoder plug-in hook**, and it contains a few concrete
errors (§5). The verified architecture is:

1. **The barcode reader is a pseudo-device in the link-device
   abstraction.** Device-config bytes with bit6 *clear* (`0x2A`,
   `0x2B`, and `0xAB` = `0x2B`+keyboard) are not real 4x-port links:
   when such a device is opened, `LinkCommandCheck` (2F7D) dispatches
   the *config byte itself* through `LinkCommandLookup` (31C6) to
   `ReaderArmRoute`. This is why the reader code is interwoven with the
   PLINTH/V24 link code — it shares the device/session plumbing but
   never touches the 4x transport ports.

2. **BDOS function 03h (CP/M "reader input", RDR:) is the app-facing
   barcode API.** `BdosReaderInChar` (ROM00:1080, dispatch table entry
   fn 3 = 1080, verified from the table bytes at ROM00:3708) selects
   the "reader channel" device from the FE83 config table, arms the
   wand, blocks on the event system, and then returns the scan to the
   caller **one byte per call** through the ring at F95E.

3. **A symbology decoder is installed at the completion hook `fbc2`**
   (bank byte `fbc1`, RST10-stub template at `fbc0`). The ROM's default
   hook (ROM00:1567, installed only at **cold start** by 156E) simply
   **zeroes the element count, discarding every scan**. The firmware
   *requires* an external decoder to be installed before BDOS fn 3 ever
   delivers data. This is the answer to the "install" question: a COM
   or DIP program writes its decoder's address into `fbc2`
   (+ bank into `fbc1`), and the OS calls it after every capture with
   the raw width table; whatever the decoder leaves in the parameter
   block is what the application receives.

---

## 2. Verified call chain (BDOS fn 3 → wand → app)

Every step below was re-derived from disassembly this session.

```
CALL 5, C=03h  (CP/M reader input)
 └─ BdosEntryDispatch (36A0)
     – fn<0x25: vectors through the **RAM** table at F1EB (36E2:
       LD HL,0xF1EB) → fn 3 = ROM00:1080          [patchable, see §4.3]
 └─ BdosReaderInChar (1080)
     ├─ DeviceSlotSelectPair (110C):
     │    index = ((fbc5 >> 2) + 5) & 0x1F  → DeviceTableIndex (31FF)
     │    → HL = FE83 + index − 1 ; f999 = *HL (device id), f978 = HL
     ├─ f999 == 0x80 → keyboard path (18C0)        [reader ch. = kbd]
     ├─ ring not empty (f954 ≠ f956) → return next byte  [see §3]
     └─ ring empty → ConsoleMsgToLink (0EE4):
          ├─ LinkTransportOpen (2EAB): fdca = *(f978) = device id
          ├─ builds TX descriptor @FDEE (→F990) and RX descriptor
          │    @FE12: len 0x20, buffer ptr (FE14) = **F958**
          ├─ LinkTransportCall (2F1A): fdd4 = fdca; BIT 6 of id:
          │    clear → LinkCommandCheck (2F7D): IX=31F5, B=fdca
          │    └─ LinkCommandLookup (31C6): id table 31F2 =
          │       {2B, 2A, 23, 03, FF}; handler words (post-increment
          │       base 31F7) = {1221, 1221, 1893, 1893}
          │       → 0x2B and 0x2A both → ReaderArmRoute, with
          │         A = matched id (becomes route byte f9aa),
          │         HL = (FDF0) = F990, DE = (FE14) = F958
          ├─ ReaderArmRoute (1221): fbb7 = F958 (caller envelope);
          │    zeroes 6 bytes; wand: 2Ch bit1 attention pulse;
          │    scanner (f9aa==2A): 2Ah bit1 + CommsLineDeassertRd;
          │    ReaderQueueWorkItem(1) → async capture work item
          └─ EventWaitForLink (168F): HALT-wait on event mask
               (fbc9 & fbca), returns when the reader completion
               posts its event bit
```

Capture and delivery (async, work-item context):

```
ReaderPollWorkItem (12EC) / ReaderScanPoll (1317)
 └─ ReaderEdgeDecode (13B8): times READER_EDGE (2Dh) bit0 levels
     → element count f9b4, width table (reversed) …
 └─ delivery tail (1443–14A2):
     (fbb9) = width-table ptr ; (fbbb) = count (word, hi=0)
     PUSH 0xFBB9 ; PUSH 0x1468 ; dispatch to **(fbc2)**  ← DECODE HOOK
       – target <0x8000 → executes stub at fbc0: D7 (RST 10h),
         bank=fbc1, addr=fbc2  (banked call)
       – target ≥0x8000 whose first byte is D7 → jumped to directly
     return to 1468:
       count (fbbb)==0        → 14DC discard/re-arm  ← DEFAULT HOOK PATH
       status (fbb5)≠0        → 14DC
       else: envelope := status@+0, count word @+4/+5,
             LDIR count bytes from (fbb9) to envelope+6
       then OUT_LATCH bit5 set, ReaderArmFrontEnd (14C8)
```

Return to the application (back in BdosReaderInChar, 10B4–10D1):

```
EventWaitForLink returned bit0 set:
  DE = word at F95C  (= envelope+4 = element count)
  f998 = E (count low) ; f954 = F95E ; f956 = F95E + DE
  return A = 0x1B                     ← "scan arrived" sentinel
next fn-3 call : returns f998 (count), clears it
next N calls   : return the N data bytes from the ring, one per call
ring exhausted : next call arms a fresh scan
```

So the per-scan byte protocol seen by a program calling BDOS fn 3 is:
**`1Bh`, `count`, then `count` data bytes** — where "data bytes" are
whatever the fbc2 hook left behind (raw widths if the hook passes them
through, decoded ASCII if the hook decodes in place).

---

## 3. The FE83 device table and `fbc5` — how routing is configured

`DeviceTableIndex` (31FF): index ≥ 'A' → FE93 (storage table);
index 1..16 → **FE83 + (index−1)**; index 0 or ≥17 → error 0xFD.

Cold-start defaults (copied ROM00:3267 → FE83 by the routine at 3220):

```
entry:  1    2    3    4  |  5    6    7    8  |  9   10   11   12 | 13   14   15   16
value: 80   AB   63   43  | 80   2B   63   43  | 80   67   63   43 | 80   67   63   43
       └── console ──┘      └── reader ch. ─┘    └─── punch ────┘    └─── list ────┘
```

Device-id byte semantics (verified from the flag logic in
DeviceConsoleInChar 0E00 / BdosReaderInChar / LinkTransportCall):

| Bits | Meaning |
|------|---------|
| bit7 | local keyboard/LCD flag (`0x80` = keyboard only) |
| bit6 | **real 4x-port link** (0x43/0x45/0x63/0x67 → LinkBlockTx/Rx path) |
| bit6 clear, low bits ≠ 0 | **pseudo-device**: id & 0x7F dispatched via LinkCommandLookup — `0x2B` wand, `0x2A` scanner route, 0x23/0x03 → 1893 stub |

Note entry 2 default `0xAB` = bit7 + 0x2B = **keyboard AND wand
combined** on the *console* channel — selecting it makes scans and
keystrokes arrive interleaved through BDOS fn 1/6 (EventWaitForLink
waits on both event bits at once). This is the "barcode as keystrokes"
mode, and it is why a decode hook that rewrites widths into ASCII makes
scans transparent to ordinary console-reading programs.

`fbc5` (written by BDOS fn **F7**, read back by fn **F6**) is a packed
selector, verified per-field:

| Field | Consumer | Table window |
|-------|----------|--------------|
| bits 0–1: `(fbc5&3)+1` | LinkSelectActiveDevice (0EC8) — console (fn 1/2/6) | entries 1–4 |
| bits 2+: `(fbc5>>2)+5` | DeviceSlotSelectPair (110C) — reader (fn 3) | entries 5–8 (values 0–3) |
| bits 4+: `(fbc5>>4)` | BdosPunchOutChar (10D2) — punch (fn 4), *direct* index 1–16 | any entry |
| (also read by BdosListOutChar 1049 — not traced further) | | |

Examples: `fbc5 = 0x04` → console = LCD/keyboard, reader channel =
entry 6 = 0x2B wand. `fbc5 = 0x01` → console = 0xAB keyboard+wand.
`fbc5 = 0x00` (probable cold default) → reader channel = entry 5 =
0x80, i.e. **fn 3 reads the keyboard until a program selects the wand**.

BDOS fns **F8/FA** read/write all 16 bytes of FE83 (verified at
3237/3241). The default table contains **no 0x2A entry** — using the
CCD/scanner route requires writing 0x2A into a slot with fn FA first.
(BDOS fn F9 stores a preset pair into fbc7/fbc8 from the 5-pair table
at 15E0 — `{0B,01},{0B,04},{03,01},{03,04},{07,01}` — but nothing in
the ROM statically *reads* fbc7/fbc8; likely consumed by the
boot-loaded session modules. Open item.)

---

## 4. Answer: installing and using a symbology decoder

### 4.1 The designed hook: `fbc0–fbc3` (the important new finding)

`ReaderDecodeHookInit` (my name; currently `SessionWireStateInit`,
ROM00:156E, called **only** from ColdStartSelfTestBanner at 022F)
builds this structure in battery RAM:

```
fbc0: D7           RST 10h opcode      ┐ synthesized banked-call stub
fbc1: <bank>       (init: from fea7)   │ executed when the hook target
fbc2: <addr word>  (init: 0x1567)      ┘ is a banked/ROM address
```

After every successful edge capture, the delivery tail calls the
routine at `(fbc2)` **before** anything is copied to the caller,
passing (on the stack, under the return address 1468) a pointer to the
parameter block:

```
fbb9 (word): pointer to the element-width table
fbbb (word): element count
fbb5 (byte): status (0 = OK, 0xEE = capture error)
```

The hook's contract, inferred from 1468–148F: whatever it leaves in
`(fbb9)`/`(fbbb)` is copied into the caller envelope and becomes the
bytes BDOS fn 3 hands to the application. Therefore:

* **The default hook (ROM00:1567) does `LD HL,0 ; LD (fbbb),HL ; RET`
  — it zeroes the count, so every scan is silently discarded and the
  capture re-arms (path 14DC).** Out of the box the machine beeps but
  delivers nothing. A decoder is *mandatory*, and `fbc2` is its socket.
* A symbology decoder installs itself by writing its entry address to
  `fbc2` and its bank byte to `fbc1` (resident code ≥8000h needs no
  real switch; the RST10 dispatcher at 0010 compares the bank byte to
  the shadow f791 and skips the switch when equal). Installation is
  **persistent across warm restarts / power-off** because fbc0-fbc3 is
  battery RAM and the default is only rewritten at cold start.
* Inside the hook the decoder reads the raw width table, classifies the
  symbology (Code 39 / I-2of5 / EAN…), and either (a) rewrites
  `(fbb9)` to point at its decoded ASCII string and `(fbbb)` to its
  length — the app then receives *decoded characters* from fn 3 (or
  fn 1, in console-0xAB mode); or (b) leaves count = 0 to reject a bad
  read, which makes the OS re-arm automatically (built-in retry).

### 4.2 Recipe for a .COM application (self-contained decoder)

```asm
; 1. select devices: console = LCD/kbd, reader channel = wand (entry 6)
    LD   C, 0F7h        ; DIPOS-B: set active device selector
    LD   E, 004h        ; bits0-1=0 console, (>>2)=1 -> FE83 entry 6 = 2Bh
    CALL 0005h
; 1b. (scanner gun only) rewrite FE83 so a reader-channel slot holds 2Ah:
;     C=0F8h read 16 bytes, patch entry, C=0FAh write back.
; 2. install the decode hook (pass-through shown; a real decoder
;    rewrites fbb9/fbbb with decoded ASCII instead)
    LD   HL, hook       ; hook must be reachable: resident copy ≥8000h,
    LD   (0FBC2h), HL   ;  or set the bank byte at FBC1 for banked code
; 3. read scans
loop:
    LD   C, 3
    CALL 0005h          ; blocks until a sweep; returns A = 1Bh
    LD   C, 3
    CALL 0005h          ; A = element count N
    ...                 ; N more fn-3 calls -> the N data bytes
    JR   loop

hook:                   ; called in OS context after each capture:
    RET                 ; leaving fbb9/fbbb untouched = deliver raw widths
```

Notes: fn 3 blocks in a HALT loop (EventWaitForLink) — for a
non-blocking design, poll with fn 06h/E=FF (BdosDirectConsoleIo,
0FD6, drains the same F95E ring without arming), or arm directly with
the banked call (§4.4). On program exit the hook should be restored to
0x1567 (or the program left resident), since a dangling `fbc2` into a
freed TPA will crash the next scan.

### 4.3 Recipe for a resident DIP decoder

The DIP loader-record grammar already documented (SyscallQueueBankedBlock
D727, `{RST10, bank, addr}` constructor records) is the natural
installer: a DIP places the decoder in battery RAM (or a RAM bank) and
its constructor record writes `fbc1/fbc2`. Two integration depths:

1. **Decode-only** (recommended): hook `fbc2` as above, decode in
   place. Combined with console device 0xAB (fn F7, E=0x01), every
   ordinary program then sees barcode data as console keystrokes —
   no per-app changes.
2. **BDOS interposition** (heavier): the dispatcher was verified to
   vector through the **RAM** tables — F1EB for fns 00–24h, F1D1 for
   F3–FF (36A0: `LD HL,0xF1EB / ADD HL,BC / ADD HL,BC`) — so a
   resident module can also patch the fn-1/3/6 vectors to wrap the
   byte-level protocol (e.g. to buffer a whole decoded label and strip
   the 1B/count framing). Keep the handler callable from the kernel's
   F382 trampoline context.

### 4.4 Direct (non-BDOS) arming — corrected calling details

A resident/banked program may call `ReaderArmRoute` itself and skip
the fn-3 framing:

```asm
    LD   DE, buf        ; result envelope (≥ 6 + max elements bytes)
    LD   A, 02Bh        ; route: 2Ah scanner, else wand
    RST  10h            ; banked-call restart #2 — opcode D7
    DB   0              ; bank 0
    DW   1221h          ; ReaderArmRoute
    ; returns immediately after queueing the capture work item;
    ; poll buf+0 (status) / fbb6 (busy) — completion also runs the
    ; fbc2 hook, then fills buf: status@+0, count word @+4/+5,
    ; data from +6.
```

HL must not point at a byte 02h and `fdd7` must be 0 on entry, or the
call takes the cancel branch (that is the disarm mechanism
LinkHandleIdle uses — it sets fdd7=FF first). This path is what the
existing barcode-reader.md sketched, but with three corrections: the
opcode (§5.4), the envelope offsets (§5.3), and the fact that it is the
*secondary* interface — BDOS fn 3 is the primary one.

---

## 5. Mistakes found in the existing documents

### 5.1 `protocol-comms.md` — LinkCommandLookup table is off by one

The doc says the 31F2 table maps `2B→0xFF03, 2A→0x1221, 23→0x1221,
03→0x1893`. Wrong: 31C6 advances IX by 2 **before** the compare, so
with the caller's IX=31F5 (set at 2F7E) the effective word base is
31F7. Actual bytes (`31F2: 2B 2A 23 03 FF | 31F7: 21 12 21 12 93 18 93
18`) give **2B→1221, 2A→1221, 23→1893, 03→1893**. There is no 0xFF03
handler. (barcode-reader.md has this one right.)

### 5.2 `barcode-reader.md` + TASKS.md — "a remote peer can command a scan via link cmd 2A/2B" is wrong

The id matched by LinkCommandLookup is **`fdca`, the local device-config
byte** captured at LinkTransportOpen (2EB8: `LD A,(HL) / LD (fdca),A`)
— i.e. the FE83 entry for the currently selected device. It is not a
received frame command id; no inbound frame reaches this dispatch. The
"command ids 0x2A/0x2B" are *device types* in the local config table.
(Additionally, the LinkHandleIdle route sets `fdd7=FF` before
dispatching, which makes ReaderArmRoute take its **cancel** branch —
that path disarms a pending scan on link-idle; it never starts one.)

### 5.3 `barcode-reader.md` — result envelope offsets

Doc: "+4 word pulse count, +5 n = widths". Actual (1468–148F): status
byte @ **+0**; count is a 16-bit word @ **+4/+5** (`LD (HL),C / INC /
LD (HL),B`); data bytes start @ **+6** (LDIR after a further INC). +1
is written 1 only on the cancel path; +1..+3 otherwise stay zero. In
the BDOS path the envelope is fixed at **F958** (RX descriptor FE12:
len 0x20, ptr F958), which is why F95E — called "the console RX ring
f95E" in the docs — is literally envelope+6: it is the reader's data
area, into which f954/f956 are pointed after each scan. The suggestion
in barcode-reader.md §"Tying the decoder into the OS" to "push decoded
characters into the console RX ring (f95E)" has it backwards: the OS
itself points the ring at the scan result; the clean injection point is
the fbc2 hook (§4.1), not manual ring stuffing.

### 5.4 `barcode-reader.md` — RST snippet has the wrong opcode

"`RST 0x02` … opcode DF at 0010h": restart #2 vectors to 0010h and its
opcode is **D7** (`RST 10h`); DF is `RST 18h` (0018h). The firmware
itself confirms D7: the decode-hook dispatcher compares the hook's
first byte against 0xD7 (1460 `CP 0xd7`), and SessionWireStateInit
writes 0xD7 into fbc0 as the stub opcode.

### 5.5 `diposb-programmers-guide.md` — fn 03h is described as "mostly no-op"

§3 lists "03h/04h/05h reader in / punch out / list out (mapped, mostly
no-op)". Fn 03h is in fact the **fully-implemented barcode/RDR: input
path** (1080, per the dispatch table at 3708), and fn 04h routes bytes
out through the FE83-selected device (10D2). This is the biggest gap in
the guide — the barcode API is its missing chapter, and the fn F7
description should document the packed `fbc5` fields (§3 above).

### 5.6 Minor

* `barcode-reader.md` says the caller buffer *is* `fBB7`; fbb7 is the
  *pointer variable* holding the caller's buffer address (F958 in the
  BDOS path). Mostly phrased correctly, occasionally not.
* "Success → beep + disarm" — after a *delivered* scan the tail
  re-arms the front end (14A0 → ReaderArmFrontEnd), it does not only
  disarm; continuous scanning is the design (the ring must drain
  before fn 3 arms a *new* session, but the front end stays live).
* `SessionWireStateInit` (156E) is misnamed — it initializes the
  **reader decode-hook stub** (fbc0–fbc4, fbb6). Suggest
  `ReaderDecodeHookInit`, and naming 1567 `ReaderDecodeHookDefault`
  (with a comment that it discards scans by zeroing fbbb).

---

## 6. Recommended follow-ups (for the other agent)

1. **Annotate the discoveries**: label fbc0/fbc1/fbc2 (decode-hook
   stub/bank/vector), F958 (reader result envelope), F95C (count),
   F95E (data area), f999/f978 (reader-channel device byte/ptr), fbc5
   packed fields; plate-comment BdosReaderInChar with the
   1B/count/data protocol; fix the two doc errors (§5.1, §5.3–5.5).
2. **Find who posts the reader's event bit** (fbc9 bit0) on
   completion — closes the EventWaitForLink loop end-to-end.
3. **ROM01 / session-module survey for fbc5 and fbc2 writers** — the
   UI almost certainly has a "reader device" settings screen; finding
   it would confirm the intended user-facing configuration values, and
   any factory decoder DIP would reveal itself by writing fbc2.
4. **fbc7/fbc8 consumers** (BDOS fn F9 presets) — no static readers;
   probably the boot-loaded session modules.
5. Emulator experiment once boot is fixed: install a pass-through hook
   at fbc2, feed synthetic edges on port 2Dh bit0, and confirm the
   1B/count/widths sequence from fn 3 — this validates §2–§4 end to
   end and yields the width-unit timing scale.

---

*Everything in §2–§4 marked as verified was read directly from the
disassembly this session: 0010, 022F, 0E00, 0EE4, 0FD6, 1080, 10D2,
110C, 120F/1221, 1443–14A2, 1458–1467, 1567/156E, 15A4, 15CB/15E0,
168F, 2EAB, 2ED3, 2F1A, 2F7D, 31C6/31F2, 31FF, 3220/3257/3267,
3237/3241/3248, 36A0/36EE, 3708.*
