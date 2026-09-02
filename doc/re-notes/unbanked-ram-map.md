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
   (`ROM00` is 61% disassembled, `ROM01` 37%). For the four originally
   unidentified spans this was re-run with an **alignment filter** —
   linear-sweep from each of the preceding 64 offsets, keep the hit only
   if a majority of sweeps land on it — plus `DD/FD 21/22/2A` and the
   conditional `JP`/`CALL` forms. Without that filter roughly half the
   raw hits are misalignment artefacts (`CD 92 2A / 21 F7 2D` reads as
   `LD HL,(F721)` if you start one byte early), and two of the four
   spans were "solved" by an artefact before it was applied.
3. **The boot-load chains** (`analysis/decode_chains.py`, and the
   pre-chain copies in `AnalyseMicronicRom.java` pass 2), which give
   the large occupied blocks with exact destinations and lengths.
4. **Existing repo findings** — Ghidra labels, [OS
   internals](os-diposb.md), `doc/research/TASKS.md`.
5. **Emulator snapshots.** `analysis/boot_hw.py --dump-mem ADDR:LEN`
   over a boot to the Main Menu and over a synthetic Load/Run. The
   harness skips the destructive RAM test, so a region reading zero in
   its dumps really was never written during the run — unlike
   `analysis/battery_ram.bin`, below.
6. **Emulator write watch.** `analysis/boot_hw.py --watch-mem LO:HI`
   hooks the CPU's write callback, so it reports every store the Z80
   makes into a range — `PUSH` and `LDIR` included — with the writing
   PC, and `--fill-mem LO:HI` seeds a range with an address-derived
   marker and reports what survived. Unlike a snapshot, these catch a
   write that was undone before you looked. The two remaining
   unidentified spans were closed with them; see "the two spans that
   stayed empty".

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
| `F180`-`F68C` | 1293 | Resident kernel (BDOS gate, syscall envelopes, RST/NMI stubs, bank helpers) | CONFIRMED | `InstallKernelToRam` `ROM00:02FE`: `ROM00:369D → F180`. The copy loop is bounded by the *address* `F68D` (`ROM00:0308` `01 8D F6`), not by a length; `0x50D` is `F68D - F180`. A second entry at `ROM00:0318` loads a different, `0xB5`-byte bank-helper image from `ROM00:35E8` to the same base — see "the two spans that stayed empty". |
| `F68D`-`F77F` | 243 | **Dead gap between the top of the resident kernel image and the port shadows.** No reference of any kind from either ROM or any RAM module, and no write from any of the five workloads driven under the emulator. It is *not* spare room in a round 1536-byte arena — that reading is **disproven** below. It is *not* stack headroom in practice either: the system stack's measured low-water mark is `F7EA`, 107 bytes above `F77F`. | CONFIRMED (unwritten across every driven workload) / OPEN (any use outside them) | `--watch-mem f68d:f77f` = 0 writes in all five runs; `--fill-mem f68d:f819` leaves everything below `F7EA` intact; see "the two spans that stayed empty" below |
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
| `FD46`-`FD5B` | 22 | RTC working area: `FD4A`-`FD4C` alarm fields, `FD4D` `RTC_AlarmSleep` countdown, `FD4F` RTC Reg C/B wake-reason latch, `FD50` `g_abRtcRegisterSnapshot` (10 B), `FD57`/`FD58` alarm date compare, `FD5B` sweep slot index | CONFIRMED | [RTC notes](rtc.md); `ROM00:2214` `LD (FD4F),A`, `ROM00:2250` `LD (FD5B),A` |
| `FD5C`-`FD83` | 40 | **Countdown-timer / work-item table** (`comm_work_table`) — **10 slots × 4 bytes**, `{+0..+1 = pointer to a 16-bit down-counter, +2..+3 = callback}`. Slot 0 is `FD5C`, slot 9 ends at `FD83`; the whole of the former "unidentified" `FD64`-`FD83` is slots 2-9. | CONFIRMED | see below |
| `FD84`-`FD96` | 19 | Comms config table | CONFIRMED | `ROM00:22E9`/`2306` copy `ROM00:2352`, 19 bytes |
| `FD97`-`FE42` | 172 | Link/device state: `FDCA` `g_bWireId`, `FDD4` wire-id copy used as the sequence-table index, `FDD5` `g_bLinkState`, `FDDE`-`FDE2` outgoing frame header, `FDE7` received sequence byte, `FDEA` TX `{count, ptr}` descriptor, `FE0E`-`FE42` | CONFIRMED | named, referenced |
| `FE43`-`FE82` | 64 | **Per-link frame-sequence table** — one byte per remote unit address, indexed `FE43 + (FDD4 & 3Fh)`, initialised to `01` for all 64 entries at link reset. The former "unidentified" `FE45`-`FE82` is entries 2-63 of it. | CONFIRMED | see below; already CONFIRMED in [Commstar evidence](commstar-evidence.md) |
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
| `FFA9`-`FFFF` | 87 | **Unclaimed remainder above the BDOS variable block** — top of RAM. No reference of any kind; every `FFxx` literal in either ROM that survives an alignment check is a small negative constant (`-1`, `-4`, `-5`, `-8`, `-10`, `-20`, `-24`, `-32`, `-48`) feeding an `ADD HL,rr` subtraction, not an address. Nothing writes it, **including a BDOS file workload that wrote 6,391 times into the bounce buffers immediately below without once crossing the boundary.** | CONFIRMED (unwritten across every driven workload, incl. the disk path) / OPEN (any use outside them) | `--watch-mem ffa9:ffff` = 0 writes in all five runs; see "the two spans that stayed empty" below |

