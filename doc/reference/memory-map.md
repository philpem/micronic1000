# Memory and I/O map

**On this page:** The programmer's reference for the Micronic 1000
memory model — banked vs fixed RAM, the `RST 10h` inter-bank call, the
shadow stack, the memory region table, stacks and heap, I/O port map,
latch-bit usage, and the rules for writing resident code. Intended for
anyone developing or patching code that must live in unpaged RAM.

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

All three require explicit pointer-mapping rules. A plain pointer into the
lower window changes meaning when the bank changes. Use fixed RAM for a
pointer dereferenced under another bank unless the API explicitly copies
the data, restores the caller's bank, or carries a bank/address descriptor.

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

For the evidence trail behind the unbanked region table, see
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

For evidence tags and the full derivation record, see
[RE notes: Memory and I/O evidence](../re-notes/memory-and-io-evidence.md).

---

## 1. The banked memory model

The Z80's 64K address space is split in half.

| Range | Size | Behaviour |
|---|---:|---|
| `0000`-`7FFF` | 32K | **Bank window.** Contents selected by port `47h`. |
| `8000`-`FFFF` | 32K | **Fixed battery-backed SRAM.** Always mapped, in every bank. |

The split is CONFIRMED and visible in every bank-aware routine — the clearest
single witness is the BDOS DMA test branching on `address >= 0x8000`
(see [§2.5](#25-the-rule-and-two-independent-corroborations)).

### 1.1 What selects a bank

A bank is selected by writing its number to **port `47h`**, and the
firmware always mirrors that write into the shadow byte
**`ram:F791`**. The canonical setter is four instructions and carries a
`DI`/conditional `EI` wrapper. CONFIRMED, byte-verified.

Three consequences for a programmer:

* **`ram:F791` is authoritative, not advisory.** Every dispatcher in the
  firmware reads `F791` to learn the current bank rather than reading the
  port back. If you switch banks yourself and do not update `F791`, the
  next `RST 10h` will compare against a stale value and take the wrong
  branch. CONFIRMED.
* **Bank switches run with interrupts disabled.** The setter does `DI`
  before the `OUT` and re-enables only if the interrupt-enable shadow
  `ram:FFA8` is non-zero. CONFIRMED.
* **The switch is instantaneous and total.** There is no partial or
  windowed mapping: the whole of `0000`-`7FFF` changes at once, including
  the code you are executing if you are executing below `8000`. This is
  why the bank helpers themselves live at `F180`+ in fixed RAM.

Derivation and site catalogue: see
[RE notes: Memory and I/O evidence](../re-notes/memory-and-io-evidence.md).

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
bank sweeper both count `C = 0x41` downward, and the RAM presence scan
counts `B` up from `1` and stops at `0x41`. CONFIRMED. That is 65 possible
banks; how many are populated on a given machine is discovered at boot, not
assumed.

### 1.3 What every bank has in common

Three things are guaranteed present no matter which bank is selected,
because the firmware puts them there:

**Page zero.** `ram:F438` (`Boot_BankWalkInit`) walks banks `40h` down to
`01`, selecting each in turn and writing the fixed vectors (`0000: JP F238`,
`0005: JP F180`, etc.) into it. CONFIRMED, byte-verified. `ROM01:0000` and
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
`0005` onward** — only `0000` differs. Because every target is `>= F180`,
i.e. in the fixed upper 32K, an interrupt or a `CALL 0005h` lands in
mapped code from any bank. `IM 1` is set at `ROM00:22EC` (`ED 56`).

Note the `0018` row: the `RST 10h` dispatcher is 15 bytes and runs
straight through the `RST 18h` slot, which holds `D7` (`RST 10h`) at
`0018`. `RST 18h` is not a usable restart on this machine.

**The chain pointer at `7FFC`.** The last word of each bank's window
points at that bank's boot-load record chain; the boot code reads it with
`LD HL,(7FFC)` twice, once per ROM bank. CONFIRMED at `ROM00:703C` and
`ROM00:7047`. See [RE notes: OS internals](../re-notes/os-diposb.md).

Boot installer listing and byte comparisons: see
[RE notes: Memory and I/O evidence](../re-notes/memory-and-io-evidence.md).

### 1.4 Which banks hold RAM

At cold boot the firmware pattern-tests every bank and records the result
as a **per-bank presence bitmap at `ram:FEB0`-`FEEF`**, one byte per bank
for banks `01`-`40`, each byte a 4-bit mask of the bank's four 8K pages.
A second pass rescans 63 entries comparing each against `0Fh` (all four
pages good). CONFIRMED.

Summary cells: `ram:FEA7`/`FEA8` bank range, `FEA9`/`FEAA` page counts,
`FEAB` the RAM-size word, `FEAF` `g_bRamBankBitmap`.

Pattern-test trace and addresses: see
[RE notes: Memory and I/O evidence](../re-notes/memory-and-io-evidence.md).

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
targets and deferred-call records. The arena is initialised by
`Kernel_InitCopyData` replicating one 4-byte template across all 281
slots. **Template is `21 01 00 C9` — `LD HL,0001; RET`**, so an
*uninstalled* slot returns `HL = 1` and does nothing. A slot only becomes
`{D7, bank, lo, hi}` when a boot-chain `fn=2` record installs it.

**Runtime thunk-patching — RESOLVED/WITNESSED 2026-09-19 (CONFIRMED).**
The `EE00-EE4F` 20-slot arena is a sub-range of the above (`ED1C-F17F`).
Both DIP type-0 blocks and COM programs can write `{D7,bank,addr}` stubs
into it. See [RE notes: OS internals](../re-notes/os-diposb.md) for the
full account including the emulator witness.

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
jump**: the callee's `RET` returns to whoever `CALL`ed the stub.

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
  operand at `D772`-`D773` is written at runtime from the kernel's
  jump-vector slot (`ram:F274` = `JP F41B`, the bank setter of
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

The cursor is reset to `E3B1` by a combined reset-and-select routine.
CONFIRMED, byte-verified.

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

Cursor reset bytes and arithmetic derivation: see
[RE notes: Memory and I/O evidence](../re-notes/memory-and-io-evidence.md).

### Pointer mapping and bank-aware exceptions {#25-the-rule-and-two-independent-corroborations}

**The caller's bank is restored when the callee returns, but it is not
mapped while the callee runs.** Between `ram:D75F` and `ram:D762` the
lower 32K belongs to the callee. Therefore:

> A plain pointer dereferenced after remapping the lower window must
> address fixed RAM (`>= 8000h`) unless the callee explicitly handles
> the pointer's bank. Follow the individual API contract.

Two places in the firmware confirm this from opposite directions.

**The Commstar entry points.** Every buffer the firmware itself hands to
a session entry point is unbanked — not one is below `8000`. CONFIRMED —
see [Commstar application API](commstar-api.md).

**The BDOS.** The firmware tests the caller's DMA address and bounces the
sector through fixed RAM *exactly when* it is banked:

```
ram:f510  2A A3 FF      LD   HL,(FFA3)    ; caller's DMA address
ram:f513  7C            LD   A,H
ram:f514  FE 80         CP   80h
ram:f516  D0            RET  NC           ; >= 8000h: use the buffer in place
ram:f517  11 FF FE      LD   DE,FEFF      ; < 8000h: bounce 128 bytes
ram:f51a  D5            PUSH DE
ram:f51b  01 80 00      LD   BC,80h
ram:f51e  CD 98 F4      CALL F498         ; Kernel_MemCopy (bank-aware)
ram:f521  E1 C9         POP HL; RET
```

CONFIRMED, byte-verified at `ROM00:3A2D`. The firmware pays for a 128-byte
copy so that this BDOS interface can accept a banked DMA pointer.
The FCB helper at `ram:F4EB` similarly copies a lower-window FCB through
fixed RAM using `ram:F498`; its caller at `ROM00:0877` precedes drive
resolution. These are **CONFIRMED bank-aware exceptions**, rechecked
2026-09-20, not a requirement that all BDOS callers supply fixed buffers.

**The barcode decode hook carries a bank and address.** Its thunk can
select the decoder's bank; it is not a plain unqualified callback pointer.
See [the hook socket](barcode.md#the-socket). Do not generalize these
exceptions to Commstar or other APIs whose buffer contract requires fixed RAM.

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
image of `0xCF81` bytes. See [Program file formats](program-formats.md).

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
    `F68D` is the first byte after the resident kernel image. The earlier
    round-1536-byte-arena explanation is withdrawn: the
    [unbanked-RAM investigation](../re-notes/unbanked-ram-map.md) rejects it.
    Lack of observed writes in the tested workloads does not allocate
    these spans to applications or establish safety on untested paths.

!!! danger "`E48C`-`E6FF` is live Commstar session state"
    Staging data there has already caused a real bug in this project
    (the 561-byte upload anomaly). The named cells and the failure
    analysis are in
    [RE notes: Unbanked RAM map](../re-notes/unbanked-ram-map.md#do-not-touch).

### 3.3 Nothing in fixed RAM survives a cold boot

`SelfTest_page_test_4banks` (`ROM00:2530`) destructively pattern-tests the
whole of `8000`-`FFFF` — four 8K pages from `8000` with a `2000` stride,
four fill/verify passes each — and is reached from `Boot_entry` at
`ROM00:01BB` (`C3 30 25`). CONFIRMED.

**It is not unconditional.** `ROM00:01A3` `JP Z,024Dh` takes the warm path
whenever `ram:F81C` holds `55h`, jumping clean over `01A6`-`024C` — which
contains the RAM test at `01BB`, the decode-hook install at `022F` and the
kernel recopy at `023E` alike. That is why the kernel is reinstalled and the
boot chains re-run **on a cold start**: their destinations have just been
erased. Battery backing preserves fixed RAM across power-*off* and across a
warm reset; only a cold start erases it.

---

## 4. Stacks and heap

There are three stacks, and no heap.

### 4.1 The system stack

`SP = F81A`, growing **down** into `F79A`-`F819` (128 bytes) before it
reaches the I/O port shadows at `F780`.

CONFIRMED: `LD SP,F81A` at `ROM00:0175`, `01A6`, `01D4` and `024D` — and
those are the only genuine `LD SP,nn` sites in `ROM00` besides the barcode
capture trick at `13BF` and the loaded-program stack at `71A9`.
`ROM00:024D` is the BDOS function 0 (system reset) handler, so a warm boot
re-establishes it.

**Usable extent: 128 bytes**, `F819` down to `F79A`. Below that are the
port shadows (`F780`-`F799`), and below *those* the currently unidentified
`F68D`-`F77F`. A stack excursion past `F79A` therefore corrupts the bank
shadow `F791` and the link control shadow `F794` before it reaches anything
harmless — which is a fast way to a machine that has forgotten which bank it
is in.

### 4.2 The loaded program's stack

`SP = D681`, growing **down** into `D481`-`D680` (512 bytes) before it
reaches module B's workspace.

CONFIRMED: `LD SP,D681` at `ROM00:71A9`, which is `ram:D7FA` at runtime.
The full entry sequence:

```
ram:d7f6  CD B5 D6      CALL D6B5     ; reset the cross-bank shadow stack,
                                      ;   then select the bank in A
ram:d7f9  E1            POP  HL       ; HL = program entry point
ram:d7fa  31 81 D6      LD   SP,D681
ram:d7fd  E9            JP   (HL)
```

CONFIRMED, byte-verified at `ROM00:71A5`-`71AC`. A program therefore starts
with a clean 512-byte stack **and** a freshly reset cross-bank shadow stack.

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
  `ram:E3BD` (`g_pProgramLoadCeiling`) has exactly **one writer** and
  **two readers**, both in the ROM01 loader, both used in a subtraction to
  compute how much room a program image has. It is a fence, not a break.
* **Every buffer in the map is at a fixed address.** The bounce buffers,
  the LCD framebuffer, the capture buffer, the session objects, the stub
  arena — all are placed by boot-chain records with literal destinations.
  Nothing in the map is described by a length-plus-base pair that changes.

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
  CONFIRMED at `ROM00:716D`.

Neither is the loader's ceiling. The real limit is `D081`, held in
`ram:E3BD`, and `D081`-`D680` is occupied by module B, its workspace and
your own stack. A program that trusts `(0006) - 1` as top-of-memory will
believe it owns 1536 bytes that it does not.

**Use `D080` as the last usable byte of your image**, or read
`ram:E3BD` if you want the firmware's own number.

---

## 5. I/O port map

For the byte-level methodology, false-positive analysis, site catalogues and
register-indirect table, see
[RE notes: Memory and I/O evidence](../re-notes/memory-and-io-evidence.md).

Direction is as the firmware uses it, not necessarily as the hardware
decodes it.

| Port | Name | Dir | Function | Evidence |
|---:|---|:--:|---|---|
| `00h` | `KBD_SENSE` | R | Keyboard matrix sense, low 6 bits | CONFIRMED |
| `02h` | `KBD_DRIVE` | W | Keyboard drive / configuration latch. Reset writes `FDh`; scan drives `3Fh`, cleared by `00h`. | CONFIRMED as keyboard; non-keyboard uses **Provisional** |
| `03h` | `LCD_DATA` | W | HD61830 data byte | CONFIRMED |
| `04h` | `IRQ_MASK` / `OUT_LATCH` | W | Interrupt-enable mask, **active low** (a set bit in the argument enables a source). Also carries power-latch bits. Shadow `F784`. | CONFIRMED |
| `05h` | `STATUS_IN` | R | Interrupt / status byte, active low. Polled by `Kernel_WorkerPollPort5`; also read at reset as boot-condition byte. | CONFIRMED |
| `07h` | `CTRL_07` | W | Control latch, shadow `F786`. **Only bits 0 and 1 are ever manipulated.** | CONFIRMED; function **unknown** |
| `08h` | `RTC_ADDR` | W | HD146818 register-address latch | CONFIRMED |
| `23h` | `LCD_REG` | W | HD61830 register/command select | CONFIRMED |
| `28h` | `RTC_DATA` | R/W | HD146818 data, paired with `08h`. See [RTC](../re-notes/rtc.md) | CONFIRMED |
| `2Ah` | `CTL_LATCH_2A` | W | Peripheral control latch, shadow `F78B`. Bits 1, 4 and 5 individually managed. Barcode front end and `Link_PortSelect`. | CONFIRMED as shared latch; bit meanings **Provisional** |
| `2Bh` | `SOUND` | W | **Beeper.** `Sound_2bWrite` / `Sound_Off`. This is a physical port, **not** the `2Bh` *wire ID* in the `FE83` device table. | CONFIRMED |
| `2Ch` | `CTL_LATCH_2C` | W | Control latch, shadow `F78D`. Per-bit assignments in [separate table](#port-2ch-bits) below | CONFIRMED |
| `2Dh` | `EXTBUS_EDGE` | R | Barcode-pen edge/level input. Eight read sites, all inside the capture front end. | CONFIRMED |
| `33h` | *unknown* | R | **Single access**: `ROM00:1ED9` `IN A,(33h); RET` inside the LCD driver block. Candidates: LCD status/busy or incomplete alias. | **OPEN** |
| `46h` | `LCD_CONTRAST` | W | LCD contrast DAC. Written via `LD C,46h` from `Lcd_Init` and power adjusters. Cold boot overwrites to `70h`. | **LIKELY** (owner-confirmed: stock `70h` is near-black; Sun contrast key adjusts it) |
| `47h` | `BANK_SEL` | W | 32K bank select, shadow `F791` | CONFIRMED |
| `48h` | `IR_STROBE` | W | Two-bit output, driven `0`,`1`,`2`,`3` in sequence by diagnostic and link selftest routines. Paired with `49h`. | CONFIRMED |
| `49h` | `IR_SENSE` / `BOOTKEYS` | R | Low 2 bits read back after each `48h` write (loopback/presence test); also read at reset to select boot path. | CONFIRMED |
| `4Ah` | `LINK_CTRL` | W | External-link control latch, shadow `F794`. Bits 0/1/4/5/6/7 are driven; **bits 2 and 3 never written**. Bit 1: port select (CONFIRMED). | CONFIRMED; electrical meanings **Provisional** |
| `4Bh` | `LINK_STATUS` | R | Link status, polled in block Tx/Rx/Probe/WaitReady. Bit 4 = "receive pending". | CONFIRMED; bit assignments **Provisional** |
| `4Ch` | `LINK_CMD` | W | Link command latch; only write is `81h` in `Link_Present`. | CONFIRMED |
| `4Dh` | `LINK_TXD` | W | Link TX data byte, sole site `ROM00:32B6`. | CONFIRMED |
| `4Eh` | `LINK_RXD` | R | Link RX data byte, sole site `ROM00:338C`. | CONFIRMED |
| `4Fh` | `LINK_PROBE` | W | Device probe/reset; sole write is `1Fh` in `Link_Probe`. | CONFIRMED |

**No other port is accessed anywhere in either ROM image or in any
RAM-resident module.** The untouched ranges are `01h`, `06h`, `09h`-`22h`,
`24h`-`27h`, `29h`, `2Eh`-`32h`, `34h`-`45h`, and everything above `4Fh`.
That is a statement about the firmware, not about the hardware: a port this
firmware never uses may still be decoded, and the address decoding may well
be partial — the `03h`/`23h`, `08h`/`28h` and `2Ah`/`2Ch` pairings suggest
only some address lines are compared. **SUSPECTED** for the partial-decode
inference; a hardware read of an unused port would settle it.

### Interrupt sources {#interrupt-sources}

**CONFIRMED.** `04h` is the enable mask and `05h` the pending register,
both **active low**, and both are only six bits wide in practice.

`Kernel_WorkerPollPort5` reads `05h`, ORs it with the mask from `F784`,
complements the result to get *pending and enabled*, and walks a table
of `{bitmask, handler}` triples at `ram:FD84`, terminated by `80h`:

| bit | mask | handler | source |
|---|---|---|---|
| 0 | `01h` | `Kbd_ScanMain` | **keyboard** |
| 1 | `02h` | `ROM00:2206` | **RTC** — reads HD146818 registers `0Ch` then `0Bh` |
| 2 | `04h` | `ROM00:31B6` | **the link controller** — see [link interrupt](../re-notes/interrupts.md#link-interrupt) |
| 3 | `08h` | `ROM00:2365` | **LIKELY** power/battery; shared with bit 4 |
| 4 | `10h` | `ROM00:2365` | same handler as bit 3 |
| 5 | `00h` | none in ROM | filled at runtime by barcode front end |
| 6, 7 | — | — | no slot exists |

Sleep-wake evidence confirming bit 0 is the keypad: see
[RE notes: Interrupts – sleep wake](../re-notes/interrupts.md#sleep-wake).

### Which latch bits the firmware ever touches {#latch-bit-usage}

Every output latch is read-modify-written through a RAM shadow, so a bit is
only touched by the routine that owns it, and the immediate mask names the
bit. This table is the exhaustive result of matching that idiom
(`LD A,(shadow)` / `AND`-`OR`-`XOR n` / `LD (shadow),A` / `OUT (p),A`) across
`ROM00`. **`o` = some instruction sets it, `-` = cleared, `x` = both,
`.` = no instruction ever touches it individually.**

| port | shadow | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 | whole-byte writers |
|---|---|---|---|---|---|---|---|---|---|---|
| `02h` `KBD_DRIVE` | `F782` | - | - | . | . | . | . | . | . | `017D` `0188` `019B` `1759` `176B` `1A47` `3B51` |
| `04h` `IRQ_MASK` | `F784` | . | . | x | - | - | . | . | x | `01B5` `023C` `177F` `22F2` `2428` `2851` `28DA` `28FB` |
| `07h` `CTRL_07` | `F786` | . | . | . | . | . | . | x | - | `17A0` `28F2` |
| `2Ah` `CTL_LATCH_2A` | `F78B` | . | . | o | o | . | . | x | . | `0154` `0255` `14F2` `1541` `179D` |
| `2Ch` `CTL_LATCH_2C` | `F78D` | . | . | - | x | . | . | x | x | `1786` `3487` `34B5` |
| `4Ah` `LINK_CTRL` | `F794` | x | x | x | x | . | . | x | x | — |

Two negatives bound searches:

* **`LINK_CTRL` bits 2 and 3 are the only ones no ROM instruction ever
  writes.** So the untried space on that latch is exactly two bits.
* **`CTRL_07` uses only bits 0 and 1.** It is a two-bit output, not an
  eight-bit one.

Pattern-matching method and caveats: see
[RE notes: Memory and I/O evidence](../re-notes/memory-and-io-evidence.md).

### Port `2Ch` bits {#port-2ch-bits}

Every write is a read-modify-write through the shadow at `F78D`, so a bit is
only ever touched by the routine that owns it. **No ROM instruction ever sets
bits 2, 3, 6 or 7.**

| bit | reading | confidence |
|---|---|---|
| 0 | An output strobe on the external port — short fixed-width pulse in the barcode block | CONFIRMED (width); **OPEN** (what it strobes) |
| 1 | An enable asserted around reads of `2Dh` | CONFIRMED (set-then-read ordering); **OPEN** (drive/wand-power/direction) |
| 2, 3 | unused, or not brought out | **OPEN** |
| 4 | **LIKELY the LCD backlight** — toggles in the keyboard handler, switched off on power-down | **LIKELY**; corroborated by MAME inference |
| 5 | **IR port select** — moves with `LINK_CTRL` bit 1 | CONFIRMED |
| 6, 7 | unused, or not brought out | **OPEN** |

Per-site evidence and exerciser plans: see
[RE notes: Memory and I/O evidence](../re-notes/memory-and-io-evidence.md).

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

---

## 6. Writing code that lives in unpaged RAM

Two kinds of resident code are in scope: a **barcode decoder module**
that the ROM calls after each scan, and a **patch to an OS function**.
The fixed-RAM placement described here avoids bank-mapping dependencies.
The barcode hook also supports a bank/address thunk; its decoder and result
buffer must follow the [hook contract](barcode.md#the-decode-hook).
A direct OS-vector patch must remain mapped when called.

### 6.1 Where to put it

Ranked, from
[RE notes: Unbanked RAM map](../re-notes/unbanked-ram-map.md#safe-for-scratch):

1. **`C000`-`D080` (4225 bytes)** — a candidate only if your image and
   runtime allocations leave it unused. A COM larger than `BF00h` bytes
   reaches `C000h`; a DIP can place a block there explicitly. Reserve the
   space in your application layout and check existing resident hooks.
2. **`8006`-`BFFF` (16378 bytes)** — same argument, four times the room,
   but it is the part of the TPA a growing program image reaches first.
   Use it only when you know the image, buffers, stacks, and resident
   allocations leave the chosen subrange free. No allocator reserves it.

Everything else that *looks* free is not:

* `F68D`-`F77F` remained unwritten in the recorded workloads, but is below
  the system stack and port shadows. The measured low-water mark is not
  a worst-case guarantee. Do not use it as general application scratch.
* `FFA9`-`FFFF` (87 bytes) is big enough for a signature word, and is
  immediately adjacent to a densely packed BIOS variable block.
* `FD64`-`FD83` and `FE45`-`FE82` **look** unreferenced and are not:
  they are the tails of the countdown-timer table at `FD5C` and the
  per-link frame-sequence table at `FE43`.

And the constraint that catches everyone: **`ROM00:2530` pattern-tests
the whole of `8000`-`FFFF` on every cold boot.** Nothing you place in
fixed RAM survives a reset unless something re-materialises it.

### 6.2 Barcode decoder module

The hook socket is a four-byte `RST 10h` stub at `ram:FBC0`.
The ROM ships a **discard** hook; the simplest correct arrangement is to
put your decoder at `C000`+ so it is valid in every bank. On entry the
hook receives a pointer to the width-table cells at `FBB9`/`FBBB`
(pointer and count) and returns to `ROM00:1468`.

The register-level contract, capture buffer layout, and full dispatch
mechanics are in:
* [Barcode reader](barcode.md) — the programmer-facing contract
* [RE notes: Barcode capture](../re-notes/barcode-capture.md) — listings,
  timing derivation, and the uncapped-count bug

### 6.3 Patching an OS function

The resident kernel dispatches BDOS calls through a **word table in
unbanked RAM**, which makes it a real hook point rather than a
theoretical one. There is one table base and two windows onto it:

| Table | Address | Index | Covers |
|---|---|---|---|
| CP/M range | `ram:F1EB`+ | `F1EB + 2×fn` | BDOS functions from `00h` |
| Extension | `ram:F1D1`-`F1EA` | `F1EB + 2×fn − 200h` (via `B = FFh`) | DIPOS-B functions `F3h`-`FFh` |

Key facts for a patch author:

* **A patch is a 16-bit store**: write your handler's address into
  `F1EB + 2 × fn` (CP/M range) or `F1D1 + 2 × (fn − F3h)` (extension).
  The dispatcher will route the call through the same `F382` envelope it
  uses for a ROM handler.
* **Your handler is entered with bank 0 selected.** A handler at `C000`+
  works unconditionally.
* **The patch survives a warm boot, and dies on a cold one.** The kernel
  recopy (`ROM00:02FE` → `ram:F180`) runs **only on a cold start**.
* **Special-cased functions bypass the table.** Functions `2Dh`, `2Eh`,
  `30h`, `62h`, `68h` and `69h` are dispatched by an explicit compare
  chain *before* the table lookup is reached.

For the full envelope listing, persistence proof, and the "do not call
unassigned functions" warning, see
[RE notes: OS internals](../re-notes/os-diposb.md).

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

For the worked example (`ram:E5C2`), see
[RE notes: Memory and I/O evidence](../re-notes/memory-and-io-evidence.md#worked-example-rame5c2).

---

## Related

* [RE notes: Unbanked RAM map](../re-notes/unbanked-ram-map.md) — the
  evidence trail for every region above, plus the empirical procedure for
  validating a scratch region
* [RE notes: OS internals](../re-notes/os-diposb.md) — boot chains,
  kernel installation, the stub arena
* [RE notes: Interrupts](../re-notes/interrupts.md) — IRQ/NMI and the
  banked-call envelope
* [RE notes: Memory and I/O evidence](../re-notes/memory-and-io-evidence.md) —
  byte-level derivation for every port and cell
* [BDOS calls](bdos.md) — the `CALL 0005h` service set the `F1EB` table
  dispatches
* [DIPOS-B extensions](extensions.md) — the `F3h`-`FFh` functions the
  `F1D1` table dispatches
* [Barcode reader](barcode.md) — the decode-hook contract in full
* [Program file formats](program-formats.md) — the `0xCF81` COM limit and
  the `D081` ceiling
* [Commstar application API](commstar-api.md) — the entry points whose
  buffers must be unbanked
