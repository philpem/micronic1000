# Program formats: COM and DIP

This is the byte-level specification of the program-image formats DIPOS-B
loads at runtime. The DIP header, block grammar and in-memory descriptor
are **CONFIRMED** from the **runtime Load/Run loader** in ROM01 (`ROM01:0A67-10CE`)
and its resident handler table (`ram:D081 -> ram:D0F0`). The ROM **boot-load
chain** (`ram:D6DB` / `ram:D6F4` `fn=0/1/2/FFFF` grammar) is a **distinct**
mechanism — it installs the kernel at cold boot and is NOT the DIP file
format.

Everything is little-endian unless stated otherwise.

## Runtime Load/Run loader (CONFIRMED)

The loader that backs the **Load/Run Program** menu lives in ROM01 and is
reached through the per-screen handler tables:

* `ram:D081` = `g_apScreenHandlerTables` — five per-screen handler-table
  pointers, indexed by the active-screen selector at `ROM01:034B`. Entry 0
  points to `g_apLoadRunHandlers` at `ram:D0F0`.
* `Ui_FormExitDispatchNext` (`ROM01:06D3`) double-dereferences the current
  entry (`word @ (D081 + 2*i)` → pointer `P`, `word @ P` → handler) and
  bank-calls it via `d828`.
* ROM01 range `0A67-10CE` implements the loader proper; `ROM01:10C6` is the
  final transfer `-> ram:D7F0` (`RunLoadedProgram`).

Key Ghidra names (CONFIRMED, byte-verified branches):

| Address | Ghidra name | Role |
|---------|-------------|------|
| `ROM01:0A67` | `Program_PrepareLoadGeometry` | validate/normalise geometry before load |
| `ROM01:0AE3` | `Program_NormalizeLoadRange` | range/bank normalisation helper |
| `ROM01:0957` | `Program_GenerateBlockChecksums` | expand 8→10-byte descriptors, generate additive checksum at +8 |
| `ROM01:09C2` | `Program_VerifyBlockChecksums` | recompute checksums before run; mismatch → `0x2332` (9010), "Program corrupt." |
| `ROM01:0B82` | `Program_LoadByName` | save the requested name and start the loader |
| `ROM01:0BAC` | `Program_ConsumeInputChunk` | chunked input consumer |
| `ROM01:0CE7` | `Program_LoadDipOrCom` | DIP-vs-COM discriminator and block loader |
| `ROM01:0CCB` | `Program_ReportLoadError` | submit a program-load error ID and clear loader state |
| `ROM01:1002` | `Program_FinalizeInput` | finalize load on zero completion — generate DIP block checksums when needed and set loader state 3; nonzero status follows the `0x2330` error path |
| `ROM01:106F` | `Program_RunByName` | post-load run path |
| `ram:D7F0`  | `RunLoadedProgram` | final transfer to loaded image |

No BDOS execute function was found. BDOS `open` / `read` / `search` remain
generic FCB services; no direct call from this loader to them was found.
`ram:D370` is `g_pProgramLoaderContinuation`, a coroutine continuation
exchanged by `Coroutine_SwapContinuation` (`ram:D9F9`), not an
input-provider pointer. The upstream physical/session provider remains
**OPEN** — do not claim the exact source-reader is identified (see below).

## COM

A COM image is the ordinary CP/M single-image file with **no header**: it
is loaded contiguously starting at **0100h**.

Fallback rule (CONFIRMED, `ROM01:0CE7` branches):

* If the **first input chunk is under 14 bytes** OR the **first word !=
  `0xC8C9`** (file bytes `C9 C8`), the loader treats the input as **raw COM**,
  copies it to `0x0100`, sets run-bank offset `0` and entry `0x0100`.

Only byte-supported claims are retained. No executable-extension comparison
exists in the inspected branches.

COM errors (CONFIRMED dispatch):

