# Stock-context v4: receive result and handover

Prepared 2026-09-24 on `ir/stock-context-v3-content`, PR #26.
**Ready for owner installation; no hardware run or upload was made in this pass.**
This replaces the proposed `stock-rx-entry` burn. Keep old releases as
historical evidence, not as the next image to install.

## What is known

See the [review](../research/reviews/ir-rounds-review-2026-09-23.md) and
[round-two record](stock-context-v3-round2.md). F7 originally produced 34
carry-set return markers; exact replay later failed to reproduce them.
No successful return frame or session is established. `7E` is still a
return-direction candidate. Optical arrival at the handheld's amplifier
is owner-confirmed; the internal probe is removed. Do not request another
probe or alignment sweep. Earlier unverified PLINTH/V24 selections prevent
using all negative trials to eliminate conventions.

## Release and implementation

Install **only ROM00** from
`analysis/rom_exerciser/releases/stock-context-v4/micron1_stock_context_v4.bin`.
ROM01 is unchanged. Its adjacent JSON contains every patch and checksum.

| Check | Value |
|---|---|
| Size | 32768 bytes |
| MD5 | `40750ca8c387483001a0348d4cd3ae36` |
| sum16 | `358B` |
| SHA-256 | `2d78a065c49f9a113b45caa074d8d1f12e9b5b1dfce30698974579ec7b375174` |

CONFIRMED by builder bytes and emulator tests: the ROM uses the guarded
zero cave at ROM00:7E96–7FF9 and the existing stock dispatcher call at
ROM00:2FC1. It records the incoming descriptor pointer in scratch RAM,
calls stock `Link_BlockRx` once, emits the previous carry-class yellow
pulse **after return**, then displays **`R4IaaFF`** and stops. `aa` is the
raw hexadecimal A register; `FF` is the raw hexadecimal F register.
The `I` is literal and denotes this dispatch/receive-result diagnostic.
For example, `R4IEExx` has A=`EE`; the final two digits must still be
recorded. F bit 0 is carry. The seven-character prefix is sufficient;
there is no need to transcribe the rest of the screen.

* `EE` with carry set: stock receive timeout.
* `ED` with carry set: descriptor exhaustion.
* `EC` with carry set: stock status-error or short-count exit; A alone
  cannot distinguish those causes.
* Carry clear: stock byte reader returned without its error indication.
  This one-shot diagnostic stops before session/header validation.

The descriptor snapshot at RAM:C7E0–C7E1 and raw F/A at C7E2–C7E3 are
implementation scratch, not an extra owner readout. No LCD or yellow
write precedes the stock receive call. The added wrapper CALL and RAM
snapshot add 33 T-states (about 9 us) before stock receive entry versus
the original direct CALL. A missing display cannot distinguish no
entry from a stuck receive call; if that ambiguity becomes material,
use a separately witnessed entry-only diagnostic rather than treating
absence as protocol rejection. The bounded modeled receive paths all
return in tests, but hardware status behavior is not fully modeled.

The boot/logger witness is now **about 5.451 ms low on yellow**
(20,095 T-states at 3.6864 MHz), distinct from v3's 3.636 ms.
It occurs at common initialization, before menu startup; it is the
installed-image identity witness, not proof of receiving IR. The logger
recognizes this as `v4_boot_signature_candidate` and never associates it
with a preceding transmission. RX pulses retain the earlier approximately
0.9/1.8-ms carry-set/clear widths.

## Coldstart changes and limits

CONFIRMED by guarded bytes and differential execution: ROM00:0172,
01A3, 3812 and retained-state entry 17A5 redirect to cold body 01A6.
The BDOS function-00 table word at ROM00:3708 now points to 01A6;
the copied table at RAM:F1EB and real copied BDOS dispatch are tested.
The common continuation at ROM00:024D is left intact, avoiding a cold
boot loop. Cold boot refreshes the RAM kernel from this new image.

The NMI handler is left intact: modeled states 0 and 2 reach the stock
power-down path; state 1 returns without restarting. The power-down loop
waits for hardware reset; that reset's retained-state branch now enters
cold initialization. No test claims to simulate the analog power/reset
circuit. Confirm the first physical boot shows TESTING and reaches the
menu. Do not interpret an ignored NMI as a warmstart or promise recovery
from arbitrary corrupted retained RAM. **Coldstart resets source selection:
explicitly choose V24 ADAPTOR on every run.**

## Arduino artifacts and last known state

Last verified live state: silent LISTEN_ONLY on `/dev/ttyACM0`.
This preparation pass did not open USB, reset the Uno, upload or transmit.
Yellow is on Uno D8 and scope D4; black remains on undriven D7.
D5/D6 drive the existing IR circuit. The electrical setup is settled.

