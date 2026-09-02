# Unbanked RAM map (`8000`-`FFFF`) — what is occupied, what is safe

The lower 32K of the address space is banked (`ROM00`, `ROM01`, RAM
pages); the upper 32K, `8000`-`FFFF`, is **fixed battery-backed SRAM**
that every bank sees. Because `RST 10h` switches the lower bank before
jumping to the callee (`ROM00:0010` → `ram:D74B`), **any buffer handed
across a Commstar or kernel entry point must live in this fixed 32K** —
the caller's page is not mapped while the callee runs.

That makes "where is it safe to put a buffer?" a load-bearing question,
and getting it wrong has already cost this project a real bug (the
561-byte upload anomaly; see [Commstar evidence](commstar-evidence.md)
and the "do not touch" section below). This page is the answer:
every region of `8000`-`FFFF`, what lives there, and how we know.

## How this map was built

1. **Instruction scan.** Every instruction Ghidra has disassembled in
   `ROM00`, `ROM01` and the RAM-resident modules (21,113 instructions)
   was walked; each operand or reference resolving into `ram:8000`-`FFFF`
   was recorded with its read/write class. 1,117 distinct addresses.
2. **Raw opcode scan** of both ROM images for `01/11/21/22/2A/31/32/3A
   lo hi` and `ED 43/4B/53/5B/63/6B/73/7B lo hi`, independent of
   disassembly, to cover the ROM bytes Ghidra has not yet classified
   (`ROM00` is 61% disassembled, `ROM01` 37%).
3. **The boot-load chains** (`analysis/decode_chains.py`, and the
   pre-chain copies in `AnalyseMicronicRom.java` pass 2), which give
   the large occupied blocks with exact destinations and lengths.
4. **Existing repo findings** — Ghidra labels, [OS
   internals](os-diposb.md), `doc/research/TASKS.md`.

!!! warning "`analysis/battery_ram.bin` is not a hardware dump"
    It is a **dump of the Ghidra `ram` block after
    `FillBatteryRam.java`** — a *simulation* of a clean cold boot, not a
    capture from a real machine. CONFIRMED: every ROM→RAM copy in it
    matches the ROM bytes exactly, `ED1C`-`F17F` holds
    `21 01 00 C9` repeated (the pattern `FillBatteryRam.fillEdArea`
    writes), and all ten of its `seedSystemVariables` cells hold exactly
    the seeded values (`FC05=70`, `FEAF=FF`, `F784=FF`, `F78B=20`, …).
    **Zero bytes in that file are therefore evidence of nothing** —
    neither that a cell is unused nor that it is zero at rest on
    hardware. Several regions that are all-zero in it are proven live
    below.

## Region table

No gaps: the table covers `8000`-`FFFF` contiguously.