* `COM file too big` — raw COM exceeds **0xCF81 bytes (53,121 bytes)**.
* `0x2332` (9010), **"Program corrupt."** — see checksum section; for COM it is the
  same post-load block-checksum mismatch, not a file-header checksum.

### Why the COM limit is 0xCF81

The limit is derived from the runtime memory layout, not from a rounded
file-size constant:

1. COM execution starts at `0x0100`, following the CP/M convention.
2. Kernel startup stores `0xD081` in `g_pProgramLoadCeiling`
   (`ram:D6A3-D6A8`). The loader treats this as an **exclusive** upper
   address (`ROM01:0D91-0DAB`).
3. Therefore the available byte count is:

   ```text
   0xD081 - 0x0100 = 0xCF81 = 53,121 bytes
   ```

   The last permitted byte is at `0xD080`.

`0xD081` looks unusual because it is the first occupied byte of resident
module B, not an alignment boundary. The bank-1 boot chain record at
`ROM01:7E23` copies `0x024A` bytes from `ROM01:7BCB` to
`ram:D081-D2CA`; the copied bytes begin with `g_apScreenHandlerTables`.
The COM transient area is simply the free range immediately below that
packed resident module. Once the loader has filled through `0xD080`, a
further raw-COM input chunk reaches `ROM01:0BCA` and reports error `0x232C`.

## DIP — file grammar (CONFIRMED)

A DIP file is **not** a stream of `ram:D6DB` loader records. It has its own
header and block structure decoded from `ROM01:0A67-10CE`.

### Header — exactly 14 bytes

| Offset | Type | Meaning |
|--------|------|---------|
| +0 | `u16` | **magic `0xC8C9`** (file bytes `C9 C8`); distinguishes DIP from COM |
| +2 | `u16` | **system ID**; accepted values `0` (wildcard) or `0x00E5` (Micronic 1000) |
| +4 | `u16` | **entry-bank offset** |
| +6 | `u16` | **image size**, clamped to `0x8000` |
| +8 | `u16` | **run-bank offset** |
| +10 | `u16` | **entry address** |
| +12 | `u16` | **block count**, maximum `5` |

All fields little-endian. The size field is clamped, not rejected, at
`0x8000` (CONFIRMED branch). `ram:ECDA` as the maximum available entry-bank
offset from selected-storage geometry is **LIKELY** only.

### How the execution fields are used

The bank values are **relative offsets**, not absolute port-47 bank values.
`Program_PrepareLoadGeometry` first records `g_wProgramBankBase` for the
selected source/storage context.

* **Entry-bank offset (`+4`)** describes where the program's load range
  begins relative to that base. `Program_NormalizeLoadRange` adds it to
  `g_wProgramBankBase` and validates the resulting range together with the
  image size at `+6`. This is load-range metadata; it does not by itself
  select the bank used when execution starts.
* **Run-bank offset (`+8`)** selects the bank that must be active when the
  program begins. Immediately before transfer, `Program_RunByName` adds it
  to `g_wProgramBankBase` and passes the resolved bank to
  `RunLoadedProgram` (`ROM01:10BD-10C6`).
* **Entry address (`+10`)** is the 16-bit Z80 address at which execution
  starts in that selected bank. `RunLoadedProgram` restores the kernel's
  dispatch state, resets SP, and performs `JP (HL)` to this value
  (`ram:D7F0-D7FD`). The bank and address are therefore separate parts of
  the far entry point.
* **Block count (`+12`)** is the number of block headers and payloads that
  follow the DIP header. The loader reads exactly that many blocks, creates
  the same number of 10-byte runtime descriptors at
  `g_abLoadedBlockDescriptors`, and later iterates the same count when
  generating and verifying checksums. The fixed descriptor array has five
  entries, so accepted values are `0..5`; values above five report error
  `0x2334` (9012), **"DIP file has too many blocks."**

Each block's own destination-bank offset is also relative to
`g_wProgramBankBase`. It controls where that block is installed and need
not equal either header bank offset.

### Blocks — `blockCount` repetitions

Each block in the file:

