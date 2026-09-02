# Memory and I/O map

This page is the programmer's reference for how a Micronic 1000 addresses
memory: what the bank window holds, what the fixed upper 32K holds, how
code in one bank calls code in another, where the stacks live, whether
there is a heap (there is not), and which I/O ports the firmware actually
touches.

It is written for three jobs in particular:

* writing a **barcode decoder module** that the ROM's capture tail calls
  after every scan;
* **patching an OS function** by repointing a kernel vector;
* passing buffers across the Commstar and BDOS entry points without
  silently handing the callee an address that is not mapped.

All three depend on the same fact, which is the single most important
thing on this page: **a pointer handed across a bank boundary must
address unbanked RAM, at or above `0x8000`.**

!!! danger "Every address here is specific to *this* ROM image"
    The bank hardware, the `RST 10h` convention and the split at `8000`
    are structural. The **addresses of OS data structures are not.** They
    are wherever this ROM's boot chains happened to place them, and the
    boot chains are data records inside the ROM images
    (`micron1.bin` / `micron2.bin`, dated 1996-12-24). A different ROM
    revision can move any of them, and nothing in the firmware advertises
    a version to check against.

    See [ROM-version fragility](#7-rom-version-fragility) for the worked
    example, and treat every four-digit RAM address below as
    "true of this dump", not "true of the Micronic 1000".

For the short stability-classified summary of the same hardware, see
[Memory and I/O map](memory-map.md). For the evidence trail behind the
unbanked region table, see
[RE notes: Unbanked RAM map](../re-notes/unbanked-ram-map.md).

## Stability

| Area | Stability |
|---|---|
| Bank window `0000-7FFF`, `BANK_SEL` at `47h`; fixed RAM `8000-FFFF` | **Stable** |
| Page-zero replication into every bank; `0005` BDOS gate; `RST` and NMI vectors | **Stable** |
| Port *addresses* below | **Stable** |
| Port *bit-level meanings* | **Provisional** — see the notes in each row |
| RTC at `08h`/`28h` (HD146818) | **Stable** address pair |
| Byte-latch link at `4Ah-4Fh` | **Stable** as a latch block; framing is in [Protocol: Commstar](../protocol/commstar.md) |
| Every absolute RAM address on this page | **This ROM image only** — see [§7](#7-rom-version-fragility) |

Battery RAM retains program and filesystem state across power-off. The
allocation policy of any banked configuration beyond the fixed
`8000-FFFF` window is not a stable contract.

## Evidence tags

Claims here carry the project's tags: **CONFIRMED** (read from the
bytes), **LIKELY** (firmware evidence plus a documented hardware fact),
**SUSPECTED** (plausible, unverified), **OPEN** (not established).

---

## 1. The banked memory model

The Z80's 64K address space is split in half.

| Range | Size | Behaviour |
|---|---:|---|
| `0000`-`7FFF` | 32K | **Bank window.** Contents selected by port `47h`. |
| `8000`-`FFFF` | 32K | **Fixed battery-backed SRAM.** Always mapped, in every bank. |

CONFIRMED: the split is visible in every bank-aware routine in the
firmware; the clearest single witness is the BDOS DMA test at
`ROM00:3A2D` (`2A A3 FF 7C FE 80 D0`), which branches on
`address >= 0x8000` — see [§2.5](#25-the-rule-and-two-independent-corroborations).

### 1.1 What selects a bank

A bank is selected by writing its number to **port `47h`**, and the
firmware always mirrors that write into the shadow byte
**`ram:F791`**. The canonical setter is four instructions:

```
ram:f41b  F3            DI
ram:f41c  32 91 F7      LD   (F791),A     ; shadow first
ram:f41f  D3 47         OUT  (47h),A      ; then the hardware
ram:f421  CD 4E F5      CALL F54E         ; conditional EI (tests FFA8)
ram:f424  C9            RET
```

CONFIRMED, byte-verified at `ram:F41B`-`F424`. The same
`LD (F791),A / OUT (47h),A` pair appears at `ram:F4B0`, `ram:F4BA`,
`ram:F443`, `ram:F463`, `ROM00:39D0`, `ROM00:39DA` and elsewhere —
**37 `OUT (47h),A` sites in `ROM00` alone**.

Three consequences for a programmer:

* **`ram:F791` is authoritative, not advisory.** Every dispatcher in the
  firmware reads `F791` to learn the current bank rather than reading the
  port back; `ROM00:0012` (`3A 91 F7`) is the first instruction of the
  inter-bank call path. If you switch banks yourself and do not update
  `F791`, the next `RST 10h` will compare against a stale value and take
  the wrong branch. CONFIRMED.
* **Bank switches run with interrupts disabled.** The setter does `DI`
  before the `OUT` and re-enables only if the interrupt-enable shadow
  `ram:FFA8` is non-zero (`ram:F54E`: `LD A,(FFA8); OR A; JP Z,…; EI`).
  CONFIRMED.
* **The switch is instantaneous and total.** There is no partial or
  windowed mapping: the whole of `0000`-`7FFF` changes at once, including
  the code you are executing if you are executing below `8000`. This is
  why the bank helpers themselves live at `F180`+ in fixed RAM.

### 1.2 What the banks contain

| Bank | Contents |
|---|---|
| `00` | ROM image 1 (`micron1.bin`) — reset entry, kernel image, BDOS handlers, LCD/keyboard/RTC/link drivers, barcode capture, diagnostics |
| `01` | ROM image 2 (`micron2.bin`) — the Workstation application and Commstar |
| `02`+ | 32K pages of the 256K static RAM: program images, DIP/COM storage, the RAM "disks" |

Bank 0 and bank 1 as the two ROMs is owner-supplied hardware fact
(`micronic_notes.md`: "Banks 0 and 1 map the two ROM images into the
lower half; additional bank values select 32K pages of RAM. On reset ROM
bank 0 is selected"), and is consistent with the firmware: `ROM00:0000`
holds `C3 03 01` (`JP 0103`, the reset entry — bank 0 must be selected at
reset), while `ROM01:0000` holds `C3 38 F2` (`JP F238`), the same vector
the page-zero installer stamps into every RAM bank. CONFIRMED
(consistency), LIKELY (the identity of banks 2+ as specific SRAM pages).

**The bank number space runs `00`-`40`.** The page-zero installer and the
bank sweeper both count `C = 0x41` downward (`ram:F425`, `ram:F438`,
`ram:F46E`: `0E 41 / 0D` = `LD C,41h; DEC C`), and the RAM presence scan
counts `B` up from `1` and stops at `0x41` (`ROM00:267A` `06 01`,
`ROM00:26C8` `FE 41`). CONFIRMED. That is 65 possible banks; how many are
populated on a given machine is discovered at boot, not assumed.

### 1.3 What every bank has in common

Three things are guaranteed present no matter which bank is selected,
because the firmware puts them there:

**Page zero.** `ram:F438` (`Boot_BankWalkInit`) walks banks `40h` down to
`01`, selecting each in turn and writing the fixed vectors into it:

```
ram:f449  3E C3         LD   A,C3h        ; JP opcode
ram:f44b  32 00 00      LD   (0000),A
ram:f44e  21 38 F2      LD   HL,F238
ram:f451  22 01 00      LD   (0001),HL    ; 0000: JP F238
…
ram:f456  32 05 00      LD   (0005),A
ram:f459  21 80 F1      LD   HL,F180
ram:f45c  22 06 00      LD   (0006),HL    ; 0005: JP F180  (BDOS gate)
```

CONFIRMED, byte-verified at `ram:F449`-`F45E`. `ROM01:0000` and
`ROM01:0005` already contain exactly those two `JP`s, so bank 1 needs no
patching and the write is harmless.

**The restart vectors**, all of which jump into the resident kernel in
fixed RAM:

| Vector | Content | Role |
|---|---|---|
| `0000` | `JP 0103` in bank 0, `JP F238` in every other bank | reset / warm entry |
| `0005` | `JP F180` | BDOS / system-call gate |
| `0008` | `JP F5E1` | `RST 08h` kernel entry |
| `0010`-`001E` | *15 bytes of inline dispatcher* | **banked call, see §2** |
| `0018` | — | **unusable**: it is byte 8 of the `0010` dispatcher |
| `0020` | `JP F5EA` | `RST 20h` kernel entry |
| `0028` | `JP F5ED` | `RST 28h` kernel entry |
| `0030` | `JP F5F0` | `RST 30h` kernel entry |
| `0038` | `JP F5F3` | `RST 38h`; doubles as the `IM 1` IRQ entry |
| `0066` | `JP F5F6` | NMI |

CONFIRMED, byte-verified in both ROM images, which are **identical from
`0005` onward** — only `0000` differs (`C3 03 01` in `ROM00`,
`C3 38 F2` in `ROM01`). Because every target is `>= F180`, i.e. in the
fixed upper 32K, an interrupt or a `CALL 0005h` lands in mapped code from
any bank. `IM 1` is set at `ROM00:22EC` (`ED 56`).

Note the `0018` row: the `RST 10h` dispatcher is 15 bytes and runs
straight through the `RST 18h` slot, which holds `D7` (`RST 10h`) at
`0018`. `RST 18h` is not a usable restart on this machine.

**The chain pointer at `7FFC`.** The last word of each bank's window
points at that bank's boot-load record chain; the boot code reads it with
`2A FC 7F` (`LD HL,(7FFC)`) twice, once per ROM bank. CONFIRMED at
`ROM00:703C` and `ROM00:7047`. See
[RE notes: OS internals](../re-notes/os-diposb.md).

### 1.4 Which banks hold RAM

At cold boot the firmware pattern-tests every bank and records the result
as a **per-bank presence bitmap at `ram:FEB0`-`FEEF`**, one byte per bank
for banks `01`-`40`, each byte a 4-bit mask of the bank's four 8K pages
(`ROM00:267A`-`26D6`; `LD HL,FEB0` at `267F`, `LD B,1` at `267A`,
`CP 41h` at `26C8`, `LD DE,2000` 8K stride, `55AA`/`AA55` patterns).
A second pass at `ROM00:26E3` rescans 63 entries comparing each against
`0Fh` (all four pages good). CONFIRMED.

Summary cells: `ram:FEA7`/`FEA8` bank range, `FEA9`/`FEAA` page counts,
`FEAB` the RAM-size word, `FEAF` `g_bRamBankBitmap`.

---

## 2. The inter-bank call: `RST 10h`

This is the mechanism that bites people, so it is worth understanding
exactly rather than by analogy.

### 2.1 The stub form

A cross-bank call is a **four-byte stub**:

```
D7          RST  10h
<bank>      DB   target bank
<lo> <hi>   DW   target address
```

You reach it with an ordinary `CALL` to the stub's first byte. The `RST`
pushes the address of the two operand bytes; the dispatcher at `0010`
picks them up. Ghidra will happily disassemble the operands as
instructions — they are data.

The firmware keeps a whole arena of these: **281 four-byte slots at
`ram:ED1C`-`F17F`**, filled by the boot chains and used as UI vtable
targets and deferred-call records.

The arena is initialised by replicating one 4-byte template across all
281 slots (`ram:D6C0`):

```
ram:d6c0  21 D7 D6      LD   HL,D6D7      ; template
ram:d6c3  11 1C ED      LD   DE,ED1C      ; arena base
ram:d6c6  01 04 00      LD   BC,4
ram:d6c9  ED B0         LDIR                        ; seed slot 0
ram:d6cb  21 1C ED      LD   HL,ED1C
ram:d6ce  11 20 ED      LD   DE,ED20
ram:d6d1  01 60 04      LD   BC,460h
ram:d6d4  ED B0         LDIR                        ; smear it over the rest
```

CONFIRMED, byte-verified. `4 + 0x460 = 0x464 = 1124`, exactly the arena
size. **The template is `21 01 00 C9` — `LD HL,0001; RET`** (`ROM00:7086`,
i.e. `ram:D6D7`), so an *uninstalled* slot is not a banked stub at all:
it returns `HL = 1` and does nothing. A slot only becomes a
`{D7, bank, lo, hi}` far-call stub when a boot-chain `fn=2` record
installs one over the template.

The cursor that tracks the next free slot is `ram:D684`, seeded to `ED1C`
by the two literal bytes `1C ED` at `ROM00:7033`, which sit inside the
dispatch block image copied to `ram:D681`. CONFIRMED.

### 2.2 The same-bank path

```
ROM00:0010  E1            POP  HL           ; HL -> inline operands
ROM00:0011  5E            LD   E,(HL)       ; E = target bank
ROM00:0012  3A 91 F7      LD   A,(F791)     ; A = current bank
ROM00:0015  BB            CP   E
ROM00:0016  C2 4B D7      JP   NZ,D74B      ; different bank -> heavy path
ROM00:0019  23            INC  HL
ROM00:001A  7E            LD   A,(HL)
ROM00:001B  23            INC  HL
ROM00:001C  66            LD   H,(HL)
ROM00:001D  6F            LD   L,A
ROM00:001E  E9            JP   (HL)         ; same bank: just jump
```

CONFIRMED, byte-verified `ROM00:0010`-`001E`. Note that the `POP HL`
consumed the stub's own return address, so the same-bank case is a **tail
jump**: the callee's `RET` returns to whoever `CALL`ed the stub. That is
what makes the stub behave like a plain `CALL` from the caller's point of
view.

### 2.3 The cross-bank path and the shadow stack

```
ram:d74b  D1            POP  DE           ; DE = caller's return address
ram:d74c  E5            PUSH HL
ram:d74d  2A 6F E3      LD   HL,(E36F)    ; shadow-stack cursor
ram:d750  2B 77         DEC HL; LD (HL),A ;   push caller's bank
ram:d752  2B 72         DEC HL; LD (HL),D ;   push return address hi
ram:d754  2B 73         DEC HL; LD (HL),E ;   push return address lo
ram:d756  22 6F E3      LD   (E36F),HL
ram:d759  E1            POP  HL
ram:d75a  7E            LD   A,(HL)       ; A = target bank
ram:d75b  23 5E         INC HL; LD E,(HL) ; DE = target address
ram:d75d  23 56         INC HL; LD D,(HL)
ram:d75f  CD 70 D7      CALL D770         ; switch bank, enter callee
;   --- callee runs in the target bank; its RET lands here ---
ram:d762  E5            PUSH HL
ram:d763  2A 6F E3      LD   HL,(E36F)
ram:d766  5E 23 56      LD E,(HL); INC HL; LD D,(HL)   ; pop return address
ram:d769  23 7E         INC HL; LD A,(HL)              ; pop caller's bank
ram:d76b  23            INC  HL
ram:d76c  22 6F E3      LD   (E36F),HL
ram:d76f  E1            POP  HL
ram:d770  D5            PUSH DE           ; return address becomes the target
ram:d771  C3 .. ..      JP   (patched)    ; -> kernel bank setter; its RET
                                          ;    "returns" to the pushed DE
```

CONFIRMED, byte-verified `ram:D74B`-`D773`.

Two details worth calling out because they are unusual:

* **`ram:D770` is a self-modifying trampoline.** `D771` is a `JP` whose
  operand at `D772`-`D773` is written at runtime
  (`ram:D77E`/`D78D`: `22 72 D7`, from `(0001) + 3Ch` — the kernel's
  jump-vector slot, `ram:F274` = `JP F41B`, the bank setter of
  [§1.1](#11-what-selects-a-bank)). CONFIRMED. `PUSH DE` before the jump
  is the "call by pushing a return address" idiom: the setter's `RET`
  transfers control to the callee.
* **The push and pop orders are mirror images**, so a frame is three
  bytes: `{return-lo, return-hi, caller-bank}` reading upward from the
  cursor.

### 2.4 Shadow-stack geometry and its hard limit

| Cell | Size | Role |
|---|---:|---|
| `ram:E36F`-`E370` | 2 | shadow-stack cursor |
| `ram:E371`-`E3B0` | 64 | shadow-stack body, grows **down** from `E3B1` |
| `ram:E3B1`-`E3C0` | 16 | 32-bit register file (`E3BD` = program load ceiling) |

The cursor is reset to `E3B1` by `ram:D6B5`
(`E5 / 21 B1 E3 / 22 6F E3 / E1 / C3 71 D7` — and note that the same
routine also performs a bank switch, so it is a combined
"reset-and-select"). CONFIRMED, byte-verified.

**Maximum nesting depth is 21 cross-bank calls.** Frame *n* leaves the
cursor at `E3B1 - 3n`; frame 21 leaves it at `E372`. Frame 22 would write
`E371`, `E370`, `E36F` — and `E36F`/`E370` *are the cursor*, which the
same routine then overwrites with its own value. **There is no depth
check anywhere in `ram:D74B`-`D75F`**: the 22nd nested cross-bank call
corrupts the mechanism silently. CONFIRMED (arithmetic over byte-verified
bounds).

Twenty-one is generous for ordinary firmware paths, but a decode hook or
a patched OS function that itself makes cross-bank calls is *adding* to
whatever depth the firmware was already at when it called you.

### 2.5 The rule, and two independent corroborations

**The caller's bank is restored when the callee returns, but it is not
mapped while the callee runs.** Between `ram:D75F` and `ram:D762` the
lower 32K belongs to the callee. Therefore:

> Any pointer passed across a bank boundary — argument, buffer, return
> area, callback address — must be `>= 0x8000`.

Two places in the firmware confirm this from opposite directions.

**The Commstar entry points.** Every buffer the firmware itself hands to
a session entry point is unbanked: `ram:D39D` (`C-RX-BLK`, from
`ROM01:141A`), `ram:D422` (`C-COMMAND`, from `ROM01:1343`), and
`ram:ECAB`, `EC99`, `ECA2`, `EC8E`, `D120` (the `C-INIT-COMMS` identity
strings, from `ROM01:12AD`-`12BD`). Not one of them is below `8000`.
CONFIRMED — see [Commstar application API](commstar-api.md).

**The BDOS.** `ram:F510` (`ROM00:3A2D`) tests the caller's DMA address
and bounces the sector through fixed RAM *exactly when* it is banked:

```
ram:f510  2A A3 FF      LD   HL,(FFA3)    ; caller's DMA address
ram:f513  7C            LD   A,H
ram:f514  FE 80         CP   80h
ram:f516  D0            RET  NC           ; >= 8000h: use the buffer in place
ram:f517  11 FF FE      LD   DE,FEFF      ; < 8000h: bounce 128 bytes
ram:f51a  D5            PUSH DE
ram:f51b  01 80 00      LD   BC,80h
ram:f51e  CD 98 F4      CALL F498         ; KernMemCopy (bank-aware)
ram:f521  E1 C9         POP HL; RET
```

CONFIRMED, byte-verified at `ROM00:3A2D` (`2A A3 FF 7C FE 80 D0 11 FF
FE`). The firmware pays for a 128-byte copy rather than let a banked
pointer cross the boundary. So should you.

**The barcode decode hook makes the same test explicitly** — see
[§6.2](#62-writing-a-barcode-decoder-module).

---

## 3. Memory map

### 3.1 The banked window, `0000`-`7FFF`

Layout is per-bank, but three regions are common to all of them:

| Range | Contents |
|---|---|
| `0000`-`00FF` | Page zero: reset/`RST`/NMI vectors and the `0005` BDOS gate, replicated into every bank ([§1.3](#13-what-every-bank-has-in-common)) |
| `0100`-`7FFB` | Bank body — ROM code in banks 0 and 1; program image or file storage in RAM banks. For a loaded COM this is the low part of the TPA, entered at `0100`. |
| `7FFC`-`7FFF` | In the two ROM banks: the boot-load chain pointer for that bank (word at `7FFC`). In RAM banks this is ordinary storage. |

A loaded COM program occupies `0100` upward, spanning out of the window
into fixed RAM and stopping at the loader's ceiling `D080` — a maximum
image of `0xCF81` bytes. See
[Program file formats](program-formats.md).

### 3.2 Fixed RAM, `8000`-`FFFF`

The full region-by-region table, with the evidence for every row, is in
[RE notes: Unbanked RAM map](../re-notes/unbanked-ram-map.md#region-table).
It is the authority; this is the programmer-facing summary.

| Range | Size | Contents |
|---|---:|---|
| `8000`-`D080` | 20609 | **Upper TPA.** Free above a loaded program's image. No firmware instruction references any address in `8006`-`D080`. |
| `D081`-`D480` | 1024 | Workstation module B and its workspace (`D081` screen-handler tables, `D0F0` Load/Run handlers, `D2CB`-`D480` workspace) |
| `D481`-`D680` | 512 | **Loaded program's stack** ([§4.2](#42-the-loaded-programs-stack)) |
| `D681`-`D892` | 530 | DIPOS dispatch block: syscall dispatch, boot-chain walker, the `RST 10h` cross-bank thunk of [§2.3](#23-the-cross-bank-path-and-the-shadow-stack) |
| `D893`-`E103` | 2161 | Session module A (string/register-file runtime) and the BDOS parameter page |
| `E104`-`E2F9` | 502 | Module A2 and session config; `E22D` = session state |
| `E2FA`-`E36E` | 117 | Page-zero image copy |
| `E36F`-`E3C0` | 82 | **Cross-bank shadow stack** and register file ([§2.4](#24-shadow-stack-geometry-and-its-hard-limit)) |
| `E3C1`-`E704` | 836 | Commstar session page and **live session state** — see the warning below |
| `E705`-`ED1B` | 1559 | Workstation/session state, logon credentials, loaded-program header and block descriptors |
| `ED1C`-`F17F` | 1124 | **Far-call stub arena** — 281 × 4-byte `RST 10h` stubs |
| `F180`-`F68C` | 1293 | **Resident kernel** (BDOS gate and dispatch tables, syscall envelopes, `RST`/NMI stubs, bank helpers) |
| `F68D`-`F77F` | 243 | **Unclaimed tail of the kernel arena** — see below |
| `F780`-`F799` | 26 | **I/O port shadows** ([§5.3](#53-port-shadows)) |
| `F79A`-`F819` | 128 | **System stack** ([§4.1](#41-the-system-stack)) |
| `F81A`-`F9B4` | 411 | System and extension variables, RTC records, RAM-disk geometry, BDOS directory swap buffer (`F8B8`-`F937`) |
| `F9B5`-`FC05` | 593 | **Barcode edge-timing capture buffer** (`F9B5`-`FBB4`) and barcode/system state, incl. the decode-hook socket at `FBC0` |
| `FC06`-`FD45` | 320 | **LCD framebuffer** (`FC06`, 20×8) and its compare shadow (`FCA6`) |
| `FD46`-`FD96` | 81 | RTC working area; the **countdown-timer / work-item table** at `FD5C`-`FD83` (10 slots × 4 bytes); comms config table at `FD84` |
| `FD97`-`FEA2` | 268 | Link/device state; the **per-link frame-sequence table** at `FE43`-`FE82` (one byte per remote unit address); the two 16-byte device config copies |
| `FEA3`-`FEEF` | 77 | Boot/sizing variables and the per-bank RAM presence bitmap |
| `FEF0`-`FFA8` | 185 | Banked-call envelope save area (incl. `FEFE`, the caller's bank), BDOS sector and FCB bounce buffers, DMA address (`FFA3`), FCB pointer (`FFA5`), interrupt-enable shadow (`FFA8`) |
| `FFA9`-`FFFF` | 87 | **Unclaimed remainder above the BDOS variable block** — see below |

!!! warning "Two spans that used to look free are not, and two are still open"
    Four spans in this map were unidentified until recently. Two have
    since been resolved and are **live structures**: `FD64`-`FD83` is
    slots 2-9 of the ten-slot countdown-timer table based at `FD5C`, and
    `FE45`-`FE82` is entries 2-63 of the per-link frame-sequence table
    based at `FE43`. Both look empty because only their base address ever
    appears as a literal. Do not use either.

    `F68D`-`F77F` and `FFA9`-`FFFF` remain **LIKELY unclaimed / OPEN**.
    `F68D` is simply the first byte after the resident kernel image —
    `ROM00:02FE` copies `369D` → `F180` with `BC = F68D` as the **end**
    address (`01 8D F6`, then a byte-copy loop) — and `F180 + 0x600 =
    F780`, so the 243 bytes are the unused remainder of a round 1536-byte
    kernel arena. The RE notes carry the current state and the
    discriminating tests; consult them rather than inferring from this
    page.

!!! danger "`E48C`-`E6FF` is live Commstar session state"
    Staging data there has already caused a real bug in this project
    (the 561-byte upload anomaly). The named cells and the failure
    analysis are in
    [RE notes: Unbanked RAM map](../re-notes/unbanked-ram-map.md#do-not-touch).

### 3.3 Nothing in fixed RAM survives a cold boot

`ram_page_test_4banks` (`ROM00:2530`) destructively pattern-tests the
whole of `8000`-`FFFF` — four 8K pages from `8000` with a `2000` stride,
four fill/verify passes each — and is called unconditionally from
`reset_entry` at `ROM00:01BB`. CONFIRMED. That is *why* the kernel is
reinstalled from ROM and the boot chains re-run on every boot: their
destinations have just been erased. Battery backing preserves fixed RAM
across power-*off*; it does not preserve it across a cold *reset*.

---

## 4. Stacks and heap

There are three stacks, and no heap.

### 4.1 The system stack

`SP = F81A`, growing **down** into `F79A`-`F819` (128 bytes) before it
reaches the I/O port shadows at `F780`.

CONFIRMED: `31 1A F8` (`LD SP,F81A`) at `ROM00:0175`, `01A6`, `01D4` and
`024D` — and those are the only genuine `LD SP,nn` sites in `ROM00`
besides the barcode capture trick at `13BF` and the loaded-program stack
at `71A9`. `ROM00:024D` is the BDOS function 0 (system reset) handler, so
a warm boot re-establishes it.

**Usable extent: 128 bytes**, `F819` down to `F79A`. Below that are the
port shadows (`F780`-`F799`), and below *those* the currently
unidentified `F68D`-`F77F`. A stack excursion past `F79A` therefore
corrupts the bank shadow `F791` and the link control shadow `F794`
before it reaches anything harmless — which is a fast way to a machine
that has forgotten which bank it is in.

### 4.2 The loaded program's stack

`SP = D681`, growing **down** into `D481`-`D680` (512 bytes) before it
reaches module B's workspace.

CONFIRMED: `31 81 D6` (`LD SP,D681`) at `ROM00:71A9`, which is
`ram:D7FA` at runtime (the dispatch block is `LDIR`'d `ROM00:7030` →
`ram:D681`, so `71A9 - 7030 + D681 = D7FA`). The full entry sequence is:

```
ram:d7f6  CD B5 D6      CALL D6B5     ; reset the cross-bank shadow stack,
                                      ;   then select the bank in A
ram:d7f9  E1            POP  HL       ; HL = program entry point
ram:d7fa  31 81 D6      LD   SP,D681
ram:d7fd  E9            JP   (HL)
```

CONFIRMED, byte-verified at `ROM00:71A5`-`71AC`
(`CD B5 D6 E1 31 81 D6 E9`). A program therefore starts with a clean
512-byte stack **and** a freshly reset cross-bank shadow stack.

**512 bytes is all you get**, and it is shared with everything the OS
does on your behalf while you are running — every BDOS call, every
interrupt, every cross-bank thunk pushes onto it. Below `D481` is module
B's workspace, whose corruption shows up as UI misbehaviour rather than
an immediate crash.

### 4.3 The cross-bank shadow stack

`ram:E36F` cursor, `E371`-`E3B0` body, 3 bytes per frame, 21 frames.
Covered in [§2.4](#24-shadow-stack-geometry-and-its-hard-limit).

It is a *separate* stack, not a region of either of the above. It is
reset at program entry and at kernel-loop entry (`ram:D6A0`), never
bounds-checked, and never unwound by anything except a matching return.

### 4.4 Heap: there is none

**DIPOS-B has no dynamic memory allocator.** All storage is statically
placed by the boot chains and the loader. CONFIRMED to the extent a
negative can be:

* **No allocator-shaped function exists.** A search of every named
  function in the database for `alloc`, `free`, `heap`, `pool`, `malloc`,
  `brk` returns nothing. (CP/M's "allocation vector" is a disk block
  bitmap, not a memory heap, and DIPOS-B's equivalents are stubs — see
  [RE notes: CP/M comparison](../re-notes/cp-m-comparison.md).)
* **The one pointer that looks like a break pointer is a constant.**
  `ram:E3BD` (`g_pProgramLoadCeiling`) has exactly **one writer** —
  `ROM00:7052` `21 81 D0 / 22 BD E3` (`LD HL,D081; LD (E3BD),HL`), which
  runs at `ram:D6A3` in the kernel main loop — and **two readers**, both
  in the ROM01 loader (`ROM01:0DA3` and `ROM01:0E9E`), both of which use
  it in a subtraction to compute how much room a program image has:

  ```
  ROM01:0d9e  11 00 01     LD   DE,0100h     ; TPA base
  ROM01:0da1  19           ADD  HL,DE
  ROM01:0da2  E5           PUSH HL
  ROM01:0da3  2A BD E3     LD   HL,(E3BD)    ; = D081, always
  ROM01:0da6  D1           POP  DE
  ROM01:0da7  EB           EX   DE,HL
  ROM01:0da8  CD A9 E0     CALL E0A9         ; 16-bit subtract
  ```

  It is never advanced, never decremented, and never consulted at
  runtime by anything but the loader. It is a fence, not a break.
* **Every buffer in the map is at a fixed address.** The bounce buffers,
  the LCD framebuffer, the capture buffer, the session objects, the stub
  arena — all are placed by boot-chain records with literal destinations.
  Nothing in the map is described by a length-plus-base pair that
  changes.

So the answer for a module author is: **decide your addresses at build
time.** There is no `alloc` to call, no free-list to walk, and no OS
service that will hand you a block. What you get is the space nobody else
is using, and you have to know where that is — which is the whole point
of [§3.2](#32-fixed-ram-8000-ffff).

### 4.5 The `0006` trap

CP/M convention says the word at `0006` is the first byte above the TPA,
so a program can size itself from it. **On DIPOS-B that word does not
mean that.** There are two writers:

* `ram:F456` (page-zero installer) writes `F180` — the BDOS gate.
* `ram:D7BE` writes `D681` — the dispatch block base.
  CONFIRMED at `ROM00:716D` (`21 81 D6 / 22 06 00 / C9`).

Neither is the loader's ceiling. The real limit is `D081`, held in
`ram:E3BD`, and `D081`-`D680` is occupied by module B, its workspace and
your own stack. A program that trusts `(0006) - 1` as top-of-memory will
believe it owns 1536 bytes that it does not.

**Use `D080` as the last usable byte of your image**, or read
`ram:E3BD` if you want the firmware's own number.

---

## 5. I/O port map

### 5.1 How this list was built

Two independent passes, because neither alone is sufficient:

1. **Ghidra instruction search** over all 21,113 disassembled
   instructions in `ROM00`, `ROM01` and the RAM-resident modules —
   169 `OUT` and 40 `IN`. Aligned and therefore trustworthy, but bounded
   by disassembly coverage (`ROM00` 61 %, `ROM01` 37 %).
2. **Raw opcode scan** of both full ROM images for `DB nn` / `D3 nn` and
   the `ED`-prefixed register-indirect forms
   (`ED 40/48/50/58/60/68/70/78` in, `ED 41/49/51/59/61/69/71/79` out),
   with every hit inspected in context.

The raw scan produces a large majority of false positives, and it is
worth saying why, because the same trap catches Ghidra: **`DB` and `D3`
turn up constantly as one byte of an address operand.** `CD DB 22` is
`CALL 22DB` — `DB` is the low byte — not `IN A,(22h)`; `2A 6E D3` is
`LD HL,(D36E)`, with `D3` as the high byte, not an `OUT`.
Module A lives at `ram:D893`-`E0F3` and module B's
workspace at `ram:D2CB`-`D480`, so calls and variable references inside
them generate `DB xx` and `D3 xx` pairs by the hundred.

Two of Ghidra's own hits are exactly this: `ROM01:0D07` "`OUT (21h),A`"
and `ROM01:0F00` "`OUT (D1h),A`" are misaligned readings of
`22 6A D3` (`LD (D36A),HL`) and `2A 6E D3` (`LD HL,(D36E)`). Likewise
`ROM00:6FFD` "`IN A,(0Dh)`" and `ROM00:7021` "`IN A,(0Bh)`" fall inside
byte tables. **None of the four is real I/O.**

Net result: **`ROM01` performs essentially no port I/O at all.** Its one
genuine access is `ROM01:0042` `3E 00 / D3 47` (`LD A,0; OUT (47h),A`),
inside the page-zero image. Everything the Workstation and Commstar do to
hardware, they do by calling into bank 0 or the resident kernel.

### 5.2 The ports

Direction is as the firmware uses it, not necessarily as the hardware
decodes it.

| Port | Name | Dir | What is established |
|---:|---|:--:|---|
| `00h` | `KBD_SENSE` | R | Keyboard matrix sense. Only the low 6 bits are used: `AND 3Fh` at `ROM00:0181` and `ROM00:1A4F`. CONFIRMED |
| `02h` | `KBD_DRIVE` | W | Keyboard drive / configuration latch. `LD A,3Fh` drives all lines (`ROM00:1A42`), `00h` clears them (`ROM00:1A83`); reset writes `FDh` at `ROM00:017B` to select one column. Shadows at `F780` and `F782`. Also written by the NMI and power-down paths. CONFIRMED as the keyboard drive; the non-keyboard uses are **Provisional** |
| `03h` | `LCD_DATA` | W | HD61830 data byte. CONFIRMED (`ROM00:1F7F`, `1F96`, `1F9E`, `1ED2`) |
| `04h` | `IRQ_MASK` / `OUT_LATCH` | W | **Interrupt-enable mask, active low.** `ROM00:22E9` does `LD A,1Fh; DI; IM 1; CPL; LD (F784),A; OUT (04h),A` — the mask is complemented before output, so a *set* bit in the argument enables a source. A second entry at `ROM00:2306` passes `A = 2`. Also carries power-latch bits (`PowerLatchSetBit0`/`ClrBit0`, `ROM00:1B36`/`1B41`). Shadow `F784`. CONFIRMED |
| `05h` | `IRQ_STATUS` / `STATUS_IN` | R | **Interrupt / status byte, active low.** `ROM00:230A` (`IrqWorkerPollPort5`) does `IN A,(05h); LD (F785),A; CPL; AND 8` — snapshot to `F785`, complement, test bit 3. Also read at reset (`ROM00:01B1`, `0238`, `17A5`) as a boot-condition byte. CONFIRMED that it is polled and complemented; the meaning of individual bits beyond bit 3 is **unknown** |
| `07h` | `CTRL_07` | W | Control latch, shadow `F786`. Written at power-down (`ROM00:28F2`), by the link watcher (`ROM00:24AD`, `24B8`) and at `ROM00:17A0`, `17B6`, `23CC`. Function **unknown** |
| `08h` | `RTC_ADDR` | W | HD146818 register-address latch. Also reached as `LD C,08h; OUT (C),B` at `ROM00:1801`, `22DD`, `22E4`. CONFIRMED |
| `23h` | `LCD_REG` | W | HD61830 register/command select. Also `LD C,23h; OUT (C),B` at `ROM00:1F7D`. CONFIRMED |
| `28h` | `RTC_DATA` | R/W | HD146818 data, paired with `08h`. Register-indirect reads at `ROM00:2104` (`LD C,28h; IN B,(C)`) and `ROM00:246E`/`2477` (`LD C,28h`, after selecting RTC registers 07h and 08h). CONFIRMED. Register map: [RE notes: RTC](../re-notes/rtc.md) |
| `2Ah` | `CTL_LATCH_2A` | W | Peripheral control latch, shadow `F78B`. Used by the barcode front end (`ROM00:123B`, `124A`, `14F2`, `1541`, `1550`) and by `LinkPortSelect` (`ROM00:345D`). CONFIRMED as a shared latch; individual bits **Provisional** |
| `2Bh` | `SOUND` | W | Beeper. `Port2bWrite` (`ROM00:35C6`) / `Sound_Off` (`ROM00:35CB`). CONFIRMED |
| `2Ch` | `CTL_LATCH_2C` | W | Control latch, shadow `F78D`. Barcode arm/disable (`ROM00:1231`, `1283`, `1292`, `14E6`, `150F`-`1528`), link port select and probe (`ROM00:3487`, `34B5`), power-down (`ROM00:1786`). CONFIRMED as a shared latch; bits **Provisional** |
| `2Dh` | `EXTBUS_EDGE` | R | Barcode-pen edge/level input. Eight read sites, all inside the capture front end (`ROM00:1299`-`13ED`). CONFIRMED |
| `33h` | *unknown* | R | **One access in the whole firmware**: `ROM00:1ED9` `DB 33` (`IN A,(33h); RET`), the tail of a four-instruction stub at `ROM00:1ED0` that first does `LD A,0Dh; OUT (03h),A`. Alignment is sound (the stub follows a `RET` at `1ECF`), but nothing references `1ED0` directly. **Purpose unknown.** Candidates worth discriminating on hardware: an LCD status/busy read (it sits inside the LCD driver block and follows an `LCD_DATA` write), or an incompletely-decoded alias of `23h`/`03h`. Do not assume it is either |
| `46h` | `LCD_CONTRAST` | W | Written only via `LD A,(FC05); LD C,46h; OUT (C),A` at `ROM00:1FD4`, called from `LcdInit` (`ROM00:1F2B`) and from `PowerLatchIncr`/`PowerLatchDecr` (`ROM00:1D73`/`1D57`), which increment and decrement the battery-RAM byte `FC05`. A ±1-adjustable level held in battery RAM and re-applied on LCD init is a contrast setting. **LIKELY** (mechanism CONFIRMED; the identity rests on the access pattern plus the project's established `LCD_CONTRAST` label). The Ghidra name `WritePowerLatchPort46` is a grandfathered misnomer |
| `47h` | `BANK_SEL` | W | 32K bank select, shadow `F791`. 37 write sites in `ROM00`, 24 in the resident kernel. CONFIRMED |
| `48h` | `IR_STROBE` | W | Two-bit output, driven `0`,`1`,`2`,`3` in sequence by `IrSenseDiagEcho` (`ROM00:24F7`-`252D`) and by `LinkSelftestRun` (`ROM00:28AE`-`28E4`), also `SessionSystemInit` (`ROM00:0359`, value `03h`) and power-down (`ROM00:178D`). CONFIRMED as a strobe/select output paired with `49h`; the project's older `LCD_STROBE` label is **not supported by the call sites**, which are all IR/link diagnostics |
| `49h` | `IR_SENSE` / `BOOTKEYS` | R | Low 2 bits read back after each `48h` write and compared against the value written (`ROM00:24F2`-`251B`: `OUT (48h) 0/1/2` then `IN A,(49h); AND 3; CP …`) — a loopback/presence test. Also read twice at reset: `IN A,(49h); AND 1; JR Z` selects the cold path, `AND 2; JP NZ` selects a second boot mode (`ROM00:0168`-`0172`). CONFIRMED |
| `4Ah` | `LINK_CTRL` | W | External-link control latch, shadow `F794`. 26 write sites. Bit assignments in [Memory and I/O map](memory-map.md) and the RE notes are **Provisional** |
| `4Bh` | `LINK_STATUS` | R | Link status, polled in `LinkBlockTx`/`LinkBlockRx`/`LinkProbe`/`LinkWaitReady`. Bit assignments **Provisional** |
| `4Ch` | `LINK_CMD` | W | Link command latch; the only write is `81h` in `LinkPresent` (`ROM00:34F5`). CONFIRMED |
| `4Dh` | `LINK_TXD` | W | Link TX data byte (`ROM00:32B6`, sole site). CONFIRMED |
| `4Eh` | `LINK_RXD` | R | Link RX data byte (`ROM00:338C`, sole site). CONFIRMED |
| `4Fh` | `LINK_PROBE` | W | Device probe/reset; the only write is `1Fh` in `LinkProbe` (`ROM00:3491`). CONFIRMED |

**No other port is accessed anywhere in either ROM image or in any
RAM-resident module.** The untouched ranges are `01h`, `06h`,
`09h`-`22h`, `24h`-`27h`, `29h`, `2Eh`-`32h`, `34h`-`45h`, and everything
above `4Fh`. That is a statement about the firmware, not about the
hardware: a port this firmware never uses may still be decoded, and the
address decoding may well be partial — the `03h`/`23h`, `08h`/`28h` and
`2Ah`/`2Ch` pairings suggest only some address lines are compared.
**SUSPECTED** for the partial-decode inference; a hardware read of an
unused port would settle it.

### 5.3 Port shadows

The firmware keeps a RAM mirror of most write-only latches, so that
read-modify-write on a latch is possible. All live in `ram:F780`-`F799`:

| Cell | Mirrors |
|---|---|
| `F780`, `F782` | port `02h` (drive value, configuration value) |
| `F784` | port `04h` |
| `F785` | last value read from port `05h` |
| `F786` | port `07h` |
| `F78B` | port `2Ah` |
| `F78D` | port `2Ch` |
| `F791` | port `47h` — `g_bBankShadowP47` |
| `F794` | port `4Ah` — `g_bLinkCtrlShadow` |
| `FC05` | value written to port `46h` |
| `FFA8` | interrupt-enable state, tested before every `EI` |

CONFIRMED. **Update the shadow whenever you write the latch**, or the
next firmware read-modify-write will undo your change — and in the case
of `F791`, will mis-route the next cross-bank call.

### 5.4 Register-indirect accesses

Seven sites use `OUT (C),r` / `IN r,(C)`, where the port number is in
`C`. All are resolved:

| Site | `C` set at | Port | Note |
|---|---|---|---|
| `ROM00:1801` | `0E 08` | `08h` | RTC address latch, followed by `IN A,(28h)` |
| `ROM00:1A7E` | `0E 02` | `02h` | `KbdDriveSetAll`, `A = 3Fh`, shadow `F782` |
| `ROM00:1A88` | `0E 02` | `02h` | `KbdDriveClearAll`, `A = 00h` |
| `ROM00:1F76` | `0E 03` | `03h` | LCD data |
| `ROM00:1F7D` | `0E 23` | `23h` | LCD register select, `B = 0Ch` |
| `ROM00:1FD9` | `0E 46` | `46h` | LCD contrast, `A = (FC05)` |
| `ROM00:2104` | `0E 28` | `28h` | `RtcReadRegisterFile`, `IN B,(C)` |
| `ROM00:22DD`, `22E4` | `0E 08` | `08h` | `RtcRegWrite` / `RtcRegRead` |
| `ROM00:246E`, `2477` | `0E 28` | `28h` | `LinkStatusWatcher` reads RTC registers `07h`/`08h` |

CONFIRMED — the `LD C,nn` immediately precedes each in every case. The
remaining raw `ED 50` (`ROM00:7E1C`) and `ED 58` (`ROM01:59A0`) hits fall
inside data tables and are not instructions.

---

## 6. Writing code that lives in unpaged RAM

Two kinds of resident code are in scope: a **barcode decoder module**
that the ROM calls after each scan, and a **patch to an OS function**.
Both must live at or above `8000`, for the reason in
[§2.5](#25-the-rule-and-two-independent-corroborations): the ROM will
call you with a bank other than yours selected.

### 6.1 Where to put it

Ranked, from
[RE notes: Unbanked RAM map](../re-notes/unbanked-ram-map.md#safe-for-scratch):

1. **`C000`-`D080` (4225 bytes)** — first choice. The top of the unbanked
   TPA, immediately below the loader's ceiling. No instruction anywhere
   in the firmware references any address in `8006`-`D080`, and `D081` is
   a hard firmware constant, not an inference.
2. **`8006`-`BFFF` (16378 bytes)** — same argument, four times the room,
   but it is the part of the TPA a growing program image reaches first.
   Use it only when you know your image size.

Everything else that *looks* free is not:

* `F68E`-`F77F` is unreferenced but sits 128 bytes below the system
  stack top, behind the port shadows. Anything you put there is a
  stack-depth canary, not scratch — and it is still `OPEN`.
* `FFA9`-`FFFF` (87 bytes) is big enough for a signature word, and is
  immediately adjacent to a densely packed BIOS variable block. Also
  still `OPEN`.
* `FD64`-`FD83` and `FE45`-`FE82` **look** unreferenced and are not:
  they are the tails of the countdown-timer table at `FD5C` and the
  per-link frame-sequence table at `FE43`. This is the general trap on
  this firmware — a base-address literal plus a walked pointer is the
  normal idiom, so unreferenced bytes are the rule *inside* buffers, not
  evidence of free space.

And the constraint that catches everyone: **`ROM00:2530` pattern-tests
the whole of `8000`-`FFFF` on every cold boot.** Nothing you place in
fixed RAM survives a reset unless something re-materialises it.

### 6.2 Writing a barcode decoder module

The hook socket is a four-byte `RST 10h` stub at `ram:FBC0`:
opcode `D7` at `FBC0`, bank byte at `FBC1`, target address at
`FBC2`-`FBC3`. It is the far-call stub form of
[§2.1](#21-the-stub-form), sitting in fixed RAM.

The ROM ships a **discard** hook, so an unmodified machine throws every
capture away:

```
ROM00:1567  21 00 00      LD   HL,0
ROM00:156a  22 BB FB      LD   (FBBB),HL   ; element count = 0 -> reject
ROM00:156d  C9            RET

ROM00:156e  21 67 15      LD   HL,1567     ; reset the socket to the above
ROM00:1571  22 C2 FB      LD   (FBC2),HL
…
ROM00:157b  3E D7         LD   A,D7h
ROM00:157d  32 C0 FB      LD   (FBC0),A
ROM00:1580  3A A7 FE      LD   A,(FEA7)
ROM00:1583  32 C1 FB      LD   (FBC1),A    ; bank byte
```

CONFIRMED, byte-verified. Note that the ROM's own default hook is at
`1567` — **below `8000`** — so the default configuration exercises the
banked path, which is why `FBC1` has to be filled in.

The capture tail calls it like this — and note the second instruction of
the dispatch, which is [§2.5](#25-the-rule-and-two-independent-corroborations)
written into the ROM:

```
ROM00:1450  21 B9 FB      LD   HL,FBB9     ; width-table ptr / count cells
ROM00:1453  E5            PUSH HL          ; argument
ROM00:1454  21 68 14      LD   HL,1468
ROM00:1457  E5            PUSH HL          ; hook returns into the envelope
ROM00:1458  2A C2 FB      LD   HL,(FBC2)   ; hook target
ROM00:145b  CB 7C         BIT  7,H         ; is it in unbanked RAM (>=8000)?
ROM00:145d  28 05         JR   Z,1464      ;   no  -> go through the stub
ROM00:145f  7E            LD   A,(HL)
ROM00:1460  FE D7         CP   D7h         ; is the target itself an RST10 stub?
ROM00:1462  28 03         JR   Z,1467      ;   yes -> jump straight to it
ROM00:1464  21 C0 FB      LD   HL,FBC0     ; otherwise enter via the stub
ROM00:1467  E9            JP   (HL)
```

CONFIRMED, byte-verified `ROM00:1450`-`1467`.

Read that as a specification:

* **A hook below `8000` is always entered through the banked stub** — the
  `BIT 7,H` test guarantees it, and `FBC1` must therefore hold your
  bank.
* **A hook at or above `8000` whose first byte is `D7`** is jumped to
  directly; it is expected to *be* a `RST 10h` stub of its own.
* **A hook at or above `8000` whose first byte is not `D7`** is still
  entered through `FBC0`, so `FBC1` still has to be right.

**The firmware's own installer fills the bank byte for you.** `ROM00:1587`
— reached through the resident kernel's jump-vector slot `ram:F27D`
(`JP F36B`, i.e. `ROM00:3888`) — does exactly this:

```
ROM00:1587  ED 53 C2 FB   LD   (FBC2),DE   ; DE = new hook address
ROM00:158b  3A FE FE      LD   A,(FEFE)    ; caller's bank, saved by the
ROM00:158e  32 C1 FB      LD   (FBC1),A    ;   envelope at ram:F38B
ROM00:1591  3E D7         LD   A,D7h
ROM00:1593  32 C0 FB      LD   (FBC0),A
```

CONFIRMED, byte-verified. `ram:FEFE` is written by the banked-call
envelope (`ram:F388`: `LD A,(F791); LD (FEFE),A`), so the bank recorded
is the bank the *installing program* was running in — which is the right
answer for a decoder that lives in a RAM bank.

The simplest correct arrangement, though, is to sidestep banking
entirely: **put your decoder at `C000`+ and it is valid in every bank**,
whatever `FBC1` ends up holding. On entry the hook receives a pointer to
the width-table cells at `FBB9`/`FBBB` (pointer and count) and returns to
`ROM00:1468`. It may rewrite the pointer and count to present decoded
bytes, or zero the count to reject the read and re-arm — which is
literally all the default hook at `1567` does. The register-level
contract is in [Barcode reader](barcode.md) and
[RE notes: OS internals](../re-notes/os-diposb.md).

The 512-byte capture buffer at `ram:F9B5`-`FBB4` is yours to read during
the hook, and is filled by `PUSH` from `SP = FBB5` downward and then
reversed in place (`ROM00:13BB`-`1419`), which is why an address-literal
search finds nothing inside it.

### 6.3 Patching an OS function

The resident kernel dispatches BDOS calls through a **word table in
unbanked RAM**, which makes it a real hook point rather than a
theoretical one:

```
ram:f18f  06 00         LD   B,0          ; BC = C = function number
ram:f191  79 FE 25      LD A,C; CP 25h
ram:f194  38 2F         JR   C,F1C5       ; fn < 25h  -> CP/M table
ram:f196  FE F3         CP   F3h
ram:f198  30 2A         JR   NC,F1C4      ; fn >= F3h -> extension table
…                                         ; 25h..F2h: special-case chain
ram:f1c4  05            DEC  B            ; B=FFh: biases the index by -200h
ram:f1c5  21 EB F1      LD   HL,F1EB      ; table base
ram:f1c8  09 09         ADD HL,BC; ADD HL,BC
ram:f1ca  7E 23 66 6F   LD A,(HL); INC HL; LD H,(HL); LD L,A
ram:f1ce  C3 82 F3      JP   F382         ; common banked-call envelope
```

CONFIRMED, byte-verified `ram:F18F`-`F1D0`. Cross-checked against the
table's own contents: entry 0 is `024D` (`ROM00:024D` = the system-reset
handler, which is one of the four `LD SP,F81A` sites), and entry 3 is
`1080` — `BdosReaderInChar`, exactly as documented in the
[programmer's guide](../manual/programmer-guide.md).

There is one table base and two windows onto it, which is why the two
tables sit `0x200` apart:

| Table | Address | Index | Covers |
|---|---|---|---|
| Extension | `ram:F1D1`-`F1EA` | `F1EB + 2×fn − 200h` (via `B = FFh`) | DIPOS-B functions `F3h`-`FFh`, 13 words |
| CP/M range | `ram:F1EB`+ | `F1EB + 2×fn` | BDOS functions from `00h` |

CONFIRMED: for `fn = F3h`, `F1EB + 0x1E6 − 0x200 = F1D1` exactly.

Both are inside the resident kernel image, so:

* **A patch is a 16-bit store**: write your handler's address into
  `F1EB + 2 × fn` for a CP/M-range function, or into
  `F1D1 + 2 × (fn − F3h)` for an extension function. The dispatcher will
  route the call through the same `F382` envelope it uses for a ROM
  handler.
* **Your handler is entered with bank 0 selected.** The envelope saves
  the caller's bank and then switches unconditionally:

  ```
  ram:f382  22 F6 FE      LD   (FEF6),HL   ; handler address
  ram:f385  2A FA FE      LD   HL,(FEFA)   ; restore the caller's argument
  ram:f388  3A 91 F7      LD   A,(F791)
  ram:f38b  32 FE FE      LD   (FEFE),A    ; caller's bank -> FEFE
  ram:f38e  F3            DI
  ram:f38f  F5 3E 00      PUSH AF; LD A,0
  ram:f392  32 91 F7      LD   (F791),A
  ram:f395  D3 47         OUT  (47h),A     ; bank 0, always
  ```

  CONFIRMED, byte-verified `ram:F382`-`F396`. So a handler in the banked
  window must be in **bank 0**, and a handler at `C000`+ works
  unconditionally, which is the reason to put it there.
* **The patch does not survive a reset.** `ROM00:02FE` copies the kernel
  image `ROM00:369D` → `ram:F180` up to end address `F68D` on every boot
  (`11 B5 00 / 21 E8 35 / 19 / 11 80 F1 / 01 8D F6` then a byte-copy
  loop), and `F1D1`/`F1EB` are inside that range. Reinstall your patch
  from your own startup path.
* **Special-cased functions bypass the table.** Functions `2Dh`, `2Eh`,
  `30h`, `62h`, `68h` and `69h` are dispatched by an explicit compare
  chain at `ram:F19A`-`F1C2` *before* the table lookup is reached
  (`CP 30h / LD HL,1893 / JR Z`, and so on), so patching their table
  slots has no effect. CONFIRMED.
* **Do not call an unassigned function in `25h`-`F2h`.** Anything in that
  range that is not one of the six special cases falls through to the
  `DEC B` at `ram:F1C4` and is indexed with the `−200h` bias, so
  `fn = 25h` fetches its handler from `ram:F035` — inside the far-call
  stub arena. There is no range check. CONFIRMED (arithmetic over the
  byte-verified dispatch above).

Beyond this table and the barcode socket, **no general hooking API has
been shown to exist.** The far-call stub arena at `ram:ED1C`-`F17F` is
281 repointable four-byte stubs and UI vtables target it directly, so it
is mechanically patchable — but which stub serves which purpose is
established for only a fraction of them, and there is no published index.
Treat repointing an arena stub as reverse engineering, not as an
interface.

### 6.4 Checklist

* Code and every pointer you hand to the OS: `>= 0x8000`.
* Update `ram:F791` if you touch port `47h` yourself; update the other
  shadows in [§5.3](#53-port-shadows) if you touch their latches.
* Budget the 512-byte program stack and the 21-frame cross-bank shadow
  stack — you are adding to whatever depth the caller was already at.
* Re-apply anything you install after a cold boot; `ROM00:2530` will have
  erased it.
* Verify your chosen region empirically before betting on it. The
  pattern-fill procedure and the emulator flags for it are in
  [RE notes: Unbanked RAM map](../re-notes/unbanked-ram-map.md).

---

## 7. ROM-version fragility

Everything structural on this page — the `8000` split, port `47h` and its
shadow, the `RST 10h` stub form, the three-byte shadow-stack frame, the
rule that cross-bank pointers must be unbanked — is a property of the
design and will hold across ROM revisions.

**The addresses are not.** They are where *this* ROM's boot chains put
things. The chains are data records inside `micron1.bin` and
`micron2.bin`, each naming a source offset, a destination and a length
(see [RE notes: OS internals](../re-notes/os-diposb.md)). Change a module's
size by one byte in a later build and every destination after it moves.
There is no version word to check and no indirection table to ask.

### The worked example: `ram:E5C2`

`ram:E5C2` is the body of the 134-byte service-33 receive object whose
header sits at `ram:E5BC`. The emulator harness writes to it on one
deliberate path — the path where the harness is *impersonating* a
service-33 receive, so writing into the receive payload is the correct
thing to do. That is a legitimate use of a precisely known address.

It is also exactly the kind of assumption that does not survive a ROM
change. `E5C2` is inside the block the bank-0 boot chain places with a
`memset E3C1..E704`; its position is determined by the cumulative size of
everything the chains copied before it. A different ROM build with a
different module A, or a different session-config block, puts the receive
object somewhere else — and the harness would then be writing 126 bytes
into whatever now occupies `E5C2`, with no error and no diagnostic.
The failure mode is silent and length-dependent: this project has already
had one such bug, in which an uncapped write from `E5C2` reached `E6C1`
and buried live session state, and it only reproduced at certain image
lengths.

The general rule that follows:

> An address in fixed RAM is only as stable as the module placement that
> produced it. Depend on the *structure* (a receive object with a header
> word and a payload) and derive the address; do not hard-code the
> address and assume the structure.

Where the firmware gives you a pointer to read — `ram:E3BD` for the load
ceiling, `ram:F791` for the current bank, `ram:FFA3` for the DMA address,
`ram:FBC2` for the decode hook — read it. Those indirections are the
version-independent part.

---

## Related

* [Memory and I/O map](memory-map.md) — the short stability-classified
  summary of the same hardware contract
* [RE notes: Unbanked RAM map](../re-notes/unbanked-ram-map.md) — the
  evidence trail for every region above, plus the empirical procedure for
  validating a scratch region
* [RE notes: OS internals](../re-notes/os-diposb.md) — boot chains,
  kernel installation, the stub arena
* [RE notes: Interrupts](../re-notes/interrupts.md) — IRQ/NMI and the
  banked-call envelope
* [BDOS calls](bdos.md) — the `CALL 0005h` service set the `F1EB` table
  dispatches
* [DIPOS-B extensions](extensions.md) — the `F3h`-`FFh` functions the
  `F1D1` table dispatches
* [Barcode reader](barcode.md) — the decode-hook contract in full
* [Program file formats](program-formats.md) — the `0xCF81` COM limit and
  the `D081` ceiling
* [Commstar application API](commstar-api.md) — the entry points whose
  buffers must be unbanked