### The two spans that turned out to be structure tails

Both were "unidentified" only because this page stopped the neighbouring
structure one entry short. Neither is free.

**`FD5C`-`FD83` — the 10-slot countdown-timer table.** Two independent
walkers fix the geometry, and both are byte-verified:

```
ROM00:2189 CommsWorkItemRegister
  21 5C FD    LD HL,FD5C     ; slot 0
  0E 0A       LD C,0Ah       ; 10 slots
  7E 23 B6    LD A,(HL); INC HL; OR (HL)   ; free if both bytes zero
  28 09       JR Z,21A3      ; -> claim it
  0D 28 12    DEC C; JR Z,21AF             ; table full -> CY
  11 03 00 19 LD DE,3; ADD HL,DE           ; +1 already done -> stride 4
  18 F2       JR 2195

ROM00:21BA CommsWorkItemCancel
  DD 21 5C FD LD IX,FD5C
  DD 6E 00 / DD 66 01    ; key = entry.+0/+1
  DD 23 ×4               ; stride 4 (the listing shows 3; the bytes are 4)
  79 FE 0A 28 0C         ; C == 10 -> not found
```

`FD5C + 10 × 4 = FD84`, which is exactly where the comms config table
starts — the table ends flush against its neighbour with no padding.
Entry layout is `{+0..+1 = pointer to a 16-bit down-counter,
+2..+3 = callback}`; `Comms_WorkItemSweep` (`ROM00:224C`) walks the same
10 slots, decrements `*(entry.+0)` and, on reaching zero, zeroes
`entry.+0..+1` and `JP (HL)`s the callback via `ROM00:2275`. The sweep
runs off the **RTC periodic interrupt**: `ROM00:2214` latches RTC Reg C
into `FD4F` and `ROM00:221F` `E6 40 / C4 4C 22` = `AND 40h; CALL NZ,224C`
— Reg C bit 6 is `PF`.