| Range | Size | Contents | Tag | Evidence |
|---|---:|---|---|---|
| `8000`-`D080` | 20609 | **Upper TPA** — the part of a loaded program's image above the bank window. Free after a program smaller than `0x7F00` loads. | LIKELY | `ROM00:7052` `21 81 D0 / 22 BD E3` = `LD HL,D081; LD (E3BD),HL` sets `g_pProgramLoadCeiling` = `D081`; COM limit `0xCF81` = `D081-0100` ([program formats](../reference/program-formats.md)). No disassembled instruction anywhere references `8006`-`D080`. |
| `D081`-`D2CA` | 586 | Workstation module B (`g_apScreenHandlerTables`, `g_apLoadRunHandlers` at `D0F0`, `commstar_state_names` at `D0CF`) | CONFIRMED | boot chain `ROM01:7E23`: memcpy `7BCB → D081`, `0x24A` |
| `D2CB`-`D480` | 438 | Module B workspace, zeroed at boot. Live cells: `D2DC` `g_formCtxW`, `D2DE` `g_formIdxW`, `D368`-`D36E` program-input globals, `D39B` `g_pProgramBlockDescriptor`, `D465` `g_wLogonModeEnableMask` | CONFIRMED | boot chain `ROM01:7E2B`: memset `D2CB..D480` |
| `D481`-`D680` | 512 | **Stack of the running loaded program**, grows down from `D681` | CONFIRMED | `ram:D7FA` (`RunLoadedProgram`) `31 81 D6` = `LD SP,D681`, then `JP (HL)`; byte-verified at `ROM00:71A9`. Ghidra records 14 call-pushes landing at `ram:D67F`. |
| `D681`-`D892` | 530 | DIPOS dispatch block: syscall dispatch, boot-chain walker, `RST 10h` cross-bank thunk, `CoroutineTaskSwitch` | CONFIRMED | `ROM00:3BAA` `21 30 70 / 11 81 D6 / 01 12 02 / ED B0 / C3 81 D6` — LDIR `ROM00:7030 → D681`, `0x212` bytes, then jump into it |
| `D893`-`E0F3` | 2145 | Session module A (string/`RegFile` runtime library, `InlineTableDispatch` at `E0B2`) | CONFIRMED | boot chain `ROM00:7D74`: `01 00 CE 73 93 D8 61 08` = memcpy `73CE → D893`, `0x861` |
| `E0F4`-`E103` | 16 | BDOS-call parameter page | CONFIRMED | boot chain `ROM00:7D58`: memcpy `7242 → E0F4`, 16 |
| `E104`-`E22C` | 297 | Module A2 (auxiliary jump/handler block) | CONFIRMED | boot chain `ROM00:7D7C`: `01 00 2F 7C 04 E1 29 01` = memcpy `7C2F → E104`, **`0x129`** |
| `E22D`-`E2F9` | 205 | Misc session config; `E22D` = `g_bSessionState` | CONFIRMED | boot chain `ROM00:7D66`: memcpy `7301 → E22D`, `0xCD` |
| `E2FA`-`E36E` | 117 | Page-zero image copy | CONFIRMED | boot chain `ROM01:7E15`: memcpy `0080 → E2FA`, `0x75` |
| `E36F`-`E370` | 2 | **`RST 10h` shadow-stack cursor** | CONFIRMED | `ram:D6B5` `E5 21 B1 E3 22 6F E3` = `PUSH HL; LD HL,E3B1; LD (E36F),HL`; `ram:D74D`-`D76C` push/pop 3-byte frames through it |
| `E371`-`E3B0` | 64 | **Shadow-stack body** — grows *down* from `E3B1`, 3 bytes per cross-bank call (`A`, `D`, `E`) | CONFIRMED | `ram:D750`-`D755`: `DEC HL; LD (HL),A; DEC HL; LD (HL),D; DEC HL; LD (HL),E` |
| `E3B1`-`E3C0` | 16 | 32-bit register file used by module A's `RegFile_*` ops; `E3BD` = `g_pProgramLoadCeiling` | CONFIRMED | `ram:DC37` `LD DE,E3B1`; `ROM00:7055` `22 BD E3` |
| `E3C1`-`E3FF` | 63 | Zeroed workspace (`E3C2`, `E3C4` live) | CONFIRMED | boot chain `ROM00:7D6E`: memset `E3C1..E704` |
| `E400`-`E48B` | 140 | Commstar session page head: `E400` `commstar_session_page`, `E44A` `g_wSessionStreamTerminal`, `E471` `session_block_cur`, `E488` (24 reads / 40 writes) | CONFIRMED | ditto; `ROM00:4693` `LD (E488),HL` etc. |
| `E48C`-`E6FF` | 628 | **Live Commstar session state** — see "do not touch" | CONFIRMED | ditto; named cells listed below |
| `E700`-`E704` | 5 | tail of the same memset | CONFIRMED | `ROM00:7D6E` |
| `E705`-`EC6C` | 1384 | Workstation/session state, zeroed at boot: `EC00` `workstation_state_page`, `EC41` `g_wEventWord`, `EC49` `g_pScreenDesc`, plus `E720`-`EBFB` link/session cells | CONFIRMED | boot chain `ROM01:7E1D`: memset `E705..EC6C` |
| `EC6D`-`ED1B` | 175 | **Not written by any boot chain, but live at runtime**: `EC71` `g_acRequestedProgramName`, `EC97`/`EC98` logon indices, `EC99`/`ECA2`/`ECAB`/`ECB4` logon user/password/group/phone, `ECC9` `g_wProgramLoadState`, `ECCB` `g_acLoadedProgramName`, `ECD8`/`ECDA` program bank base/limit, `ECDC` program header, `ECEA` block descriptors | CONFIRMED | reads/writes from `ROM01:0A1D`, `0D54`, `0F90`, `0E05` and the `C-INIT-COMMS` string arguments |
| `ED1C`-`F17F` | 1124 | Deferred-call / far-call stub arena: 281 × 4-byte `{RST10h, bank, target}` stubs, also used as UI vtable targets | CONFIRMED | fn=2 chain records in both banks; see [OS internals](os-diposb.md#queue-purpose-the-fn2-records) |
| `F180`-`F68C` | 1293 | Resident kernel (BDOS gate, syscall envelopes, RST/NMI stubs, bank helpers) | CONFIRMED | `InstallKernelToRam` `ROM00:02FE`: `ROM00:369D → F180`, `0x50D` |
| `F68D`-`F77F` | 243 | **Unidentified.** No reference from either ROM or any RAM module. Sits between the kernel image end and the port shadows. | OPEN | absence of references only — see caveat below |
| `F780`-`F799` | 26 | I/O port shadows: `F780` p02, `F782` p02-cfg, `F784` p04, `F786` p07, `F78B` p2A, `F78D` p2C, `F791` `g_bBankShadowP47`, `F794` `g_bLinkCtrlShadow` | CONFIRMED | named, heavily read/written |
| `F79A`-`F819` | 128 | **System stack**, grows down from `F81A` | CONFIRMED | `31 1A F8` = `LD SP,F81A` at `ROM00:0175`, `01A6`, `01D4`, `024D`; 54 call-pushes recorded at `ram:F818` |
| `F81A`-`F8B7` | 158 | System variables: `F81C` `g_bWarmbootSig`, `F81D` `g_bBootmodeFlag`, `F81E`-`F82F`, `F8AE`-`F8B6` RAM-disk geometry (`F8B0`=`0100`, `F8B6`=`8000`, set at `ROM00:05A1`) | CONFIRMED | `ROM00:05A1`-`05BB` |
| `F8B8`-`F937` | 128 | **BDOS directory swap buffer** | CONFIRMED | `ram:F535` `2A A3 FF / 11 B8 F8 / EB / 01 80 00` = `LD HL,(FFA3); LD DE,F8B8; EX DE,HL; LD BC,80h; CALL KernMemCopy` |
| `F938`-`F9B3` | 124 | System/extension variables: `F958` `g_abExtResultEnv`, `F95C` `g_wExtResultCount`, `F95E` `g_abExtResultData`, `F99A` `g_abRtcAlarmRecord`, `F9A2` `g_abRtcTimeRecord` | CONFIRMED | named, referenced |
| `F9B4` | 1 | Barcode edge-sample count | CONFIRMED | `ROM00:1409` `LD (F9B4),A` (A = capped sample count, `CP 80h` at `140F`) |
| `F9B5`-`FBB4` | 512 | **Barcode-pen edge-timing capture buffer** — filled by `PUSH` from `SP=FBB5` downward, then reversed in place | CONFIRMED | `ROM00:13BB` `ED 73 BD FB` save SP; `13BF` `31 B5 FB` `LD SP,FBB5`; `1401` `PUSH HL` per edge; `1404` restore; `1415` `DD 21 B5 F9` `LD IX,F9B5`; `1419` `FD 21 B3 FB` `LD IY,FBB3` |
| `FBB5`-`FC05` | 81 | Barcode/system state: `FBB5` sample-loop counter and capture SP base, `FBBD` saved SP, `FBC0`-`FBC2` ext decode hook, `FBC5` `g_bActiveDevice`, `FBC6` `g_bActiveDrive`, `FBC9` `g_bEventFlags`, `FBD0` `g_wSysSavedSp`, `FC05` power-latch value | CONFIRMED | named, referenced |
| `FC06`-`FCA5` | 160 | **LCD framebuffer** (20 cols × 8 rows ASCII) | CONFIRMED | `ROM00:1D9F` `LD HL,FC06`; `1DE3`, `1DEE` |
| `FCA6`-`FD45` | 160 | **LCD shadow/compare buffer** (paired with the above) | CONFIRMED | `ROM00:1DA4` `LD HL,FCA6` immediately after `FC06`, compared byte-for-byte |
| `FD46`-`FD63` | 30 | RTC working area: `FD4A`-`FD4C` alarm fields, `FD50` `g_abRtcRegisterSnapshot` (10 B), `FD5C` `comm_work_table` | CONFIRMED | [RTC notes](rtc.md) |
| `FD64`-`FD83` | 32 | **Unidentified** (tail of the RTC/comms working area) | OPEN | absence of references only |
| `FD84`-`FD96` | 19 | Comms config table | CONFIRMED | `ROM00:22E9`/`2306` copy `ROM00:2352`, 19 bytes |
| `FD97`-`FE44` | 174 | Link/device state: `FDCA` `g_bWireId`, `FDD5` `g_bLinkState`, `FDEA` TX `{count, ptr}` descriptor, `FE0E`-`FE44` | CONFIRMED | named, referenced |
| `FE45`-`FE82` | 62 | **Unidentified** | OPEN | absence of references only |
| `FE83`-`FE92` | 16 | Device config copy A; `FE86` `g_bDeviceWireId4` | CONFIRMED | `ROM00:3237` `LD HL,FE83` ← `ROM00:3267`, 16 bytes |
| `FE93`-`FEA2` | 16 | Device config copy B (storage wires `C:`=`73`, `D:`=`72`) | CONFIRMED | `ROM00:3205`/`3223`/`3229` LDIR ← `ROM00:3257`, 16 bytes |
| `FEA3`-`FEAF` | 13 | Boot/sizing variables: `FEA7`/`FEA8` bank range, `FEA9`/`FEAA` page counts, `FEAB` RAM-size word (`FEA9`×`20h`), `FEAF` `g_bRamBankBitmap`. Owner-supplied: the user-entered serial number lives in this area. | CONFIRMED (cells) / LIKELY (serial) | `ROM00:2739` `LD (FEAB),HL`, `2598`/`25B5` `LD (FEAF),A`; serial per AGENTS.md owner statement |
| `FEB0`-`FEEF` | 64 | **Per-bank RAM-presence bitmap**, one byte per bank, banks `01`-`40` | CONFIRMED | `ROM00:267F` `21 B0 FE / 36 00`; `26C7` `78 FE 41 28 17 23 36 00` (`INC HL; LD (HL),0` per bank until `B==41h`); `26E3` `21 B0 FE / 06 3F` rescans 63 entries |
| `FEF0`-`FEFE` | 15 | Banked-call envelope save area (`FEF0`, `FEF6`, `FEF8`-`FEFE`) | CONFIRMED | `ram:F382` `LD (FEF6),HL`, `ram:F3E4` `bcret_load_fefe` |
| `FEFF`-`FF7E` | 128 | **BDOS sector bounce buffer** | CONFIRMED | `ram:F517` and `F52A` `11 FF FE` + `01 80 00` = `LD DE,FEFF; LD BC,80h; CALL KernMemCopy` |
| `FF7F`-`FFA2` | 36 | **BDOS FCB/directory bounce buffer** | CONFIRMED | `ram:F4F4` `21 7F FF` and `F50B` `11 7F FF`, each with `01 24 00` (`BC=24h`) |
| `FFA3`-`FFA4` | 2 | DMA / transfer address (CP/M-style) | CONFIRMED | `ram:F510`, `F523`, `F535`, `F543` all `LD HL,(FFA3)` |
| `FFA5`-`FFA7` | 3 | Current FCB pointer (+1 spare byte) | CONFIRMED | `ram:F4EC` `LD (FFA5),HL`, `F501`/`F508` read it |
| `FFA8` | 1 | Interrupt-enable shadow, tested by `Kernel_ConditionalEnableInterrupts` | CONFIRMED | `ram:F54F` `LD A,(FFA8); OR A; JP Z,…; EI` |
| `FFA9`-`FFFF` | 87 | **Unidentified** — top of RAM, immediately above the BDOS variable block | OPEN | absence of references only |

### The one thing that touches everything

`ram_page_test_4banks` (`ROM00:2530`, called unconditionally from
`reset_entry` at `ROM00:01BB`) **destructively pattern-tests the whole of
`8000`-`FFFF`**. CONFIRMED from the bytes: `06 04` `LD B,4` (four pages),
`21 00 80` `LD HL,8000`, `11 00 20` `LD DE,2000` (8K stride), then four
fill/verify passes (`55AA`, `AA55`, `H,L`, `~H,~L`) per page, advancing
`HL += 2000h` each time — `8000`, `A000`, `C000`, `E000`. The result
goes to `FEAF` and `FDB0`.

This is why the kernel is reinstalled from ROM (`InstallKernelToRam`) and
the boot chains re-run on every boot: the RAM test has just erased their
destinations. It runs **before** any program, so it does not threaten a
running test COM — but it does mean *nothing* in `8000`-`FFFF` survives a
cold boot except by being re-materialised, and it means a harness that
pre-seeds fixed RAM before `reset_entry` completes is wasting its time.

## Safe for scratch

Ranked. Each entry states what would falsify it.

### 1. `C000`-`D080` (4225 bytes) — first choice

The top of the unbanked TPA, immediately below the loader's program
ceiling.

**Why:**

* The loader's own ceiling is `D081` (CONFIRMED: `ROM00:7052`
  `21 81 D0 / 22 BD E3`), so nothing the loader places can reach above
  it, and module B starts exactly at `D081` — the boundary is a hard
  firmware constant, not an inference.