| Offset | Type | Meaning |
|--------|------|---------|
| +0 | `u16` | **type** — defined handlers exist for `0` and `1` |
| +2 | `u16` | **destination bank offset** |
| +4 | `u16` | **destination address** |
| +6 | `u16` | **payload byte count** |
| +8 | `u8[payload]` | **payload** (immediately follows header) |

The 8-byte header is read first; payload length comes from `+6`.

* **Type 0** — payload is copied directly to `destination bank / address`.
* **Type 1** — payload consists of 4-byte items `{u16 bank offset, u16 target
  address}`. For each item the loader writes a 4-byte
  `{0xD7, resolved bank byte, target address LE}` **RST 10h banked-call
  trampoline** into the destination range. `0xD7` is the `RST 10h` opcode;
  the bank byte is resolved from the bank offset.

Only types `0` and `1` have defined handlers. Other values take the inline
dispatch table's default "next block" path; there is no explicit error at
that dispatch. No additional payload format is CONFIRMED.

### In-memory expansion — `DIP_LoadedBlockDescriptor` (10 bytes)

At load time each 8-byte file block header is expanded to a **10-byte
`DIP_LoadedBlockDescriptor`**:

* `Program_GenerateBlockChecksums` (`ROM01:0957`) computes an **additive
  checksum** over the loaded payload and stores it at descriptor offset `+8`.
  The checksum is **NOT in the DIP file**.

Before execution, `Program_VerifyBlockChecksums` (`ROM01:09C2`) recomputes
checksums over the resident payloads; mismatch reports **`0x2332` (9010),
"Program corrupt."** The user-visible meaning is therefore **loaded program memory
changed / failed integrity check**, not "file header checksum failed".

## DIP and COM error catalogue (CONFIRMED)

The loader stores errors as hexadecimal IDs, but the error screen shows their
**decimal** values. This table records both in `0xNNNN (decimal)` form.

| Error shown | ID / trigger | Meaning |
|-------------|--------------|---------|
| `0x232B` (9003), "Bad DIP file." | short / structurally incomplete 8-byte block header or incomplete payload read | NOT bad magic |
| `0x2331` (9009), "Program not built for this system." | `+2` system ID incompatible | neither `0` nor `0x00E5` |
| `0x2334` (9012), "DIP file has too many blocks." | `+12` block count `>5` | also used for related bank-range bound |
| `0x232A` (9002), "DIP file too big." | `destination + payload` exceeds memory boundary | — |
| `0x232C` (9004), "COM file too big." | raw COM exceeds capacity | — |
| `0x2332` (9010), "Program corrupt." | runtime block checksum mismatch | `09C2` recompute vs `0957` value |

The strings live in `ram:D1BD-D253` (module B data, source
`ROM01:7BCB` → `ram:D081`, 586 bytes) and are reached through the
runtime-built error-code table around `ram:D159` via `Program_ReportLoadError`
(`ROM01:0CCB`). No direct xref exists — the table is built at runtime.

## Boot-load chain and ROM footer — separate mechanism (CONFIRMED)

Each ROM bank ends with a 16-byte footer at `7FF0h`:

| Offset | bank 0 | bank 1 | Meaning |
|--------|--------|--------|---------|
| 7FFA-7FFB | `58 7D` | `15 7E` | boot-chain pointer (word) |
| 7FFC-7FFD | `7D 58` | `15 7E` | duplicate chain pointer |
| 7FFE-7FFF | `F8 AC` | `12 2E` | candidate system ID / ROM tag |

The boot chain lives at `(7FFC)` (bank 0: `7D58`, bank 1: `7E15`) and is a
**bare record stream with no header** using the **boot-only** `fn` grammar:

```
d6de:  read fn (word)                     ; record type
       index handler table at ram:d6f4     ; entry = word @ (d6f4 + 2*fn)
       tail-jump to handler                ; handler re-enters d6de
```