Empirically live, too: booting to the Main Menu under
`analysis/boot_hw.py` leaves `FD5C:40` =
`9F FD B0 24 | 00 00 11 17 | 00 00 11 17 | 00 …`. Slot 0 matches its
registration site byte for byte — `ROM00:2489`
`21 00 0F / 22 9F FD / 11 9F FD / 21 B0 24 / CD 89 21` =
`LD HL,0F00; LD (FD9F),HL; LD DE,FD9F; LD HL,24B0; CALL 2189`, i.e.
"count `0F00` ticks down at `FD9F`, then call `24B0`" — which is an
independent confirmation of the `{counter pointer, callback}` layout.
Slots 1 and 2 have fired: zeroed pointer, residual callback, exactly as
`ROM00:2275` leaves them. **Slot 2 is `FD64`**, the first byte this page
used to call unidentified. Under a synthetic Load/Run the same dump
reads `… | 00 00 86 2F | 00 00 11 17 |`, slot 1 now carrying
`ROM00:2F86`, the routine the link setup at `ROM00:3053` calls.

This was already established in the repo — `doc/research/TASKS.md`
records the FD5C queue as a 10-slot countdown-timer/callback table with
the Ghidra names applied — and simply never reached this page.

**`FE43`-`FE82` — the per-link frame-sequence table.** 64 bytes, one per
remote unit address:

```
ROM00:317B  (link reset)
  21 43 FE   LD HL,FE43
  06 40      LD B,40h        ; 64 entries
  36 01      LD (HL),1       ; every entry starts at 1
  23 10 FB   INC HL; DJNZ
  3E 04 32 D5 FD   LD A,4; LD (FDD5),A     ; g_bLinkState = 4

ROM00:3192  (address helper)
  3A D4 FD   LD A,(FDD4)     ; copy of g_bWireId for this transaction
  E6 3F      AND 3Fh         ; 6-bit unit address
  6F 26 00   LD L,A; LD H,0
  11 43 FE   LD DE,FE43
  19         ADD HL,DE       ; -> FE43 + (FDD4 & 3Fh)
```

with three one-line accessors on top: `31A1` get (`CALL 3192; LD A,(HL)`),
`31A6` set, `31AB` increment. `FE43 + 3Fh = FE82`, matching the `B=40h`
fill exactly. The use is a sequence number: `ROM00:3084`
`3A E7 FD / 47 / CD A1 31 / B8` reads the received sequence byte
`FDE7`, fetches `tbl[wire]` and compares; equal → `CALL 31AB`
(increment); otherwise, and only when `FDCB` = 2, `79 3D B8 28 09`
(`LD A,C; DEC A; CP B; JR Z,30A4`) takes a second branch when the
received byte is one *less* than the stored one — a repeat of the
previous frame, LIKELY the duplicate-retransmission case; anything else
falls through to `01 EF 01` = error `01EF`. On transmit, `ROM00:316B` stitches
`tbl[wire]` into the outgoing header at `FDE1` while building a frame at
`FDDE`. Every emulator snapshot shows all 64 bytes reading `01`, the
`317B` init value.

This one was *also* already CONFIRMED in the repo — see [Commstar
evidence](commstar-evidence.md), which has used `FE43h + (fdd4 & 3Fh)`
for months — so the row is a straight import, not a new finding. What is
new here is only the **extent**: the table is 64 bytes wide, so `FE43`
and `FE44` belong to it and not to the link-state block below.

### The two spans that stayed empty

`F68D`-`F77F` and `FFA9`-`FFFF` survived the static treatment and stayed
empty, and a write watch over five driven workloads has now failed to
find a single write into either. What was ruled out statically, and how:

* **No static reference of any kind.** A raw-opcode scan of both full
  ROM images and all five RAM-resident modules for every 16-bit-operand
  form (`01/11/21/22/2A/31/32/3A`, `ED 43/4B/53/5B/63/6B/73/7B`,
  `DD/FD 21/22/2A`, and all `JP`/`CALL` forms), filtered by a
  linear-sweep alignment check, returns **nothing** in either span. The
  one literal that names `F68D` is `ROM00:0308` `01 8D F6` =
  `LD BC,F68D` — the *terminator* of `InstallKernelToRam`'s copy loop
  (`ROM00:0305` `11 80 F1` `LD DE,F180`, then
  `7E 12 23 13 7B B9 20 F8 7A B8 20 F4 C9`, copy until `DE == BC`), so
  `F68D` is the exclusive end of the kernel image, not a use of it. In
  `FFA9`-`FFFF` every surviving `FFxx` literal is a small negative
  constant — `LD HL,FFFF` (−1), `LD DE,FFFC/FFFB/FFF8/FFF6/FFEC`,
  `LD BC,FFE8` (−24), `LD HL,FFE0` (−32), `LD DE,FFD0` (−48) — feeding
  an `ADD HL,rr` subtraction.