* Zero references. Across all 21,113 disassembled instructions in
  `ROM00`, `ROM01`, module A, module B, module A2, the dispatch block
  and the resident kernel, **no instruction reads or writes any address
  in `8006`-`D080`.** The only ROM instructions naming addresses in the
  whole `8000`-`D080` span are `LD HL,8000` in the RAM test
  (`ROM00:2539`/`256D`/`257B`/`25F3`/`262F`/`2670`) and its `55AA`/`AA55`
  patterns.
* It is above every buffer, stack, module and table the firmware places,
  and below module B — so it cannot be reached by either an overflow
  downward from `D681` or a growth upward from the kernel area.
* A test COM of ordinary size (say ≤ 16 KB) ends far below `C000`, so the
  region is not part of its own image either.

**Falsified by:** (a) a test image larger than `0xBF00` bytes — then
`C000` is inside the program's own image, and the scratch base must move
up or the image must shrink; (b) a cold boot occurring *after* the
scratch is seeded (the RAM test at `ROM00:2530` overwrites it); (c) a
computed or indirect write we have not found — see the honesty note
below, and run the empirical check.

### 2. `8006`-`BFFF` (16378 bytes) — when you need room

Same argument, four times the space, but it is the part of the TPA a
growing program image reaches **first**. Use it only when you know the
image size and can prove the gap. Falsified by exactly the same things,
sooner.