Archived without recompilation:

* `analysis/arduino/releases/f7-sparse33/m1000_ir_probe.ino.hex`
  SHA-256 `c25dda43b1d3cf3a78bf0d1dc2e2b43dbdda34138aa996a22d7f8fda67210d8f`.
* `analysis/arduino/releases/stock-silent/m1000_ir_probe.ino.hex`
  is the cached LISTEN_ONLY control; verify its banner before use.

Each directory contains a manifest, original build options and compiler
commands. Original absolute paths are provenance, not a portable build
recipe. Both use Uno / AVR core 1.8.8 / avr-gcc 7.3.0-atmel3.6.1-arduino7.
Use the HEX without bootloader with the existing Arduino CLI uploader.
F7 is opening `7E`, stuffing 1, phase +2/8 cell, type-2 payload
`00 07 00 02 01 43 00 00 02 01`, delayed 33 ms after every third full
handheld burst. The amplifier-check free-running build was a different
phase and repetition mode; it is not the F7 control.

## Next agent: test sequence

**Stop and ask the owner plainly before any handheld action.** Start and
verify capture first, then send a standalone request and wait. Do not bury
requests in JSON or let a timed capture expire before the owner starts.

1. Verify release checksums and arrange the new ROM installation. With
   the silent Uno and USB logging already active, ask for a coldstart.
   Record Uno startup banner, a roughly 5.45-ms yellow boot witness,
   TESTING, and arrival at the menu. If the witness is absent, resolve
   image/logger identity before interpreting absent RX events.
2. Still silent, ask for **Load/Run, FOO, V24 ADAPTOR, LOCAL_LINK**.
   Record any `R4I...` prefix or the normal error sequence. A diagnostic
   in this control indicates receive activity without an Arduino reply;
   record it before considering stimulus attribution.
3. Upload the archived F7 HEX and verify its banner. Start a new named
   capture, then ask for the same explicitly selected V24 operation.
   Record the prefix, pulses, full handheld bursts and emitted replies.
   This ROM stops on the first receive return, so 100/34 burst/reply
   totals are no longer an expected completion condition.
4. Repeat the matched silent/F7 pair on fresh coldstarts, confirming V24
   each time. Keep the Uno silent during each boot; enable F7 only for
   the intended stimulated attempt. Stop on inconsistent boot identity,
   event drops, or a result in the silent control that changes attribution.
   Each diagnostic stop needs a fresh coldstart.
5. Preserve each result and exact build identity before selecting a new
   single-variable comparison. No broad payload sweep until repeatable
   controller/stock RX evidence has been obtained. Restore LISTEN_ONLY
   and verify its banner at handover.

Start the existing passive logger with a unique output path, for example:

```sh
python3 analysis/stock_context_log.py --log analysis/captures/stock-v4-silent-boot-01.jsonl --duration 300
```

Capture the banner by resetting the Uno after logging begins. If using
scope CSV, record acquisition sample rate and exported time spacing.
The earlier 40-us export interval can resolve the millisecond markers,
but cannot settle clock/data setup at roughly 122-us cells. Use a separate
short-window, higher-rate acquisition for any edge-timing inference.
Segmented memory remains useful for multiple exchanges; it does not by
itself guarantee an adequate sample rate. The scope is `msox3054a:5025`.

## Reproduction and validation

```sh
analysis/venv/bin/python analysis/rom_exerciser/stock_context_v4.py \
  -o /tmp/micron1_stock_context_v4.bin
analysis/venv/bin/python -m pytest -q analysis/test_stock_context_v3.py \
  analysis/test_stock_instrument.py analysis/test_stock_context_v4.py \
  analysis/test_stock_context_log.py
MICRONIC_ROM0=/tmp/micron1_stock_context_v4.bin timeout 300 \
  analysis/venv/bin/python analysis/boot_hw.py --lcd --max-slices 100000 \
  --expect 'To Continue Press>>:\r' --expect 'serial number:12345678\r' \
  --expect 'Main Menu:'
```

Use **analysis/venv**, whose emulator executes callback-backed memory.
The earlier helper regression has been corrected; PyPI z80 is not an
equivalent substitute. Acceptance: 69 tests pass, release bytes reproduce,
raw A/F match unpatched stock for modeled EE/EC/ED and carry-clear cases,
receive port I/O is identical until return, boot pulse preserves registers,
and stock/patched reset inputs 00/01/03 discriminate correctly.

The canonical harness reached Main Menu with all three expect steps
completed. Its normal RAM-test shortcuts remain enabled: this validates
startup integration through the menu, not a physical destructive RAM test
or a full electrical power-cycle model. The log is archived beside the
ROM as `boot-menu.log.gz`. Physical boot and IR acceptance remain pending.