* **No `SP`-filled buffer.** The same scan turns up 17 candidate
  `LD SP,nn` sites in the whole firmware. Only three of them are real
  code targeting fixed RAM — `F81A` (system stack), `FBB5` (barcode
  capture) and `D681` (program stack) — and none is in either span. The
  rest decode as `LD SP` only when read mid-table: `ROM00:1B80`
  `31 7F ED` (`LD SP,ED7F`) sits inside a keyboard table, `ROM00:235A`
  inside the comms config table copied by `ROM00:22E9`.
* **`FFA9`-`FFFF` is not reached by the Z80's power-on `SP = FFFF`
  either.** `reset_entry` sets the stack before it can push anything:
  `ROM00:014B` `F3 / 2A D0 FB / F9` = `DI; LD HL,(FBD0); LD SP,HL` are
  the first three instructions executed after `0000` `JP 0103` →
  `JP 014B`. No `CALL` or `PUSH` precedes them.
* **Not an overrun of the neighbouring buffers.** `ram:F4F4`/`F50B` walk
  `FF7F` with `BC = 24h`, last byte `FFA2`; `ram:F510`/`F523` walk
  `FEFF` with `BC = 80h`, last byte `FF7E`. Both stop exactly where this
  page says they do.
* **Empirically untouched at every snapshot.** Under
  `analysis/boot_hw.py` (which skips the destructive RAM test, so zero
  means "nothing wrote here"), both spans read all-zero at every
  `--dump-mem f68d:243 --dump-mem ffa9:87` of a boot to the Main Menu and
  of a synthetic Load/Run.

#### What the write watch showed

Snapshots only prove a span is zero *when you look*. `boot_hw.py` now has
`--watch-mem LO:HI` (see `analysis/README.md`), which hooks the CPU's
write callback and so sees every store the Z80 makes into a range —
`PUSH` and `LDIR` included — with the address, the value, `SP`, the bank
and the PC of the writing instruction. Five workloads were run with both
spans watched and with `--fill-mem f68d:f819` seeding the gap, the port
shadows and the whole system stack with an address-derived marker:

| | Workload | Driven by | `F68D`-`F77F` | `FFA9`-`FFFF` | stack low-water |
|---|---|---|---:|---:|---|
| A | Cold boot → Main Menu → Display Status | `--expect` steps through the banner, the serial prompt, menu key `3` | **0** | **0** | `F7EA` |
| B | Load/Run program download over PLINTH | `--trace-loadrun-source plinth --synthetic-loadrun … --synthetic-loadrun-finalize` | **0** | **0** | `F7EA` |
| C | Commstar record upload, handheld → host | `--commstar-peer --upload` with the `CommstarRecordUploadTest` driver (C-INIT-COMMS → C-DIAL → C-BEGIN-FILE → C-TX-REC → C-END-FILE → C-END-TX); the 51-byte record reached the peer | **0** | **0** | `F7EA` |
| D | Commstar program download, host → handheld | `--commstar-peer --commstar-serve-program` with the `CommstarProgramDownloadTest` driver; 300 bytes in four blocks, screen reached "Program received" | **0** | **0** | `F7EA` |
| E | **BDOS file/disk workload** | a purpose-built COM issuing ~70 BDOS file calls (below) | **0** | **0** | `F7EA` |

The instrument is not silently dead. On the same boot, a control watch on
the port shadows `F780`-`F799` reported **61,923 writes from 33 distinct
PCs**; and the write callback demonstrably fires on stack pushes (a
three-instruction probe — `LD (nn),HL`, `PUSH HL`, `LD (nn),A` — reports
all five bytes), which is what makes a watch below a stack top a valid
stack-depth measurement.