### 3. `FFA9`-`FFFF` (87 bytes) — for a marker or a counter

Unreferenced, at the very top of RAM, above the BDOS variable block
(`FEFF`-`FFA8`). Big enough for a signature word or a small counter,
nothing more. **Falsified by:** it is immediately adjacent to a densely
packed, exactly-sized BIOS variable block — a single off-by-one in
`ram:F4EB`-`F54D` (the bounce-buffer helpers) lands here. Treat a
corrupted marker as a signal, not a nuisance.

### Not recommended, despite looking free

* **`F68E`-`F77F` (242 B).** Unreferenced, but the system stack top is
  `F81A` and only 128 bytes of headroom sit between it and the port
  shadows at `F780`. A stack excursion past `F79A` runs into the shadows
  first and this region next. Anything you put here is a stack-depth
  canary, not scratch.
* **`FD64`-`FD83`, `FE45`-`FE82`.** Unidentified, but wedged between
  live RTC, comms-config and link-state cells in the most densely packed
  part of the map. The prior that they are structure padding of their
  neighbours is much stronger than the prior that they are free.

!!! note "\"Nothing references it\" is not \"it is free\""
    The instruction scan is bounded by disassembly coverage: `ROM00` is
    61% disassembled, `ROM01` 37%. An independent raw-opcode scan of both
    full ROM images found 405 byte sequences that *encode* an address in
    `8000`-`D080`; every one inspected was either a misalignment artefact
    (e.g. `21 01 00 C9` read starting at the `01` as `LD BC,C900`) or a
    **size** constant rather than an address — `ROM01:0AC5`/`0AF0`/`0AF9`
    clamp an image length to `0x8000`, and `ROM00:05A7` writes `0x8000`
    to `F8B6` as a bytes-per-track figure beside `F8B0 = 0x0100`. None
    was a memory access. That is a strong negative, not a proof. Verify
    empirically before betting a long experiment on it.