| `fn`   | Handler    | Record                                     | Action |
|--------|------------|--------------------------------------------|--------|
| `0x0000` | `ram:d6fa` | `{fn, addr, count}`                        | `memset(addr, 0, count)` |
| `0x0001` | `ram:d713` | `{fn, src, dst, count}`                    | `memcpy(dst ← src, count)` |
| `0x0002` | `ram:d727` | `{fn, N, addr[N]}`                         | enqueue `N` deferred calls |
| `0xFFFF` | `ram:d6ee` | *(none)*                                   | terminate stream |

`0xFFFF` terminates by wrap-around: `d6f4 + 2*0xFFFF ≡ d6f2` (mod 64K), word
at `ram:d6f2` = `d6ee` (pop + return). Each `fn=2` target emits a 4-byte
`{0xD7, bank, addr_lo, addr_hi}` stub — the deferred-call queue at
`ram:d684`, drained at boot. This grammar is **CONFIRMED for the boot chain
only**. It is not the runtime DIP file format, and DIP files do NOT funnel
through `ram:D6DB`. Earlier docs that claimed funnelling are superseded.

### Checksum (boot primitive)

`ram:d7d1` (`ChecksumBytes`) computes a **16-bit additive byte-sum** — not a
CRC — over a byte range. It is the boot-chain primitive; the runtime DIP
per-block checksum is computed by `ROM01:0957` and verified by `ROM01:09C2`
(see above).

## Where the runtime parser lives

* The runtime DIP/COM discriminator and block loader is `ROM01:0CE7`
  (`Program_LoadDipOrCom`), called via `ram:D081 → ram:D0F0`.
* The boot dispatcher/copy lives in the **kernel dispatch / boot-loader block**
  copied from `ROM00:7030` → `ram:D681` (`0x212` bytes, via `ROM00:3BAA`).
  That block is **not** the runtime COM/DIP loader — the two are separate.
* Module A (`ROM00:73CE` → `ram:D893`, 2145 bytes) is **not** the DIP parser.
* `ram:D370` is `g_pProgramLoaderContinuation` (`Coroutine_SwapContinuation`
  `ram:D9F9`); the upstream physical/session provider remains **OPEN**.

## Emulator evidence: real-loader upload (bounded, below Commstar)

`analysis/boot_hw.py --upload` boots normally, invokes the real
`Program_LoadByName` (`ROM01:0B82`), feeds chunks according to the request
word at `D36C` through `Program_ConsumeInputChunk` (`ROM01:0BAC`), calls
`Program_FinalizeInput` (`ROM01:1002`), checks loader state `3` and resident
bytes, then invokes `Program_RunByName`/`RunLoadedProgram` (`ROM01:106F` →
`ram:D7F0`). It injects below the Commstar session and does **not** prove a
valid Commstar exchange or provider.

**CONFIRMED bounded runs (all byte-verified):**

* 28-byte raw COM: loader requested `14+14`; one-block 50-byte DIP: loader
  requested `14`-byte header + `8`-byte block header + `28` payload. Both
  entered `0100h` and printed `Hello World` / set marker `A5h` at `0200h`.
* Maximum `0xCF81`-byte (53,121) COM: loader requested `14`, then
  `207` chunks of `256`, then a final `115` — sequence
  `14 + 207*256 + 115 = 53121` (total `209` calls; calls `2-208` were
  `256`). Remainder `53107` after the first `14`. Exact bytes through
  `D080` verified and loader state `3` reached in `--upload-no-run` mode.

Host staging on the emulator uses the established incoming payload object
at `E5C2`; a regression proved a guessed `D500` workspace is modified
during `Program_ConsumeInputChunk`, so the emulator was moved to `E5C2`.
This host-only staging detail is **not** a firmware provider identity —
do not present it as such.

## Related

- [Loader internals](../internals/os-diposb.md) — boot-chain context (now
  distinguished from runtime DIP).
- [Programmer guide](programmer-guide.md) — application-level constraints.
- `analysis/decode_chains.py` — the boot-chain decoder (boot grammar only).