**Workload E is the one this page asked for.** The COM does: reset disk
(fn `0D`), select drive A: (`0E`), set the DMA address to `0300` — inside
the *banked* window, which forces the `FEFF` bounce path at `ram:F510` —
search-first (`11`) and twelve search-nexts (`12`) over a wildcard FCB,
delete (`13`), make (`16`), sixteen write-sequentials (`15`), close
(`10`), open (`0F`), sixteen read-sequentials (`14`), set-random-record
(`24`), write-random (`22`), read-random (`21`), file-size (`23`), close,
then DMA to `8100` — *unbanked*, the no-bounce path — search-first and
eight more search-nexts, delete, reset. It ran through to its completion
marker, so every call returned. The RAM disk is real in this
configuration: the Display Status screen reports `RAMdisk size 190k`.

What it moved, from the same run's watch counters:

* `F8B8`-`F937` (BDOS directory swap buffer): **15,851 writes**, all 128
  bytes, 6 distinct PCs — `ram:F4A1` (the `KernMemCopy` inner loop)
  ×15,488, `ROM00:056B` ×256 (the boot-time `E5` fill), plus `06D6`,
  `063F`, `064E`, `08E4`.
* `FEFF`-`FFA8` (sector bounce, FCB bounce, DMA pointer, FCB pointer,
  interrupt shadow): **6,391 writes**, 169 of its 170 addresses, 35
  distinct PCs — `ram:F4A1` ×4,608, `ram:F669`/`F683` ×584 each (the
  `FFA8` interrupt shadow), `ROM00:06AA` ×308, `ram:F4EF` ×128, and
  `ROM00:0990`/`09BF` inside the search-first/search-next handlers
  (`ROM00:096C`/`09A3`, BDOS table entries 11h/12h) and `ROM00:0B3E`
  inside write-sequential (`0B09`).
* `FFA9`-`FFFF`: **0**.

That is the discriminating result. The bounce-buffer helpers at
`ram:F4EB`-`F54D` were driven hard, wrote 6,391 times into the block
that ends at `FFA8`, and did not cross into `FFA9` once.

#### The "1536-byte kernel arena" reading is disproven

`InstallKernelToRam`, byte-verified from `micron1.bin` at `ROM00:02FE`
(`11 b5 00 21 e8 35 19 11 80 f1 01 8d f6 7e 12 23 13 7b b9 20 f8 7a b8 20
f4 c9`):

```
02FE  11 B5 00     LD DE,00B5
0301  21 E8 35     LD HL,35E8
0304  19           ADD HL,DE       ; HL = 369D: the source
0305  11 80 F1     LD DE,F180      ; the destination
0308  01 8D F6     LD BC,F68D      ; <- a loop TERMINATOR ADDRESS
030B  7E 12 23 13  LD A,(HL); LD (DE),A; INC HL; INC DE
030F  7B B9 20 F8  LD A,E; CP C; JR NZ,030B
0313  7A B8 20 F4  LD A,D; CP B; JR NZ,030B
0317  C9           RET
```

The copy is bounded by an **address**, not a length: it stops when
`DE == BC == F68D`. So `F68D` is the firmware's own stated exclusive end
of the kernel image, and the familiar `0x50D` is *derived* from it
(`F68D - F180`), not the other way round. The constant `0x600` occurs
nowhere in this code; `F180 + 0x600 = F780` is numerology and there is no
arena. This page previously carried the arena as LIKELY — it should not
have.

The second entry at `ROM00:0318` (`11 80 f1 21 e8 35 01 35 f2 18 e8`) is
not "the same kernel, installed shorter" either:

```
0318  11 80 F1     LD DE,F180
031B  21 E8 35     LD HL,35E8      ; note: no ADD HL,DE this time
031E  01 35 F2     LD BC,F235
0321  18 E8        JR 030B         ; re-enter the same copy loop
```