## Do not touch

### The Commstar session state, `E48C`-`E6FF` — the trap that already bit us

`analysis/boot_hw.py` staged upload chunks of up to 256 bytes at
`ram:E5C2` and reached `E6C1`, burying live session state. The failure
depended on image length, because the final short chunk only overwrote
the low end of the window and residue from the previous chunk survived
above it. See `doc/research/TASKS.md` and
[the Commstar API notes](../reference/commstar-api.md).

Named cells to keep clear of:

| Cell | Role |
|---|---|
| `E22D` | `g_bSessionState` |
| `E48C`-`E491` | session-state gate cells (17 reads at `E48C` alone) |
| `E52E` | `g_wSessionDeviceSelector` |
| `E530` | `g_wSessionTxPayloadLength` |
| `E534`+ | `g_abSessionTxPayload` |
| `E5BA` | `g_wSessionRxCapacity` |
| `E5BC` | `g_wSessionRxLogicalLength` |
| `E5BE`/`E5BF`/`E5C0`/`E5C1` | RX frame type / sequence / marker / opaque header |
| `E5C2`-`E641` | `g_abSessionRxPayload` — the **body of the 134-byte service-33 receive object at `E5BC`** |
| `E644` | `g_wSessionRxWorkingLength` |
| `E646` | `g_wSessionRxTypeOrResult` |
| `E648`/`E649` | RX sequence / link-id copies |
| `E64C` | `g_wSessionRxOperation` |
| `E681` | `g_wTxResult` — latches the `SessionRxByteLoop` error |
| `E69F`-`E6B3` | `SessionRxByteGet` (`ROM00:65C2`) pushback buffer |
| `E6A9`-`E6AA` | its 16-bit count — **never named literally in either ROM**, only ever touched as the high half of the `E6A9` word, which is why an address search misses it |
| `E6FF`/`E701` | `g_wSessRcv2` / `g_wSessRcv1` |

