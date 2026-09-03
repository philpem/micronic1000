# Barcode capture — mechanics and evidence

Evidence behind [Reference: Barcode reader](../reference/barcode.md). Every
claim here is byte-read from `micron1.bin` or measured in the emulator with
`analysis/test_barcode.py` and the `--barcode-*` harness options.

## Identification: mechanism yes, name no

The capture front end, its buffer, the decode hook and the delivery path are
all **CONFIRMED**. What is *not* established from the firmware is that the
attached device is a barcode pen:

* no string in either ROM names a barcode, pen, wand or symbology;
* the default `FE83` wire table makes wire `2Bh` the **EXT STORAGE ADAPTER**;
* the A:/B: RAM drives never touch this bus.

The barcode identification rests on the project owner's knowledge of the
physical hardware. Ghidra names use the neutral `Ext*` prefix. Treat
"barcode" as the application, and the `Ext*` front end as the mechanism.

## The capture loop — `ROM00:13BB`-`1441`

### Arming

`ROM00:13CB` polls `IN A,(2Dh)` and waits for **bit 0 = 1**. The quiet line
reads 0, so element 0 is always the first dark bar. The arm times out after
4 × 65536 polls (`ROM00:13C9` `LD C,4`), then `SCF; RET`.

The presence probe at `ROM00:1299`-`12AB` classifies the line first: bit 0
and bit 1 both clear gives type 2 (measured `ram:F9AB = 02`); bit 0 set at
probe time gives type 0, which becomes the `EEh` no-device error at
`ROM00:13A3`.

### The width unit

**Widths are counts of port-`2Dh` polls, not time.** Each element starts at
`ROM00:13E5` with `LD HL,1` and pre-increments at `13E8` before every poll,
so an element held for *N* samples is recorded as *N+1*.

The unchanged-level path is 55 T-states, so at 3.6864 MHz one count is
**≈14.9 µs** (corrected 2026-09-03; this passage previously assumed
3.579545 MHz and read ≈15.4 µs). That makes the minimum element ≈104 µs and
the capture terminator ≈92 ms of still line.

### Element limits

| Limit | Where | Effect |
|---|---|---|
| minimum 8 | `ROM00:13FA` `SUB 8` / `13FC` `JR C,13BF` | restarts the whole capture |
| maximum `1800h` = 6143 | `ROM00:13DF` `LD D,18h` / `13EA` `CP D` | **ends** the capture; the final element is not recorded |
| 128 elements | `ROM00:140F` `CP 80h` | caps the reverse copy |

**Correction:** the Ghidra EOL comment at `ROM00:13FA` reads "first element
< 8 loops: noise, restart". The test is in the per-element path at
`13F5`-`13FC` and applies to **every** element — the `LD A,H / OR A / JR NZ`
before it only skips the check when the width already exceeds 255.

The trailing quiet zone is the only thing that ends a scan.

### Why 128

The table is `PUSH`ed downward from `ram:FBB3` and reverse-copied
head-to-tail to `ram:F9B5`. 128 entries × 2 bytes is exactly where source and
destination meet — observed as `IX=FAB5`, `IY=FAB3` at that point. The cap is
geometric, not a protocol limit.

### The uncapped-count bug

```text
ROM00:1409  LD   (0F9B4h),A     ; the element count, UNCAPPED
ROM00:140F  CP   80h
ROM00:1411  JR   C,+2
ROM00:1413  LD   A,80h          ; caps only the register used for the copy
...
ROM00:1446  LD   A,(0F9B4h)     ; reads the UNCAPPED value back
ROM00:1449  LD   (0FBBBh),A     ; and hands it to the decode hook
```

**CONFIRMED by experiment**: fed 140 elements, `ram:F9B4` holds 140 and the
hook's parameter block reads `b5f9 8c00` — count 140 — while only 128 table
entries exist. A decode hook must clamp.

## The hook dispatch — `ROM00:1450`-`1468`