It copies `35E8`-`369C`, `0xB5` bytes — exactly the `DE` value `02FE`
adds to reach *its* source — to `F180`-`F234`. The ROM holds **two
different images back to back at `35E8`, both loaded to `F180`**. The
short one is the bank-switching helper set: `D3 47` (`OUT (BANK_SEL),A`)
opens and closes every routine in it, around fill, compare and copy loops
(`35E8`, `3603`, `3627`, `3653`, `3667`, `3670`). The long one at `369D`
is the resident kernel. Cold boot installs the short set first —
`ROM00:01ED` `CD 18 03` — because the RAM-sizing code that follows needs
bank helpers before a kernel exists; the full kernel goes in later at
`ROM00:023E` `CD FE 02`, immediately before the warm-boot entry `024D`
that `ROM00:01A3` `CA 4D 02` jumps to when `F81C` already holds `55`.
Two alternative images sharing one load address is not evidence of an
oversized arena, and neither image reaches `F68D`.

#### The stack-headroom reading, measured

`--fill-mem f68d:f819` seeds the gap, the port shadows and the entire
system stack with `mem[a] = (a ^ (a >> 8)) & FF` at the instant the
destructive RAM test finishes — which is also the instant `ROM00:01D4`
`31 1A F8` resets `SP` to `F81A`, so nothing live is overwritten. What
still holds its marker at exit is therefore a **cumulative low-water mark
for the whole session**.

All five workloads agree: the lowest byte the firmware disturbed is
`F7EA`. `F81A - F7EA = 0x30`, so the system stack peaks at **48 bytes
deep and leaves 80 of its 128 bytes unused**, and the nearest it comes to
`F77F` is `F7EA - F77F` = 107 bytes. Both `F68D`-`F77F` (the whole span)
and `F79A`-`F7E9` (the unused bottom of the stack) still held the marker
at exit; the only things that moved below `F7EA` were the port shadows
`F780`-`F799`, which are live cells and were expected to. The two lowest words of the deepest frame read `31C5`
and `2346`, both `ROM00` addresses in the link bring-up that runs during
boot, so the deep point is a boot-time excursion rather than anything a
session drives deeper. (Marker survival can only under-report: a write
that happened to store a byte's own marker value would hide. The 80-byte
contiguous intact run `F79A`-`F7E9` makes that implausible as an
explanation of the boundary; per run, two bytes inside `F7EA`-`F819` did
coincide, which is the expected 1-in-256 rate.)

So both readings this page offered for `F68D`-`F77F` are wrong, but not
symmetrically. "Spare arena" is disproven from the bytes. "Stack
headroom" is *true in principle and irrelevant in practice*: the span is
indeed the next thing below the stack, but the stack stops 107 bytes
short of it in every workload driven, and it must cross the port shadows
first — which would have broken the machine long before it reached
`F68D`. What is left for both spans is the same, dull answer: **nothing
uses them.**

#### The shape of the remaining risk

"Never written across five workloads" is bounded evidence of disuse, not
proof of freedom. Specifically:

* **Covered:** cold boot and the boot-time RAM sizing, the banner and
  serial-entry screens, the Main Menu and Display Status screens, the
  RTC periodic-interrupt path (the workloads log 745-99,146 RTC/link
  transactions each), the PLINTH Load/Run download and its ROM
  finalizer, both Commstar directions through the application API, the
  program loader and `RunLoadedProgram`, and the BDOS file layer end to
  end including both the bounced and the unbounced DMA paths.
* **Not covered — the barcode path.** It cannot be driven with the
  harness as it stands: `boot_hw.py`'s input callback returns a constant
  `0xFF` for every port it does not model, `EXTBUS_EDGE` (2Dh) among
  them, so the edge loops at `ROM00:13CB` and `13ED` (both `DB 2D / E6
  01`) never see a transition and no capture occurs. Driving it needs a wand model — a
  `--barcode-pattern`-style source feeding timed 2Dh transitions — which
  is a separate feature. The static bound is reassuring but not a
  substitute: the capture writes by `PUSH` from `SP = FBB5`
  (`ROM00:13BB` `ED 73 BD FB`, `13BF` `31 B5 FB`) and its loop counter is
  a single byte in `C`, so at the absolute worst 256 pushes fill exactly
  `F9B5`-`FBB4`, its documented 512 bytes; `ROM00:1408` `79 32 B4 F9 FE
  09 D8 FE 80 38 02 3E 80` then caps the recorded count at `80h`. Neither
  span is reachable from there.