**On `E5C2` specifically.** The current `UPLOAD_BUFFER_MAX = 126` cap is
correct as a *fix for the overrun* — capped writes stop at `E63F`, below
`g_wSessionRxWorkingLength` at `E644`, and the harness restores the
window afterwards. But `E5C2` is still a poor choice of general scratch
even capped: it is the live RX payload object, so writing there is only
ever legitimate while the harness is deliberately *impersonating* a
service-33 receive. Keep `E5C2` for that one path and move any other
host staging to `C000`+.

### The two stacks

* **`D481`-`D680`** — the loaded program's stack, `SP = D681`
  (`ram:D7FA`). **`boot_hw.py` currently sets `UPLOAD_NAME_ADDR = 0xD600`**,
  which is `0x81` bytes below that stack top. The staged program name
  therefore sits *inside* the region the program's own stack grows into.
  It has not bitten yet because the name is written before the program
  runs and the stack is shallow at that point, but it is the same class
  of bug as the `E5C2` overrun and should move to the `C000`-`D080`
  region.
* **`F79A`-`F819`** — the system stack, `SP = F81A`
  (`ROM00:0175`/`01A6`/`01D4`/`024D`). 128 bytes of headroom before the
  port shadows at `F780`.

### The buffers that look like padding

* **`F9B5`-`FBB4`** — barcode edge-timing capture. Filled by `PUSH` with
  `SP = FBB5`, so it takes no ordinary `LD (nn)` reference and an
  address-literal search finds nothing in it. 504 of its 512 bytes look
  like a free hole.