```text
1450  LD   HL,0FBB9h / PUSH HL   ; the single stack argument
1454  LD   HL,1468h   / PUSH HL  ; the return address
1458  LD   HL,(0FBC2h)           ; the hook ADDRESS field
145B  BIT  7,H / JR Z,1464h      ; banked address -> use the socket
145F  LD   A,(HL) / CP 0D7h      ; unbanked: is it already its own thunk?
1462  JR   Z,1467h               ;   yes -> jump direct
1464  LD   HL,0FBC0h             ;   no  -> via the socket
1467  JP   (HL)
1468  POP  HL / LD HL,(0FBBBh)   ; on return: test the count
```

`BIT 7,H` is **not** a gate on banked hooks — both branches reach the hook.
It only chooses which thunk carries the bank byte, and the direct jump
requires the hook to be at `>= 8000h` *and* start with `D7`.

### Measured entry state

Same-bank, and cross-bank with `FBC1 = 02`:

```text
same-bank   PC=9000 HL=9000 SP=D619 bank=00  stack: 1468 FBB9 ...
cross-bank  PC=9000 HL=FBC3 SP=D619 bank=02  stack: D762 FBB9 ...   (F791=02)
```

`HL` is not a parameter — it is the hook's own address (same-bank tail-jump)
or `FBC3` (cross-bank). The stack shape is identical: `[return][→FBB9]`. The
cross-bank return goes through `ram:D762`, the kernel's bank-restore
trampoline, with the real return and the old bank on the shadow stack.

## Delivery — `ROM00:1470`-`148B`

Written into the buffer at `(ram:FBB7)` = `ram:F958`:

| Offset | Contents |
|---|---|
| +0 | status byte, copied from `ram:FBB5` — must be 0 or delivery aborts |
| +1..+3 | not written by this path |
| +4..+5 | the 16-bit count |
| +6.. | the decoded bytes |

Measured for `"A1"`: `F958 = 00 00 00 00 02 00 41 31`.

**Capacity is 26 bytes.** The RX descriptor built at `ROM00:0F0E`/`0F14`
gives the buffer length `20h`, leaving `F95E`-`F977` after the six-byte
header, but the `LDIR` at `ROM00:148B` is unbounded — a longer result
overruns into the device-table pointer at `F978`.

### Reader-channel selection

`ROM00:110C` computes `((FBC5 >> 2) + 5) & 1Fh`, and `ROM00:320B` indexes
`FE83 + index − 1`. Measured `FBC5 = 04` gives `FE83+5` = wire `2Bh`, which
`LinkCommandLookup` routes to `ExtBusArm`.

### `BDOS 03h` framing

`ROM00:10CF` emits `1Bh`; `10C2` stashes the count for the next call;
`10AB`-`10B3` walks the ring `F954` → `F956` over `F95E`. **CONFIRMED by
execution**: a driven `A1` scan returns `1B 02 41 31`.

## Harness notes

* Only two sites sample port `2Dh`: `ROM00:13CB` (arm) and `13ED` (time).
  The wand model gates on those PCs so the presence probe at `12A3` and the
  idle polls at `1302`/`1317`/`132E`/`1370` cannot consume samples.
* A synthetic direct capture must stop at `ROM00:30BD`: `CALL 30BD` never
  returns, because `LinkResetSession` sets `ram:FBC9` bit 0 and tail-jumps
  through `(ram:FDD2)`, the device-completion callback. By then the whole
  record is written.
* Acceptance evidence for the wand: `--barcode-scan A1` feeds 39 elements
  and `--watch-mem f9b5:fbb4` records 234 writes from 5 PCs — 78 from the
  `PUSH` at `ROM00:1401` (39 × 2 bytes) and the rest from the reverse copy —
  with the recorded widths matching the input exactly.

## Correction to `AGENTS.md`

Its restart-vector list says "`0008` → `JP F180` (BDOS dispatch), `0010` →
`JP F5E1` (banked-call dispatcher)". The bytes say otherwise:

```text
0005: C3 80 F1    JP F180   <- the CP/M BDOS gate
0008: C3 E1 F5    JP F5E1
0010: E1 5E 3A    not a jump -- the dispatcher is coded inline here
```