* **Not covered — anything only real hardware or a real host can
  reach:** a genuine V24 adaptor peer, the EXT STORAGE ADAPTER on
  drives `C:`/`D:` over the 4x transport, alarm/sleep-wake cycles, the
  self-test and Diagnostics paths beyond the Display Status screen, and
  any loaded application other than the drivers written here. A
  Commstar service this peer model does not implement could still
  exercise firmware neither span has seen.
* **Not covered — the disassembly bound is unchanged.** `ROM00` is 61%
  disassembled, `ROM01` 37%; the static negative rests on a raw-opcode
  scan with an alignment filter, not on full coverage.

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
nothing more. The negative is now stronger than "no disassembled
reference": no aligned 16-bit-operand instruction anywhere in either
full ROM image or any RAM module names an address in it, no `LD SP`
targets it, and the power-on `SP = FFFF` is overwritten before the first
push (`ROM00:014B`). **The off-by-one worry has now been tested and it
did not happen:** a COM issuing ~70 BDOS file calls drove the
bounce-buffer helpers at `ram:F4EB`-`F54D` to 6,391 writes across 169 of
the 170 bytes of `FEFF`-`FFA8`, and `--watch-mem ffa9:ffff` saw nothing.
It stayed unwritten through that and through four other workloads (see
"the two spans that stayed empty"). **Falsified by:** a BDOS path those
workloads did not reach — most plausibly one belonging to the EXT
STORAGE ADAPTER drives `C:`/`D:`, which no harness can drive yet. Treat
a corrupted marker as a signal, not a nuisance.

### Not recommended, despite looking free

* **`F68D`-`F77F` (243 B).** Unreferenced and never written in any driven
  workload, and the system stack turns out to stop a long way short of
  it — measured low-water mark `F7EA`, 107 bytes above `F77F`, in all
  five (see "the stack-headroom reading, measured"). It is still the
  wrong place for scratch: it is the next thing below a stack whose
  depth you would be betting on, and a stack excursion reaches the port
  shadows at `F780` before it reaches here, so a corrupted byte in this
  span means the machine is already broken. Anything you put here is a
  stack-depth canary, not scratch — but as a canary it is now calibrated:
  48 bytes used of 128.
* **`FD64`-`FD83`, `FE45`-`FE82`. Now identified — do not use them.**
  The prior that they were structure padding of their neighbours was
  right, and stronger than stated: they are not padding but *live
  entries*. `FD64`-`FD83` is slots 2-9 of the 10-slot countdown-timer
  table based at `FD5C`, and `FE45`-`FE82` is entries 2-63 of the
  64-byte per-link sequence table based at `FE43`. Both were found by
  the base-literal-plus-stride idiom this page warns about, and both
  were already documented elsewhere in the repo.

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
   interest: `boot_hw.py --fill-mem LO:HI` does this, seeding the range
   at the point the destructive RAM test finishes and reporting at exit
   how much of it survived. Its default pattern is **non-zero and
   non-constant** — address-derived, `mem[a] = (a ^ (a >> 8)) & 0xFF` —
   so a routine writing zeros, or writing a constant that happens to
   equal your fill, cannot hide. Better still, add
   `--watch-mem LO:HI` alongside it: the fill tells you *that* something
   wrote, the watch tells you *which instruction did*, in real time, and
   catches a write that was later overwritten with the marker value.