* **`FEFF`-`FF7E`** (BDOS sector bounce) and **`FF7F`-`FFA2`** (FCB
  bounce). Same shape: only their base addresses appear as literals.
* **`F8B8`-`F937`** — BDOS directory swap buffer, likewise.
* **`FC06`-`FCA5`** and **`FCA6`-`FD45`** — the LCD framebuffer and its
  compare shadow.
* **`FEB0`-`FEEF`** — the per-bank RAM bitmap; the loop walks `HL`
  upward from the single literal `FEB0`.
* **`ED1C`-`F17F`** — the far-call stub arena. UI vtables point directly
  into it, and **no static reference to `ED1C` exists anywhere in either
  ROM**, so it too reads as unreferenced.

The pattern is the point: on this firmware, a base-address literal plus a
walked pointer is the normal idiom, so *unreferenced bytes are the rule
inside buffers, not the exception*.

### A corroborating detail worth knowing

The BDOS itself encodes the banked/unbanked distinction. `ram:F510`
(`BdosPrepWriteBuf`) reads the DMA address, and:

```
f510: LD HL,(FFA3)     ; caller's DMA address
      LD A,H
      CP 0x80
      RET NC           ; >= 8000h: use the caller's buffer in place
      LD DE,0xFEFF     ; < 8000h: bounce 128 bytes through FEFF
      LD BC,0x80
      CALL F498        ; KernMemCopy (bank-aware)
```

Byte-verified at `ROM00:3A2D` (`2A A3 FF 7C FE 80 D0 11 FF FE`). The
firmware bounces a sector buffer through fixed RAM **exactly when the
caller's buffer is in the banked window**, and uses it directly when it
is already unbanked — independent confirmation, from the other
direction, of the rule that cross-bank buffers must live above `8000`.

## Verifying a candidate region empirically

Do not trust this page for a region you are about to bet an experiment
on. Check it:

1. **Seed a non-zero pattern.** Fill the candidate range in the
   emulator's fixed-RAM array after boot completes but before the run of
   interest. `boot_hw.py` has `--upload-marker ADDR:VAL` for a single
   byte; a range fill is a two-line addition next to it. Use a
   **non-zero, non-constant** pattern — an address-derived one such as
   `mem[a] = (a ^ (a >> 8)) & 0xFF` — so that a routine writing zeros,
   or writing a constant that happens to equal your fill, cannot hide.
2. **Run the whole workflow, not a fragment.** Boot to the Main Menu,
   then drive the path you care about end to end, e.g.

   ```sh
   timeout 300 analysis/venv/bin/python3 analysis/boot_hw.py \
       --expect "To Continue Press>>:\r" --expect "Serial:\r12345678\r" \
       --expect "Main Menu:1" \
       --synthetic-workflow /tmp/driver.json \
       --dump-mem c000:256 --dump-mem cf80:256
   ```