2. **Run the whole workflow, not a fragment.** Boot to the Main Menu,
   then drive the path you care about end to end, e.g.

   ```sh
   timeout 300 analysis/venv/bin/python3 analysis/boot_hw.py \
       --expect "To Continue Press>>:\r" \
       --expect "serial number:\r12345678\r" \
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
* **This page's own boundaries at `FD64`, `FE45` and `FD97`-`FE44` were
  wrong, and two of its four "unidentified" spans were already solved
  elsewhere in the repo.** `doc/research/TASKS.md` has recorded the
  `FD5C` queue as a 10-slot countdown-timer/callback table since
  2026-08-25 (with `CommsWorkItemRegister` / `Comms_WorkItemSweep` named
  in Ghidra, and an explicit warning that the stride is 4 even though
  the listing shows three `INC IX`), and [Commstar
  evidence](commstar-evidence.md) has treated `FE43h + (fdd4 & 3Fh)` as
  a CONFIRMED per-link sequence slot throughout. Neither reached this
  page, and both row boundaries were drawn two entries into the
  structure rather than at its end — which is exactly the failure mode
  the "base literal plus walked pointer" note warns about, committed by
  the map itself.
  Corrected above: `FD46`-`FD5B` / `FD5C`-`FD83`, and `FD97`-`FE42` /
  `FE43`-`FE82`.
* **This page asserted a 1536-byte kernel arena that does not exist.**
  `F180 + 0x600 = F780` was arithmetic in search of a mechanism: the
  install loop at `ROM00:02FE` is bounded by the address `F68D`
  (`0308` `01 8D F6`), the `0x600` appears nowhere, and the "second,
  shorter install" at `ROM00:0318` copies a *different* image (the
  `0xB5`-byte bank-helper set at `ROM00:35E8`) rather than a truncated
  kernel. Corrected in "the two spans that stayed empty". The lesson is
  the page's own: a round number is not evidence.
* **The worked example under "Verifying a candidate region empirically"
  waited for `"Serial:"`.** The serial-entry screen renders
  `Enter the Workstation serial number shown on the back` — lowercase,
  no colon — so that step never matched and the run stalled at the
  banner. Corrected to `"serial number"`.

## Open

* `FD64`-`FD83` and `FE45`-`FE82` are **closed**: they are the tails of
  the `FD5C` countdown-timer table (10 × 4 B) and the `FE43` per-link
  sequence table (64 × 1 B) respectively. See "the two spans that turned
  out to be structure tails".
* `F68D`-`F77F` (243 B) and `FFA9`-`FFFF` (87 B) have **no identity to
  find**: each is a gap, not a structure. Neither is referenced
  statically and neither took a single write across five driven
  workloads — cold boot, a PLINTH Load/Run download, a Commstar record
  upload, a Commstar program download, and a BDOS file workload that hit
  the bounce buffers 6,391 times. See "the two spans that stayed empty".
  Two earlier readings are now settled: the "spare room in a 1536-byte
  kernel arena" story is **disproven** (`ROM00:0308` `01 8D F6` is a copy
  terminator, not a size; the `0x600` is numerology), and "stack
  headroom" is true only in the topological sense — the measured stack
  low-water mark is `F7EA`, 107 bytes above `F77F`.
  What remains open is only the *bound*: the barcode path cannot be
  driven at all with the current harness (no port-2Dh edge model), and
  nothing exercises the EXT STORAGE ADAPTER drives, a real V24 peer, or
  alarm/sleep-wake. Either span could still be claimed by firmware
  those paths reach.
* Ghidra still labels `FD5C` `comm_work_table`, which reads as a comms
  buffer rather than a timer table. The name is grandfathered and this
  page does not rename it, but a reader following the label alone will
  mis-size the structure.
* The negative result for `8006`-`D080` is bounded by 61%/37% ROM
  disassembly coverage. Extending coverage of `ROM01` would tighten it.

## Related

* [OS internals](os-diposb.md) — boot chains, kernel installation, the
  stub arena
* [Commstar evidence and traces](commstar-evidence.md) — the session
  objects at `E5BC`/`E5C2`
* [Memory and I/O map](../reference/memory-map.md) — the stable
  bank-window contract
* [Program file formats](../reference/program-formats.md) — the `0xCF81`
  COM limit and the `D081` ceiling