3. **Diff.** `--dump-mem ADDR[:LEN]` dumps on every expect match and at
   exit; compare against the pattern. Any changed byte disqualifies the
   region — record *which* byte, since a single changed cell usually
   names a structure you have not mapped yet.
4. **Repeat with a second pattern.** A region that survives one fill but
   not its complement is being written with a value-dependent test, not
   left alone.
5. **Vary the input length.** The `E5C2` bug was invisible at most
   lengths. `CommstarCleanTeardownTest.test_the_image_length_does_not_change_the_outcome`
   in `analysis/test_boot_upload.py` is the model: run the same driver at
   several sizes and require identical outcomes.

A test whose result changes when you add a NOP is a memory-collision
symptom, not a timing one.

## Errors found in existing material

* **`~/ghidra_scripts/FillBatteryRam.java` copies module A2 seven bytes
  too long.** It uses `copyRomToRam(0x7c2f, 0x0130, 0xe104)`, but the
  boot-chain record at `ROM00:7D7C` is
  `01 00 2F 7C 04 E1 29 01` — length `0x129`, not `0x130`. The extra
  seven bytes would overrun `E22D`-`E233`, the head of the separate
  `E22D` config block that the chain copies from `ROM00:7301`.

    The script bug is real, but **the corruption is not present in
    `analysis/battery_ram.bin`**: its `E22D`-`E238` reads
    `00 00 4F 4B 00 00 4E 4F 00 01 44 4D`, matching `ROM00:7301` exactly.
    The dump therefore predates the bug or was made with a corrected
    length — consistent with `analysis/ghidra/AnalyseMicronicRom.java`
    pass 0, which already carries the `0x129` fix. Only the standalone
    `~/ghidra_scripts/FillBatteryRam.java` still needs correcting.
* **`analysis/battery_ram.bin` is described in the task framing (and read
  by `analysis/decode_inline_tables.py`) as post-boot RAM.** It is a dump
  of the Ghidra `ram` block after `FillBatteryRam.java`, i.e. a
  simulation. `decode_inline_tables.py` says so in its docstring; nothing
  else does. Treated as ground truth it would license "this region is
  zero, therefore free" for `8000`-`D080`, `D2C8`-`D680`, `E36E`-`ED1B`,
  `F68D`-`F783`, `F78C`-`FC04`, `FD97`-`FE82` and `FEB0`-`FFFF` — and
  four of those spans are proven live above.
* **[OS internals](os-diposb.md#queue-purpose-the-fn2-records) says
  "Remaining unwritten by the chains: tail `EC6D`-`ED1B` and gap
  `D481`-`D892`".** True as stated about the *chains*, but both spans are
  occupied at runtime: `D681`-`D892` is the dispatch block LDIR'd from
  `ROM00:7030` by `ROM00:3BAA` before the chains run, `D481`-`D680` is
  the loaded program's stack, and `EC6D`-`ED1B` holds the logon
  credentials and the loaded-program header and block descriptors. The
  sentence is easy to read as "these are free".

## Open

* `F68D`-`F77F` (243 B), `FD64`-`FD83` (32 B), `FE45`-`FE82` (62 B) and
  `FFA9`-`FFFF` (87 B) are unidentified. Discriminating test: the
  pattern-fill procedure above, run across a full session including a
  barcode read, a file write and a Commstar exchange.
* The negative result for `8006`-`D080` is bounded by 61%/37% ROM
  disassembly coverage. Extending coverage of `ROM01` would tighten it.

## Related

* [OS internals](os-diposb.md) — boot chains, kernel installation, the
  stub arena
* [Commstar evidence and traces](commstar-evidence.md) — the session
  objects at `E5BC`/`E5C2`
* [Memory and I/O map](../reference/memory-io.md) — the stable
  bank-window contract
* [Program file formats](../reference/program-formats.md) — the `0xCF81`
  COM limit and the `D081` ceiling
