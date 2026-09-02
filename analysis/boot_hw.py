#!/usr/bin/env python3
"""boot_hw.py - canonical emulator harness for the Micronic 1000.

Canonical single-harness: paced keyboard injection (--drive-serial/--serial,
--drive-kbd fixed), LCD render (--lcd/--no-lcd/--lcd-rate), expect-DSL
(--expect/--expect-file/--expect-timeout), multi-bank RAM (--ram/--ram-size
FF on absent pages), host upload (--upload), --dump-bank, snapshot
(--dump-mem/--snapshot), --help.
Drop-in: no args still does basic trace (prints help then boots).

Feature history (all folded into this one file):

Key additions over the original self-test boot:

1. LCD DISPLAY  (FC06-FCA5 = 160 bytes = 20 cols × 8 rows, ASCII)
   Verified from firmware: LcdRefreshScreen (ROM00:1E27) streams the
   160-byte buffer at FC06 via lcd_putc (ROM00:1F79) → ports 23h/03h;
   lcd_clear_spaces (ROM00:1Exx) writes 0xA0 (160) space chars to FC06.
   Memory map doc confirms FC06 160 bytes, 20×8 layout.
   Rendered to terminal as 8 rows of 20 chars, home-cursor (\\x1b[H)
   whenever the framebuffer CHANGES (or every --lcd-rate slices).
   Escape/CR/LF/space rendered as space/visible, not raw control.

2. expect-STYLE WAIT DSL
   Express boot as ordered steps: wait until substrings appear in LCD
   text, then inject key bytes.  Steps come from --expect on the CLI
   or --expect-file JSON.  Each step waits for ALL its match substrings
   (AND) to be present, then its keys are paced into the keyboard ring
   exactly like the manual inject path (port 16C9 HALT wait, FBC9 bit2).

3. MULTI-BANK RAM
   Port 47h (BANK_SEL, shadow F791) selects the 32K banked window
   0000-7FFF: 0=ROM0, 1=ROM1, 2..N = RAM pages (32K each).  Fixed RAM
   8000-FFFF is always present (32K).  Default 256K total = 32K fixed +
   7 banked pages (banks 2..8).  --ram 512 → 32K fixed + 15 pages
   (banks 2..16).  Banking is save/restore: on 47h write the current
   low window is written back to its RAM page (if >=2 and <=BANK_MAX)
   before the new window is loaded.  Non-present banks (>BANK_MAX)
   read as 0xFF (unprogrammed RAM / open bus) and writes are discarded;
   this matches hardware and makes --ram 256 report 256K (not 2016K).
   --dump-bank N dumps any 32K page (ROM or RAM); when dumping the
   currently-mapped bank the live window is returned.

Memory safety: single process, timeout 300, --max-slices bounded,
log ring 200k, gc.disable() + manual collect.

USAGE
  analysis/venv/bin/python3 analysis/boot_hw.py [options]
  timeout 300 analysis/venv/bin/python3 analysis/boot_hw.py [options]

OPTIONS
  -h, --help              Show this help and exit. Also shown when no args.
  --drive-serial          Legacy serial-drive: auto-type ENTER, SERIAL_TEXT,
                          ENTER at the banner/key wait (ring injection at
                          0x16C9 when FBC9 bit2 clear). Uses --serial text.
  --serial TEXT           Serial string for --drive-serial (default 12345678).
                          Also accepted as --drive-serial's payload when used
                          with expect DSL via --expect "Serial:TEXT\\r".
  --max-slices N          Max Z80 slices (each ~3400 ticks) before stop.
                          Default 900000. Bounded; use timeout 300 wrapper.
  --dump-bank N           At exit dump 32K bank N to analysis/ram_bank_NN.bin.
                          0=ROM0, 1=ROM1, 2..BANK_MAX=RAM, >BANK_MAX=0xFF-filled.
                          If N is currently mapped, live window is dumped.
  --lcd / --no-lcd        Enable/disable LCD rendering (default on). LCD is the
                          20×8 framebuffer at FC06 rendered via \\x1b[H home.
  --lcd-rate N            Render period: heartbeat every N slices plus on-change.
                          Default 5000 (or on-change only if --lcd given alone
                          in older versions). Lower = more chatter.
  --expect SPEC           Add one expect step. Can be repeated. Grammar:
                            SPEC := MATCH [ :KEYS | ::KEYS | |KEYS ]
                            MATCH := "" (immediate) or substrings joined by
                                     ',' or '&' meaning AND (all must appear).
                                     Example: "Ram:,K.B." waits for both.
                            KEYS  := bytes to inject after match, with escapes.
                          If multiple --expect are given they run in order.
                          When no --expect and --drive-serial is set, legacy
                          queue is used; otherwise expect DSL drives injection.
  --expect-file FILE      JSON file of steps. Each entry is either
                            {"match": "a,b", "keys": "\\r"}  or
                            {"match": ["a","b"], "keys": "\\r"}  or
                            ["match","keys"] tuple.
                          JSON escapes follow python unicode_escape.
  --expect-timeout N      Slices to wait per step before warning+skip (0=forever).
  --ram N / --ram-size N  Total RAM in KB: 128, 256 (default), or 512. Controls
                          banked window size:
                            256K = 32K fixed (8000-FFFF) + 7×32K banks 2..8
                            512K = 32K fixed + 15×32K banks 2..16
                            128K = 32K fixed + 3×32K banks 2..4
                          Banks beyond the configured max read as 0xFF and
                          writes are discarded (Boot_BankWalkInit walks 0x41..1).
  --dump-mem ADDR[:LEN]   Hex-dump RAM at ADDR for LEN bytes (default 16) on
                          each expect match and at exit. Repeatable; also
                          --mem-dump alias. Example: --dump-mem e488:8
                          --dump-mem d0e0:32
  --snapshot / --mem-snapshot
                          Shorthand: dump task-relevant cells on each expect
                          match and at exit: e488,e48d,e48c,e520,d0e0,e681,
                          fbc9,f791 (plus any --dump-mem ranges). Use for
                          chasing "No program in memory" (ROM01:7d07 via d0e0).
  --upload FILE            At Main Menu, feed FILE through the real Load/Run
                           chunk callbacks, finalize it, and invoke Run.
  --upload-name NAME       Logical loader name (default: input basename).
  --upload-bank N          Writable RAM base bank (default 2).
  --upload-max-bytes N     Host-side input bound (default 65535).
  --upload-marker A:V      Require byte V at bank-local address A after entry.
                           Example: --upload-marker 0200:A5.
  --upload-no-run          Load and verify only; do not invoke RunLoadedProgram.
  --trace-session-builder N
                           At Main Menu, execute session TX builder 4 or 5 up
                           to its service-33 call and dump the counted span.
  --trace-session-transaction N
                           Execute builder 4 through a mechanically valid
                           type-2/type-4 service-33 transaction. Payload
                           semantics remain open.
  --trace-loadrun-source NAME
                           Drive the Load/Run PLINTH or V24 ADAPTOR source
                           form and capture its first session TX bytes.
  --trace-loadrun-v24-mode N
                           Select V24 form mode N (0..3) with the raw
                           counter-edit byte before accepting the form.
                           Experimental trace control; not a V24 peer.
  --watch-pc A[,B,...]     Report each time execution reaches a hex address,
                           with registers. Real breakpoints, so nothing is
                           missed. Example: --watch-pc 3277,32b6,3318
  --watch-mem LO:HI[,...]  Report every memory write landing in a hex range.
                           Ranges are INCLUSIVE of both ends (unlike
                           --dump-mem, which takes ADDR:LEN). Each report
                           gives the address, the value, the PC, SP and the
                           current bank. Stack pushes are ordinary writes and
                           are reported too, so a range below a stack top
                           measures how far that stack descends: compare the
                           reported address with SP. Printing stops at
                           --watch-mem-limit per range but COUNTING does not,
                           so a hot region cannot flood the log. At exit each
                           range gets a summary: total writes, the distinct
                           writing PCs with counts, and the lowest/highest
                           address touched. Example:
                             --watch-mem f68d:f77f,ffa9:ffff
  --watch-mem-limit N      Per-range print cap for --watch-mem (default 24).
  --fill-mem LO:HI[,...]   Fill an inclusive hex range of fixed RAM with a
                           marker pattern once, at the point the destructive
                           power-on RAM test would have finished, so the
                           pattern is in place for the whole session. The
                           default pattern is address-derived,
                           mem[a] = (a ^ (a >> 8)) & FF, so a routine writing
                           zeros or a constant cannot hide in it. At exit each
                           range reports how many bytes still hold the pattern
                           and the lowest and highest byte that does not --
                           the survival/low-water mark. Filling live cells
                           (the port shadows at F780-F799, for instance) will
                           break the run; that is the point of the test, but
                           expect it. Example: --fill-mem f68d:f77f
  --fill-mem-value NN      Use the constant hex byte NN for --fill-mem instead
                           of the address-derived pattern. Run a fill twice,
                           once with a value and once with its complement, if
                           you need to rule out a value-dependent write.
  --commstar-peer          Attach the protocol peer to a plain --upload run so
                           a loaded application can hold a Commstar session.
                           Replies come from micronic.peer.CommstarPeer.
  --commstar-serve-program FILE
                           With --commstar-peer, serve FILE to a handheld that
                           drives a program download: the peer answers the
                           C-COMMAND record with OK, then hands the image over
                           in blocks, marking the last.
  --commstar-program-name NAME
                           The program name the handheld must ask for. Default
                           is the empty name, which answers to anything.
  --commstar-chunk N       Bytes per served block (default 126, the largest
                           object the handheld's receive descriptor holds).
  --commstar-reply-delay N Hold each reply back N pump passes. Use to test
                           whether a result depends on answering instantly.
  --slice-ticks N          Emulator ticks per slice (default 3400). The peer is
                           pumped once per slice.
  --trace-loadrun-name TEXT
                           Type TEXT into the Load/Run Name field before
                           choosing the source. Used with --serial to measure
                           which captured frame bytes carry each field.
   --synthetic-loadrun FILE
                           With --trace-loadrun-source, serve FILE as later
                           raw program-data state-44 payloads.
   --synthetic-workflow FILE
                           Load a JSON SyntheticWorkflow manifest for the
                           tested PLINTH image path. Scan records, run intent,
                           feedback, and safe removal remain adapter policy.
  --synthetic-loadrun-finalize
                           Complete a synthetic stream through the ROM loader
                           finalizer after its final payload. This is an
                           adapter-completion policy, not a wire-frame claim.
  --trace-loadrun-debug
                           Bound a stalled synthetic state-44 reply phase and
                           print the link state and captured TX suffix.

BARCODE WAND  (--barcode-*)
  The edge-capture front end (ROM00:13BB) polls EXTBUS_EDGE (port 2Dh) bit 0
  and records how many polls each level lasts. These options attach a wand
  model to that port, so a scan can be driven end to end. Widths are in the
  unit the firmware records -- the value the capture loop pushes into the
  table at F9B5 -- so the widths given here are the widths that land there.
  The model holds each level for width-1 samples to absorb the loop's
  LD HL,1 / INC HL pre-increment.

  Only the two IN A,(2Dh) sites inside the capture loop draw samples
  (ROM00:13CB arming, ROM00:13ED timing). Every other read of the port --
  the device-presence probe at ROM00:12A3, the idle polls at 1302/1317/
  132E/1370 -- sees the quiet line, so they cannot shift the widths.

  --barcode-widths W1,W2,...
                          Element widths, alternating bar, space, bar, ...
                          starting with a bar. 8 is the minimum the firmware
                          accepts (ROM00:13FA SUB 8 restarts the capture
                          below it) and 6143 the maximum (ROM00:13EA ends a
                          capture at 1800h). No more than 128 elements
                          (ROM00:140F CP 80h). This option or --barcode-scan
                          is what enables the wand.
  --barcode-scan TEXT     Encode TEXT as Code 39 and use that instead. The
                          '*' start/stop characters are added for you; '*'
                          may not appear in TEXT. Ten data characters is the
                          most that fits in 128 elements.
  --barcode-narrow N      Narrow-element width for --barcode-scan (default 12)
  --barcode-wide N        Wide-element width for --barcode-scan (default 30)
  --barcode-idle N        Samples of quiet line before the first bar
                          (default 4). The arm loop spins on these.
  --barcode-line2 0|1     Level reported on port 2Dh bit 1, the second line
                          the presence probe at ROM00:12A3 reads (default 0,
                          which makes the probe record device type 2 in
                          F9AB).
  --barcode-probe         Install a decode hook that records the machine
                          state it was entered with -- registers, stack,
                          bank shadow and the parameter block -- then
                          rejects the scan. Use it to measure the hook
                          contract rather than assume it.
  --barcode-decode        Install the Code 39 decoder from
                          micronic/barcode.py as the decode hook.
  --barcode-hook HEX      Install these raw hex bytes as the decode hook.
  --barcode-hook-at ADDR  Where the hook is written (hex, default 9000, in
                          the free upper TPA). The thunk at FBC0 is pointed
                          at it.
  --barcode-hook-bank N   Bank byte written to FBC1 (default 0). When it
                          differs from the bank running the capture, the
                          RST 10h thunk takes its cross-bank path and the
                          hook returns through the kernel's bank-restore
                          trampoline instead of straight to ROM00:1468.
  --barcode-record-at A   Receive buffer handed to the delivery path through
                          FBB7 (hex, default f958, which is where ExtBusArm
                          points it on the real reader channel).
  --barcode-expect TEXT   Assert the decoded scan equals TEXT.
  --barcode-bdos          Read the scan back the way a program would: set
                          the reader channel, then CALL 0005h with C=03h
                          repeatedly and print the byte stream. Without it
                          the capture is driven directly (DI, CALL 13B8),
                          which stops at ROM00:30BD because the delivery
                          tail jumps through the device callback at FDD2
                          and never returns.
  --barcode-device NN     Reader-channel selector written to FBC5 (hex,
                          default 04, which picks FE83+5 = wire 2Bh).
  --barcode-bdos-slices N Slice budget for --barcode-bdos (default 20000).
  --barcode-trampoline-at A
                          Where the harness's DI/CALL stub goes (hex,
                          default f68d, the dead gap below the port
                          shadows).

  Examples:
    # Acceptance test: widths in, matching table out.
    timeout 550 analysis/venv/bin/python3 analysis/boot_hw.py --no-lcd \\
      --max-slices 60000 --expect-timeout 45000 \\
      --expect "To Continue Press>>:\\r" \\
      --expect "Enter the,Workstation:\\r12345678\\r" --expect "Main Menu" \\
      --barcode-scan A1 --barcode-probe --watch-mem f9b5:fbb4

    # Whole path: Code 39 hook, read back through BDOS function 03h.
    ... --barcode-scan A1 --barcode-decode --barcode-bdos --barcode-expect A1

EXPECT DSL GRAMMAR
  match:keys              Wait for match substrings in LCD text (20×8, 160 bytes),
                          then type keys into the keyboard ring (paced, one per
                          HALT loop at 16C9 when FBC9 bit2 clear, FFA8==1).
  AND via commas:         "Ram:,K.B." or "Ram:&K.B." means both "Ram:" AND "K.B."
                          must be visible before advancing. Use --expect-file
                          with ["Ram:","K.B."] list for explicit AND without
                          comma ambiguity.
  Escape sequences:       Keys decode via python unicode_escape plus \\e -> ESC:
                            \\r, \\n -> 0x0D (ENTER; \\n is mapped to \\r for
                                     firmware convenience),
                            \\t      -> 0x09,
                            \\e / \\E -> 0x1B,
                            \\\\     -> \\,
                            \\xNN    -> byte NN hex,
                            \\uNNNN  -> unicode.
                          Example: --expect "To Continue Press>>:\\r"
                                   --expect "Serial:\\r12345678\\r"
                                   --expect "Main Menu:1"

EXAMPLES
  # Watch boot with LCD (default on):
  timeout 300 analysis/venv/bin/python3 analysis/boot_hw.py --lcd --max-slices 300000

  # Drive serial prompt then menu via expect DSL:
  timeout 300 analysis/venv/bin/python3 analysis/boot_hw.py --lcd --expect "To Continue Press>>:\\r" --expect "Serial:\\r12345678\\r" --expect "Main Menu:1"

  # Expect from file + 512K RAM + dump bank 2:
  timeout 300 analysis/venv/bin/python3 analysis/boot_hw.py --ram 512 --expect-file /tmp/steps.json --dump-bank 2

  # Load and run a COM through the ROM loader; require its success marker:
  timeout 300 analysis/venv/bin/python3 analysis/boot_hw.py --no-lcd \
    --upload hello.com --upload-marker 0200:A5

  # JSON steps file example:
  # [{"match": "To Continue Press>>", "keys": "\\r"},
  #  {"match": ["Ram:", "K.B."], "keys": "\\r"},
  #  {"match": "Main Menu", "keys": "1"}]

RAM MODEL
  Port 47h selects 0000-7FFF. Banks 0/1 are ROM. Banks 2..BANK_MAX are RAM
  (bytearray 0x8000 each, save/restore on switch). Banks >BANK_MAX are not
  installed: reads return 0xFF, writes discarded. Installed size is counted
  by contig_ram_map_test (267A) + ram_page_test_4banks (2530); DelayCountUp
  (271F) computes FEAB = FEA9*0x20 (FEA9 = count of 0xFF-probed present pages)
  which is displayed as "Ram: NN K.B." on the banner.

SEE ALSO
  doc/memory-map.md (banking + RAM layout), doc/TASKS.md (RAM SIZE vs SERIAL),
  micronic_notes.md (hardware), analysis/README.md (Emulator section).
"""

import gc

gc.disable()
import sys, re, json, os
from pathlib import Path

sys.path.insert(0, "/home/philpem/Micronic-1000/analysis")
import z80
from micronic.rtc import RTC146818
from micronic.commstar import SyntheticWorkflow
from micronic.program import validate
from micronic import proto
from micronic import barcode
from micronic.z80asm import assemble as z80_assemble


# ---------- CLI args ----------
def get_arg(name, default=None, cast=None):
    if name in sys.argv:
        try:
            v = sys.argv[sys.argv.index(name) + 1]
            return cast(v) if cast else v
        except:
            return default
    # also --name=VALUE
    for a in sys.argv:
        if a.startswith(name + "="):
            v = a.split("=", 1)[1]
            return cast(v) if cast else v
    return default


def has_flag(name):
    return name in sys.argv


# --help / -h handling: print docstring header and exit for explicit help, print for no args
if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)
if len(sys.argv) == 1:
    # Task requires help when no args; show usage but continue with defaults so bare run still boots
    print(__doc__)

# legacy serial drive
DRIVE_SERIAL = has_flag("--drive-serial") or has_flag("--drive-kbd")
SERIAL_TEXT = get_arg("--serial", "12345678")

DUMP_BANK = None
if has_flag("--dump-bank"):
    try:
        DUMP_BANK = int(get_arg("--dump-bank", "0"), 0)
    except:
        DUMP_BANK = None

MAX_SLICES = int(
    get_arg("--max-slices", "900000", cast=lambda x: int(x, 0))
    if has_flag("--max-slices")
    else "900000"
)

# LCD flags
LCD_ENABLED = True
if has_flag("--no-lcd"):
    LCD_ENABLED = False
elif has_flag("--lcd"):
    LCD_ENABLED = True
# default: on when we are going to show it; keep on unless --no-lcd.
# Allow --lcd-rate N
LCD_RATE = None
if has_flag("--lcd-rate"):
    try:
        LCD_RATE = int(get_arg("--lcd-rate", "0"), 0)
    except:
        LCD_RATE = None
# If LCD enabled but no rate, we render on change only (plus periodic heartbeat every 5000 slices for progress)
if LCD_ENABLED and LCD_RATE is None:
    LCD_RATE = 5000  # heartbeat

# RAM size
RAM_KB = 256
if has_flag("--ram"):
    try:
        RAM_KB = int(get_arg("--ram", "256"), 0)
    except:
        RAM_KB = 256
if has_flag("--ram-size"):
    try:
        RAM_KB = int(get_arg("--ram-size", str(RAM_KB)), 0)
    except:
        pass
if RAM_KB not in (256, 512):
    # also allow 128 for testing, but default clamp
    if RAM_KB not in (128, 256, 512):
        print(f"[warn] --ram {RAM_KB} not 256/512, using 256", file=sys.stderr)
        RAM_KB = 256
NUM_BANKED_PAGES = RAM_KB // 32 - 1  # 7 for 256K, 15 for 512K
BANK_MAX = 1 + NUM_BANKED_PAGES  # inclusive max bank number: 8 for 256K, 16 for 512K
# Note: banks 2..BANK_MAX inclusive (2..8 for 256K, 2..16 for 512K)

# Host upload. The ROM loader remains authoritative; host validation only
# rejects malformed or unbounded input before starting the expensive boot.
UPLOAD_PATH = get_arg("--upload") if has_flag("--upload") else None
UPLOAD_NAME = get_arg("--upload-name") if has_flag("--upload-name") else None
UPLOAD_BANK = int(get_arg("--upload-bank", "2"), 0)
UPLOAD_MAX_BYTES = int(get_arg("--upload-max-bytes", "65535"), 0)
UPLOAD_NO_RUN = has_flag("--upload-no-run")
TRACE_SESSION_BUILDER = (
    int(get_arg("--trace-session-builder"), 0)
    if has_flag("--trace-session-builder")
    else None
)
if TRACE_SESSION_BUILDER not in (None, 4, 5):
    print("--trace-session-builder must be 4 or 5", file=sys.stderr)
    sys.exit(2)
TRACE_SESSION_TRANSACTION = (
    int(get_arg("--trace-session-transaction"), 0)
    if has_flag("--trace-session-transaction")
    else None
)
if TRACE_SESSION_TRANSACTION not in (None, 4):
    print("--trace-session-transaction currently supports only 4", file=sys.stderr)
    sys.exit(2)
TRACE_LOADRUN_SOURCE = (
    get_arg("--trace-loadrun-source").lower()
    if has_flag("--trace-loadrun-source")
    else None
)
TRACE_LOADRUN_V24_MODE = (
    int(get_arg("--trace-loadrun-v24-mode"), 0)
    if has_flag("--trace-loadrun-v24-mode")
    else 0
)
# Typed into the Load/Run form's Name field before the source is chosen.
# Used to measure which captured frame bytes carry the program name.
TRACE_LOADRUN_NAME = (
    get_arg("--trace-loadrun-name") if has_flag("--trace-loadrun-name") else ""
)
# Attach the protocol peer to a plain --upload run, so a loaded application
# can hold a Commstar session with something on the other end. Independent of
# the Load/Run phase script, which keeps its own responder.
COMMSTAR_PEER_MODE = has_flag("--commstar-peer")

# --commstar-serve-program FILE  Serve FILE to a handheld that runs a program
# download (C-COMMAND "LOAD" then a C-RX-BLK loop). The peer answers the
# command with OK and then hands the image over in 128-byte blocks, marking
# the last. --commstar-program-name is the name the handheld must ask for;
# omit it and the image answers to any name.
COMMSTAR_SERVE_PROGRAM = (
    get_arg("--commstar-serve-program") if has_flag("--commstar-serve-program") else None
)
COMMSTAR_PROGRAM_NAME = (
    get_arg("--commstar-program-name") if has_flag("--commstar-program-name") else ""
)
COMMSTAR_CHUNK = int(get_arg("--commstar-chunk", "126"), 0)
# --commstar-reply-delay N  Hold each peer reply back N pump passes before
# handing it to the link. A real IR adapter cannot answer instantly, and this
# is how to find out whether a result depends on answering too fast.
COMMSTAR_REPLY_DELAY = int(get_arg("--commstar-reply-delay", "0"), 0)

# --watch-pc ADDR[,ADDR...]  Report every time execution reaches an address.
# Uses real breakpoints, unlike the W counters, which sample the PC between
# emulator slices and therefore miss almost every hit.
WATCH_PC = []
if has_flag("--watch-pc"):
    try:
        WATCH_PC = [int(a, 16) & 0xFFFF
                    for a in get_arg("--watch-pc").replace(" ", "").split(",") if a]
    except ValueError:
        print("--watch-pc takes comma-separated hex addresses", file=sys.stderr)
        sys.exit(2)
watch_hits = {a: 0 for a in WATCH_PC}
WATCH_REPORT_LIMIT = 4


# --watch-mem LO:HI[,LO:HI...]  Report every memory write into a range.
# Hooked into the CPU's write callback, so it sees stack pushes and
# LDIR/LDDR stores as well as ordinary LD (nn),r -- everything the Z80
# writes. Host-side pokes (host_write) bypass it deliberately: they are the
# harness writing, not the firmware.
def parse_watch_ranges(text, option):
    """LO:HI[,LO:HI...] hex, inclusive both ends, normalised low-first."""
    out = []
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        try:
            lo_s, hi_s = part.split(":", 1)
            lo = int(lo_s, 16) & 0xFFFF
            hi = int(hi_s, 16) & 0xFFFF
        except ValueError:
            print(f"{option} takes comma-separated hex LO:HI ranges",
                  file=sys.stderr)
            sys.exit(2)
        out.append((lo, hi) if lo <= hi else (hi, lo))
    return out


WATCH_MEM_RANGES = (
    parse_watch_ranges(get_arg("--watch-mem", ""), "--watch-mem")
    if has_flag("--watch-mem")
    else []
)
WATCH_MEM_REPORT_LIMIT = int(get_arg("--watch-mem-limit", "24"), 0)
# per range: writes seen, lines printed, {pc: count}, {addr: count}
watch_mem_count = {r: 0 for r in WATCH_MEM_RANGES}
watch_mem_printed = {r: 0 for r in WATCH_MEM_RANGES}
watch_mem_pcs = {r: {} for r in WATCH_MEM_RANGES}
watch_mem_addrs = {r: {} for r in WATCH_MEM_RANGES}

# --fill-mem LO:HI[,...] / --fill-mem-value NN
FILL_MEM_RANGES = (
    parse_watch_ranges(get_arg("--fill-mem", ""), "--fill-mem")
    if has_flag("--fill-mem")
    else []
)
FILL_MEM_VALUE = (
    int(get_arg("--fill-mem-value", "00"), 16) & 0xFF
    if has_flag("--fill-mem-value")
    else None
)


def fill_pattern_byte(addr):
    """Address-derived marker: no constant and no zero run can hide in it."""
    if FILL_MEM_VALUE is not None:
        return FILL_MEM_VALUE
    return (addr ^ (addr >> 8)) & 0xFF


# --------------------------------------------------------------------------
# Barcode wand model  (--barcode-*)
#
# The edge-capture front end (ROM00:13BB) polls port 2Dh bit 0 and records
# the number of polls each level lasts. BARCODE_WAND turns a list of element
# widths into that level sequence; ich() hands it one sample per IN A,(2Dh)
# while a capture is running. Widths are in the unit the firmware records,
# so what goes in on the command line is what lands in the table at F9B5.
# --------------------------------------------------------------------------
BARCODE_NARROW = int(get_arg("--barcode-narrow", "12"), 0)
BARCODE_WIDE = int(get_arg("--barcode-wide", "30"), 0)
BARCODE_IDLE = int(get_arg("--barcode-idle", "4"), 0)
BARCODE_LINE2 = int(get_arg("--barcode-line2", "0"), 0)
BARCODE_HOOK_AT = int(get_arg("--barcode-hook-at", "9000"), 16) & 0xFFFF
BARCODE_HOOK = get_arg("--barcode-hook", None)
BARCODE_DECODE = has_flag("--barcode-decode")
BARCODE_PROBE = has_flag("--barcode-probe")
BARCODE_HOOK_BANK = int(get_arg("--barcode-hook-bank", "0"), 0) & 0xFF
BARCODE_BDOS = has_flag("--barcode-bdos")
BARCODE_BDOS_SLICES = int(get_arg("--barcode-bdos-slices", "20000"), 0)
# ((FBC5 >> 2) + 5) & 1Fh indexes the FE83 device table (ROM00:110C /
# ROM00:320B), and the entry is at FE83 + index - 1. 04h therefore picks
# FE83+5, which the ROM ships as 2Bh -- the wire LinkCommandLookup routes
# to ExtBusArm (ROM00:1221).
BARCODE_DEVICE_SELECT = int(get_arg("--barcode-device", "04"), 16) & 0xFF
BARCODE_RECORD_AT = int(get_arg("--barcode-record-at", "f958"), 16) & 0xFFFF
BARCODE_TRAMPOLINE_AT = int(get_arg("--barcode-trampoline-at", "f68d"), 16) & 0xFFFF
BARCODE_EXPECT = get_arg("--barcode-expect", None)

BARCODE_WIDTHS = None
if has_flag("--barcode-widths"):
    try:
        BARCODE_WIDTHS = [int(w, 0) for w in
                          get_arg("--barcode-widths", "").replace(" ", "").split(",") if w]
    except ValueError:
        print("--barcode-widths takes comma-separated integers", file=sys.stderr)
        sys.exit(2)
elif has_flag("--barcode-scan"):
    try:
        BARCODE_WIDTHS = barcode.encode_code39(
            get_arg("--barcode-scan", ""),
            narrow=BARCODE_NARROW, wide=BARCODE_WIDE)
    except barcode.Code39Error as exc:
        print(f"--barcode-scan: {exc}", file=sys.stderr)
        sys.exit(2)

BARCODE_ENABLED = BARCODE_WIDTHS is not None
if BARCODE_ENABLED:
    try:
        BARCODE_WAND = barcode.Wand(BARCODE_WIDTHS, idle=BARCODE_IDLE,
                                    line2=BARCODE_LINE2)
    except barcode.Code39Error as exc:
        print(f"--barcode-widths: {exc}", file=sys.stderr)
        sys.exit(2)
else:
    BARCODE_WAND = None
# The wand only answers port 2Dh once the capture driver arms it, so the
# device probes the firmware runs at other times see a quiet line.
barcode_armed = False
barcode_status = "pending" if BARCODE_ENABLED else None

SYNTHETIC_LOADRUN_PATH = (
    get_arg("--synthetic-loadrun") if has_flag("--synthetic-loadrun") else None
)
SYNTHETIC_WORKFLOW_PATH = (
    get_arg("--synthetic-workflow") if has_flag("--synthetic-workflow") else None
)
synthetic_workflow = None
if SYNTHETIC_WORKFLOW_PATH:
    if SYNTHETIC_LOADRUN_PATH:
        print(
            "--synthetic-workflow cannot be combined with --synthetic-loadrun",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        synthetic_workflow = SyntheticWorkflow.from_file(SYNTHETIC_WORKFLOW_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[synthetic-workflow] invalid manifest: {exc}", file=sys.stderr)
        sys.exit(2)
    if synthetic_workflow.source != "plinth":
        print(
            "[synthetic-workflow] only source 'plinth' has a tested harness path",
            file=sys.stderr,
        )
        sys.exit(2)
    if TRACE_LOADRUN_SOURCE and TRACE_LOADRUN_SOURCE != synthetic_workflow.source:
        print(
            "--trace-loadrun-source disagrees with synthetic workflow source",
            file=sys.stderr,
        )
        sys.exit(2)
    if synthetic_workflow.image is None:
        print("[synthetic-workflow] manifest requires image for this harness", file=sys.stderr)
        sys.exit(2)
    TRACE_LOADRUN_SOURCE = synthetic_workflow.source
    SYNTHETIC_LOADRUN_PATH = str(
        Path(SYNTHETIC_WORKFLOW_PATH).parent / synthetic_workflow.image
    )
    print(
        "[synthetic-workflow] "
        f"scan_records={len(synthetic_workflow.scan_records)} "
        f"run_after_load={synthetic_workflow.run_after_load} "
        f"feedback={synthetic_workflow.feedback} "
        f"safe_to_remove={synthetic_workflow.safe_to_remove}"
    )
if TRACE_LOADRUN_SOURCE not in (None, "plinth", "v24"):
    print("--trace-loadrun-source must be plinth or v24", file=sys.stderr)
    sys.exit(2)
if TRACE_LOADRUN_V24_MODE not in range(4):
    print("--trace-loadrun-v24-mode must be 0 through 3", file=sys.stderr)
    sys.exit(2)
if TRACE_LOADRUN_V24_MODE and TRACE_LOADRUN_SOURCE != "v24":
    print("--trace-loadrun-v24-mode requires --trace-loadrun-source v24", file=sys.stderr)
    sys.exit(2)
SYNTHETIC_LOADRUN_DATA = None
SYNTHETIC_LOADRUN_FINALIZE = has_flag("--synthetic-loadrun-finalize")
SYNTHETIC_RUN_AFTER_LOAD = bool(
    synthetic_workflow is not None and synthetic_workflow.run_after_load
)
TRACE_LOADRUN_DEBUG = has_flag("--trace-loadrun-debug")
if TRACE_LOADRUN_DEBUG and not TRACE_LOADRUN_SOURCE:
    print("--trace-loadrun-debug requires --trace-loadrun-source", file=sys.stderr)
    sys.exit(2)
if SYNTHETIC_LOADRUN_PATH:
    if not TRACE_LOADRUN_SOURCE:
        print("--synthetic-loadrun requires --trace-loadrun-source", file=sys.stderr)
        sys.exit(2)
    synthetic_file = Path(SYNTHETIC_LOADRUN_PATH)
    try:
        SYNTHETIC_LOADRUN_DATA = synthetic_file.read_bytes()
    except OSError as exc:
        print(f"[synthetic-loadrun] cannot read {synthetic_file}: {exc}", file=sys.stderr)
        sys.exit(2)
    synthetic_validation = validate(SYNTHETIC_LOADRUN_DATA)
    if not synthetic_validation.valid:
        for issue in synthetic_validation.errors:
            print(f"[synthetic-loadrun] invalid input: {issue}", file=sys.stderr)
        sys.exit(2)
    print(
        f"[synthetic-loadrun] prepared {synthetic_file} "
        f"({len(SYNTHETIC_LOADRUN_DATA)} bytes, {synthetic_validation.kind})"
    )
elif SYNTHETIC_LOADRUN_FINALIZE:
    print("--synthetic-loadrun-finalize requires --synthetic-loadrun", file=sys.stderr)
    sys.exit(2)
if sum(
    option is not None
    for option in (
        UPLOAD_PATH,
        TRACE_SESSION_BUILDER,
        TRACE_SESSION_TRANSACTION,
        TRACE_LOADRUN_SOURCE,
    )
) > 1:
    print("select only one upload/session trace mode", file=sys.stderr)
    sys.exit(2)
UPLOAD_MARKER = None
if has_flag("--upload-marker"):
    try:
        marker_addr, marker_value = get_arg("--upload-marker").split(":", 1)
        UPLOAD_MARKER = (int(marker_addr, 16), int(marker_value, 16))
    except (AttributeError, TypeError, ValueError):
        print("[upload] --upload-marker must be ADDR:BYTE in hex", file=sys.stderr)
        sys.exit(2)

UPLOAD_DATA = None
UPLOAD_NAME_BYTES = None
validation = None
if UPLOAD_PATH:
    upload_file = Path(UPLOAD_PATH)
    try:
        with upload_file.open("rb") as f:
            UPLOAD_DATA = f.read(UPLOAD_MAX_BYTES + 1)
    except OSError as exc:
        print(f"[upload] cannot read {upload_file}: {exc}", file=sys.stderr)
        sys.exit(2)
    if len(UPLOAD_DATA) > UPLOAD_MAX_BYTES:
        print(
            f"[upload] input exceeds --upload-max-bytes {UPLOAD_MAX_BYTES}",
            file=sys.stderr,
        )
        sys.exit(2)
    validation = validate(UPLOAD_DATA)
    if not validation.valid:
        for issue in validation.errors:
            print(f"[upload] invalid input: {issue}", file=sys.stderr)
        sys.exit(2)
    if UPLOAD_NAME is None:
        UPLOAD_NAME = upload_file.name
    try:
        UPLOAD_NAME_BYTES = UPLOAD_NAME.encode("ascii") + b"\x00"
    except UnicodeEncodeError:
        print("[upload] logical name must be ASCII", file=sys.stderr)
        sys.exit(2)
    if not 2 <= UPLOAD_BANK <= BANK_MAX:
        print(f"[upload] bank {UPLOAD_BANK} is not installed", file=sys.stderr)
        sys.exit(2)
    print(
        f"[upload] prepared {upload_file} ({len(UPLOAD_DATA)} bytes, "
        f"{validation.kind}) as {UPLOAD_NAME!r} in bank {UPLOAD_BANK}"
    )

# ---------- memory snapshot ----------
# --dump-mem ADDR[:LEN] repeatable, e.g. --dump-mem e488:16 --dump-mem d0e0:32
# --snapshot : shorthand for dumping task-relevant cells e488,e48d,e48c,e520,d0e0,e681,fbc9 on each expect match and at exit
DUMP_MEM_RANGES = []
# parse --dump-mem (repeatable, also supports --dump-mem=ADDR:LEN)
args_raw = sys.argv[1:]
j = 0
while j < len(args_raw):
    if args_raw[j] == "--dump-mem" and j + 1 < len(args_raw):
        DUMP_MEM_RANGES.append(args_raw[j + 1])
        j += 2
        continue
    if args_raw[j].startswith("--dump-mem="):
        DUMP_MEM_RANGES.append(args_raw[j].split("=", 1)[1])
        j += 1
        continue
    j += 1
# also allow --mem-dump alias
j = 0
while j < len(args_raw):
    if args_raw[j] == "--mem-dump" and j + 1 < len(args_raw):
        DUMP_MEM_RANGES.append(args_raw[j + 1])
        j += 2
        continue
    if args_raw[j].startswith("--mem-dump="):
        DUMP_MEM_RANGES.append(args_raw[j].split("=", 1)[1])
        j += 1
        continue
    j += 1

SNAPSHOT = (
    has_flag("--snapshot") or has_flag("--dump-snapshot") or has_flag("--mem-snapshot")
)
# task-required cells: e488,e48d,e48c,e520 plus runtime string table d0e0 and related e68x/fbc9
TASK_CELLS = [
    "e488:8",
    "e48d:8",
    "e48c:8",
    "e520:16",
    "d0e0:32",
    "e681:4",
    "fbc9:2",
    "f791:2",
]


def parse_dump_range(spec):
    spec = spec.strip()
    if ":" in spec:
        a_hex, l_hex = spec.split(":", 1)
        try:
            a = int(a_hex, 16)
            l = int(l_hex, 0)
        except:
            a = 0
            l = 16
    else:
        try:
            a = int(spec, 16)
            l = 16
        except:
            a = 0
            l = 16
    return a, l


# build final list for snapshot dumps
SNAPSHOT_RANGES = []
for s in DUMP_MEM_RANGES:
    SNAPSHOT_RANGES.append(parse_dump_range(s))
if SNAPSHOT:
    for s in TASK_CELLS:
        SNAPSHOT_RANGES.append(parse_dump_range(s))
# deduplicate
seen = set()
uniq_ranges = []
for a, l in SNAPSHOT_RANGES:
    if (a, l) not in seen:
        seen.add((a, l))
        uniq_ranges.append((a, l))
SNAPSHOT_RANGES = uniq_ranges


def hexdump_mem(label, addr, length):
    # dump from current mem snapshot (live window + fixed RAM)
    # handle banked window correctly via rd() for 0x0000-0x7FFF? For snapshot we just dump mem array
    # as seen by CPU (current window). For addresses >=0x8000 it's fixed RAM, for <0x8000 it's current bank window.
    try:
        data = bytes(mem[addr : addr + length])
        hexs = " ".join(f"{b:02X}" for b in data)
        ascii_s = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
        print(f"[mem] {label} {addr:04X}:{length:02d} {hexs} |{ascii_s}|")
    except Exception as e:
        print(f"[mem] {label} {addr:04X} err {e}")


print(
    f"[cfg] RAM {RAM_KB}K = 32K fixed + {NUM_BANKED_PAGES}×32K banked (banks 2..{BANK_MAX}), MAX_SLICES={MAX_SLICES}, LCD={'on' if LCD_ENABLED else 'off'} rate={LCD_RATE}, DUMP_BANK={DUMP_BANK} dump_mem={DUMP_MEM_RANGES} snapshot={SNAPSHOT}"
)


# ---------- expect DSL ----------
def parse_keys(s):
    """Decode escape sequences in keys string to bytes.
    Supports \\r, \\n -> 0x0D (ENTER), \\t, \\e (0x1B), \\\\ , \\xNN, \\uNNNN etc via unicode_escape.
    """
    if s is None or s == "":
        return b""
    # python unicode_escape handles \\r \\n \\t \\x \\u
    # Need to handle \\e separately (not standard)
    # Replace \\e with escape char placeholder before decode
    tmp = s.replace("\\e", "\x1b").replace("\\E", "\x1b")
    try:
        decoded = tmp.encode("utf-8").decode("unicode_escape")
    except Exception as e:
        # fallback raw
        decoded = tmp
    # unicode_escape decodes \\r as \r (0x0D) already; keep.
    # Ensure we return latin1 bytes (0..255)
    out = bytearray()
    for ch in decoded:
        out.append(ord(ch) & 0xFF)
    # Special: treat \\n as CR (firmware ENTER is 0x0D) - but keep 0x0A as well; map 0x0A -> 0x0D for convenience
    # Only if user wrote \\n we emitted 0x0A; convert to 0x0D so "press ENTER" works with either
    # Keep both? We'll map 0x0A to 0x0D in the injection path optionally, but leave as is and let firmware accept both?
    # Keep mapping: if they typed \\n we send 0x0A, but firmware expects 0x0D for banner/serial. So convert LF to CR here.
    for i in range(len(out)):
        if out[i] == 0x0A:
            out[i] = 0x0D
    return bytes(out)


def parse_expect_arg(arg):
    """Parse one --expect arg of form 'match1[&,]match2:keys' or 'match|keys'."""
    # Find separator between match and keys: prefer last colon, but also support |
    # Use first colon that is not at start? Simpler: split on last colon where right side looks like keys (may contain escapes).
    # We'll split on first ':' or '|' that gives a keys part which when decoded is plausible. Prefer ':'.
    match_part = arg
    keys_part = ""
    # if arg contains "::" use that
    if "::" in arg:
        idx = arg.find("::")
        match_part = arg[:idx]
        keys_part = arg[idx + 2 :]
    elif ":" in arg:
        # split on last colon to allow colon inside match? But matches rarely contain colon except "To Continue Press>>" no.
        # Use first colon from right where left side not empty? Use rsplit.
        # If match contains colon (unlikely), user can escape or use file. So rsplit is ok but may split keys containing colon.
        # Keys rarely contain colon. So split on first colon.
        idx = arg.find(":")
        # If there are multiple colons, treat first as delimiter, rest as part of keys
        match_part = arg[:idx]
        keys_part = arg[idx + 1 :]
    elif "|" in arg:
        idx = arg.find("|")
        match_part = arg[:idx]
        keys_part = arg[idx + 1 :]
    else:
        match_part = arg
        keys_part = ""
    # split match_part into substrs: comma, &, &&, plus
    substrs = []
    if match_part.strip() != "":
        # split on commas or &'s
        parts = re.split(r"[&,]+", match_part)
        # also handle "&&" already covered, but keep
        substrs = [p.strip() for p in parts if p.strip() != ""]
        # If original contained no delimiter but had e.g. "a|b", already handled
        # Keep as is: if single string with spaces, it's one substr
        if not substrs and match_part.strip():
            substrs = [match_part.strip()]
    else:
        substrs = []  # empty match means immediate
    keys_bytes = parse_keys(keys_part)
    return {"need": substrs, "keys": keys_bytes, "raw": arg}


EXPECT_STEPS = []
# collect repeated --expect args (support --expect "a:b" --expect "c:d")
# Need to handle that sys.argv may have --expect with next token containing spaces (quoted)
args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "--expect" and i + 1 < len(args):
        EXPECT_STEPS.append(parse_expect_arg(args[i + 1]))
        i += 2
        continue
    if args[i].startswith("--expect="):
        EXPECT_STEPS.append(parse_expect_arg(args[i].split("=", 1)[1]))
        i += 1
        continue
    i += 1
# --expect-file
if has_flag("--expect-file"):
    fpath = get_arg("--expect-file", None)
    if fpath and os.path.exists(fpath):
        try:
            data = json.load(open(fpath))
            # data is list of dicts or list of [match,keys]
            for entry in data:
                if isinstance(entry, dict):
                    need = entry.get("match", entry.get("need", ""))
                    # need may be str or list
                    if isinstance(need, str):
                        # split same way
                        need_list = (
                            [
                                s.strip()
                                for s in re.split(r"[&,]+", need)
                                if s.strip() != ""
                            ]
                            if need.strip()
                            else []
                        )
                    elif isinstance(need, list):
                        need_list = [str(s) for s in need]
                    else:
                        need_list = []
                    keys_str = entry.get(
                        "keys", entry.get("press", entry.get("press_keys", ""))
                    )
                    kb = (
                        parse_keys(keys_str)
                        if isinstance(keys_str, str)
                        else bytes(keys_str)
                    )
                    EXPECT_STEPS.append(
                        {"need": need_list, "keys": kb, "raw": str(entry)}
                    )
                elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    need_raw = entry[0]
                    keys_raw = entry[1]
                    if isinstance(need_raw, str):
                        need_list = (
                            [
                                s.strip()
                                for s in re.split(r"[&,]+", need_raw)
                                if s.strip() != ""
                            ]
                            if need_raw.strip()
                            else []
                        )
                    elif isinstance(need_raw, list):
                        need_list = [str(s) for s in need_raw]
                    else:
                        need_list = []
                    kb = (
                        parse_keys(keys_raw)
                        if isinstance(keys_raw, str)
                        else bytes(keys_raw)
                    )
                    EXPECT_STEPS.append(
                        {"need": need_list, "keys": kb, "raw": str(entry)}
                    )
        except Exception as e:
            print(f"[expect-file] failed to load {fpath}: {e}", file=sys.stderr)
    else:
        print(f"[expect-file] not found: {fpath}", file=sys.stderr)

if TRACE_LOADRUN_SOURCE:
    if EXPECT_STEPS:
        print("--trace-loadrun-source cannot be combined with --expect", file=sys.stderr)
        sys.exit(2)
    source_keys = b"\x06\x06\r" if TRACE_LOADRUN_SOURCE == "v24" else b"\x06\r"
    logon_keys = (
        b"\xDB" * TRACE_LOADRUN_V24_MODE + b"\r"
        if TRACE_LOADRUN_SOURCE == "v24"
        else b"\r"
    )
    EXPECT_STEPS.extend(
        [
            parse_expect_arg("To Continue Press>>:\\r"),
            parse_expect_arg(
                f"Enter the,Workstation:\\r{SERIAL_TEXT}\\r"
            ),
            parse_expect_arg("Main Menu:1"),
            {
                "need": ["Name", "From"],
                "keys": TRACE_LOADRUN_NAME.encode() + source_keys,
                "raw": "loadrun source",
            },
            {"need": ["Log-on information"], "keys": logon_keys, "raw": "loadrun logon"},
        ]
    )

# legacy serial drive vs expect: if expect steps supplied, prefer them; otherwise legacy queue
use_legacy_queue = (
    DRIVE_SERIAL
    or UPLOAD_PATH is not None
    or TRACE_SESSION_BUILDER is not None
    or TRACE_SESSION_TRANSACTION is not None
    or TRACE_LOADRUN_SOURCE is not None
) and len(EXPECT_STEPS) == 0

print(f"[expect] steps={len(EXPECT_STEPS)} legacy_queue={use_legacy_queue}")
for idx, st in enumerate(EXPECT_STEPS):
    print(
        f"  step {idx}: need={st['need']!r} keys={st['keys']!r} hex={st['keys'].hex()} raw={st['raw']!r}"
    )

# ---------- memory / banking ----------
B0 = open("/home/philpem/Micronic-1000/micronic/micron1.bin", "rb").read()
B1 = open("/home/philpem/Micronic-1000/micronic/micron2.bin", "rb").read()
mem = bytearray(0x10000)
mem[0:0x8000] = B0
mem[0xD681 : 0xD681 + 0x212] = B0[0x7030:0x7242]
mem[0xF180 : 0xF180 + 0x50D] = B0[0x369D : 0x369D + 0x50D]
pat = bytes([0x21, 1, 0, 0xC9])
for off in range(0xED1C, 0xF180, 4):
    mem[off : off + 4] = pat
mem[0xFD84 : 0xFD84 + 19] = B0[0x2352 : 0x2352 + 19]
mem[0xFE93:0xFEA3] = B0[0x3257:0x3267]
mem[0xFE83:0xFE93] = B0[0x3267:0x3277]
mem[0xFC05] = 0x70
RAM = {}
cb = 0
log = []
# Unmapped bank window: reads return 0xFF, writes discarded. This is critical
# for RAM sizing. Boot_BankWalkInit sweeps banks 0x41..0x01 (64 slots) regardless
# of installed RAM, but only banks 2..BANK_MAX are backed by physical RAM
# (32K fixed 8000-FFFF + N banked 32K pages). DelayCountUp (ROM00:271F) computes
# FEAB = FEA9 * 0x20 where FEA9 = count of present pages from contig_ram_map_test
# (267A) / ram_page_test_4banks (2530) probing for non-0xFF. If missing banks
# read as 0x00 (zero-filled dummy page) the count is inflated: 63*0x20=2016K.
# Correct: banks >BANK_MAX (including 0x41 sweep) must read as 0xFF.
FF_PAGE = bytearray([0xFF] * 0x8000)
# For unmapped banks, keep vector area (0x0000-0x00FF) readable as ROM vectors
# so RST/IRQ still work, but the rest of the window reads as 0xFF (open bus)
# and writes are discarded except for vector area (so BankWalkInit's vector
# replication can succeed). This matches the needed hybrid: RAM tests probe
# at 0x0100+ and see 0xFF, while vectors at 0x0000 remain valid.
VEC_SIZE = 0x100


def rd(a):
    a &= 0xFFFF
    if a < 0x8000 and cb > BANK_MAX:
        if a < VEC_SIZE:
            return mem[a]  # vector area: keep valid so RST/IRQ work
        return 0xFF
    return mem[a]


def note_mem_write(a, v):
    """Record one watched write. mach.pc during a write callback is the
    address of the instruction AFTER the writing one (verified against a
    known LD (nn),HL and a PUSH), so it is reported as pc-after."""
    for r in WATCH_MEM_RANGES:
        if r[0] <= a <= r[1]:
            pc = mach.pc & 0xFFFF
            sp = mach.sp & 0xFFFF
            watch_mem_count[r] += 1
            watch_mem_pcs[r][pc] = watch_mem_pcs[r].get(pc, 0) + 1
            watch_mem_addrs[r][a] = watch_mem_addrs[r].get(a, 0) + 1
            if watch_mem_printed[r] < WATCH_MEM_REPORT_LIMIT:
                watch_mem_printed[r] += 1
                print(
                    f"[watch-mem] {r[0]:04X}-{r[1]:04X} #{watch_mem_count[r]} "
                    f"{a:04X}={v:02X} pc-after={pc:04X} SP={sp:04X} "
                    f"bank={cb:02X}"
                )
                if watch_mem_printed[r] == WATCH_MEM_REPORT_LIMIT:
                    print(
                        f"[watch-mem] {r[0]:04X}-{r[1]:04X} print cap "
                        f"{WATCH_MEM_REPORT_LIMIT} reached; still counting"
                    )


def wr(a, v):
    a &= 0xFFFF
    if WATCH_MEM_RANGES:
        note_mem_write(a, v & 0xFF)
    if a < 0x8000 and cb > BANK_MAX:
        if a < VEC_SIZE:
            mem[a] = v & 0xFF  # allow vector writes for missing banks
            return
        return  # discard writes to unmapped RAM area
    mem[a] = v & 0xFF


def host_write(addr, data):
    """Write while the CPU is paused, keeping both memory views in sync."""
    data = bytes(data)
    addr &= 0xFFFF
    if addr + len(data) > 0x10000:
        raise ValueError("host write wraps address space")
    mem[addr : addr + len(data)] = data
    mach.set_memory_block(addr, data)


def host_write_word(addr, value):
    host_write(addr, bytes([value & 0xFF, (value >> 8) & 0xFF]))


def read_word(addr):
    return mem[addr] | (mem[(addr + 1) & 0xFFFF] << 8)


fill_mem_done = False


def apply_fill_mem():
    """Seed every --fill-mem range with the marker pattern, once."""
    global fill_mem_done
    if fill_mem_done or not FILL_MEM_RANGES:
        return
    fill_mem_done = True
    for lo, hi in FILL_MEM_RANGES:
        host_write(lo, bytes(fill_pattern_byte(a) for a in range(lo, hi + 1)))
        kind = (
            f"value {FILL_MEM_VALUE:02X}"
            if FILL_MEM_VALUE is not None
            else "pattern (a^(a>>8))"
        )
        print(f"[fill-mem] {lo:04X}-{hi:04X} ({hi - lo + 1} bytes) seeded, {kind}")


def report_fill_mem():
    """Which seeded bytes survived, and where the damage starts and ends."""
    for lo, hi in FILL_MEM_RANGES:
        changed = [a for a in range(lo, hi + 1) if mem[a] != fill_pattern_byte(a)]
        total = hi - lo + 1
        if not changed:
            print(
                f"[fill-mem] {lo:04X}-{hi:04X} intact: all {total} bytes still "
                f"hold the marker"
            )
            continue
        print(
            f"[fill-mem] {lo:04X}-{hi:04X} {len(changed)}/{total} bytes changed, "
            f"lowest={changed[0]:04X} highest={changed[-1]:04X}"
        )
        for a in changed[:16]:
            print(
                f"[fill-mem]   {a:04X}: marker {fill_pattern_byte(a):02X} -> "
                f"{mem[a]:02X}"
            )
        if len(changed) > 16:
            print(f"[fill-mem]   ... {len(changed) - 16} more")


def report_watch_mem():
    """Per-range totals: how many writes, from which PCs, over which cells."""
    for r in WATCH_MEM_RANGES:
        lo, hi = r
        n = watch_mem_count[r]
        if not n:
            print(
                f"[watch-mem] {lo:04X}-{hi:04X} totals: 0 writes "
                f"(never written in this run)"
            )
            continue
        addrs = sorted(watch_mem_addrs[r])
        pcs = sorted(watch_mem_pcs[r].items(), key=lambda kv: -kv[1])
        pc_s = " ".join(f"{p:04X}x{c}" for p, c in pcs[:12])
        if len(pcs) > 12:
            pc_s += f" (+{len(pcs) - 12} more PCs)"
        print(
            f"[watch-mem] {lo:04X}-{hi:04X} totals: {n} writes, "
            f"{len(addrs)} distinct addresses {addrs[0]:04X}..{addrs[-1]:04X}, "
            f"{len(pcs)} distinct PCs"
        )
        print(f"[watch-mem] {lo:04X}-{hi:04X} writing PCs (pc-after): {pc_s}")


rtc = RTC146818()
rtc_sel = 0x00
from micronic.peer import CommstarPeer, ProgramDownloadPolicy

# Shadow responder: the protocol-aware peer runs alongside the phase script
# and is asked what it would have replied at each point. It changes nothing;
# it exists to prove the two agree before the script is retired.
# Records the handheld sends us during an application-driven upload.
uploaded_records = []


# Host-to-handheld direction: when --commstar-serve-program names a file, the
# peer runs a real program download instead of the fixed OK object.
program_policy = None
if COMMSTAR_SERVE_PROGRAM:
    _image = open(COMMSTAR_SERVE_PROGRAM, "rb").read()
    program_policy = ProgramDownloadPolicy(
        {COMMSTAR_PROGRAM_NAME: _image}, chunk=COMMSTAR_CHUNK
    )
    print(
        f"[commstar-peer] serving {len(_image)} bytes as "
        f"{COMMSTAR_PROGRAM_NAME or '<any name>'} in {COMMSTAR_CHUNK}-byte blocks"
    )


def _shadow_policy(request):
    """Mirror the phase script's application policy, so any remaining
    difference is a protocol difference rather than a policy one."""
    if request.obj:
        # The handheld sent us data: this is the handheld-to-host direction.
        uploaded_records.append((request.state, request.arg, request.obj))
        print(
            f"[commstar-peer] received {len(request.obj)} bytes from state "
            f"{request.state:#06x}: {request.obj[:24].hex()}"
        )
    if program_policy is not None:
        answer = program_policy(request)
        if answer is not None:
            marker, data = answer
            print(
                f"[commstar-peer] served marker={marker} {len(data)} bytes "
                f"for state {request.state:#06x} size={request.size:#06x}"
            )
        return answer
    if request.state == 0x0044:
        return (1, bytes.fromhex("4f4ba55a3cc3"))   # the OK control object
    return None                                      # plain control ack


shadow_peer = CommstarPeer(on_request=_shadow_policy)
# Replies waiting out --commstar-reply-delay pump passes before they are fed.
_reply_queue = []


def pump_peer(counter):
    """One pump pass: take what the handheld sent, hand back what is due."""
    captured = session_link_peer.peek_tx()
    if len(captured) > counter["tx_seen"]:
        shadow_peer.feed_tx(bytes(captured[counter["tx_seen"]:]))
        counter["tx_seen"] = len(captured)
        for reply in shadow_peer.take_rx():
            _reply_queue.append([COMMSTAR_REPLY_DELAY, reply])
    still = []
    for entry in _reply_queue:
        if entry[0] > 0:
            entry[0] -= 1
            still.append(entry)
            continue
        session_link_peer.feed_rx(entry[1])
        counter["replies"] = counter.get("replies", 0) + 1
        print(f"[commstar-peer] replied {entry[1].hex()}")
    _reply_queue[:] = still
_peer_state = {"tx_seen": 0, "replies": 0}
shadow_tx_seen = 0
shadow_agree = 0
shadow_differ = []
shadow_unsolicited = 0


def feed_rx_checked(queue):
    """Feed the emulator's link peer, comparing against the shadow peer."""
    global shadow_tx_seen, shadow_agree, shadow_unsolicited
    try:
        captured = session_link_peer.peek_tx()
        if len(captured) > shadow_tx_seen:
            shadow_peer.feed_tx(bytes(captured[shadow_tx_seen:]))
            shadow_tx_seen = len(captured)
        expected = shadow_peer.take_rx()
    except Exception as exc:                      # never break a trace over this
        shadow_differ.append(f"shadow error: {exc}")
        expected = []
    if not expected:
        shadow_unsolicited += 1
    elif bytes(queue) == expected[0]:
        shadow_agree += 1
    else:
        shadow_differ.append(
            f"scripted={bytes(queue).hex()} shadow={expected[0].hex()}"
        )
    return session_link_peer.feed_rx(queue)


session_link_peer = (
    proto.LinkPeer(completion_bits=0x02)
    if TRACE_SESSION_TRANSACTION or TRACE_LOADRUN_SOURCE or COMMSTAR_PEER_MODE
    else None
)

# ---------- LCD helpers ----------
FC06 = 0xFC06
FCA5 = 0xFCA5  # inclusive
FB_SIZE = 0xA0  # 160


def lcd_byte_to_char(b):
    """Render one framebuffer byte to a visible terminal char.
    0x00 -> space (cleared), 0x20..0x7E -> as-is, 0x0A/0x0D/0x1B -> space/visible,
    others -> '.' (middle dot would be more visible but '.' is safe)."""
    if b == 0x00:
        return " "  # cleared cell
    if b == 0x1B:
        return " "  # ESC - show as space (could be '␛' but keep ASCII)
    if b in (0x0A, 0x0D):
        return " "  # CR/LF -> space in 20-char row context
    if 0x20 <= b < 0x7F:
        return chr(b)
    # 0xFF etc
    return "."  # or "·"


def get_lcd_text(mem_snapshot=None):
    src = mem if mem_snapshot is None else mem_snapshot
    fb = src[FC06 : FC06 + FB_SIZE]
    # for matching, join rows without newline, but also keep newline version
    txt = "".join(lcd_byte_to_char(b) for b in fb)
    return txt, fb


def render_lcd(fb_bytes, slice_idx, bank):
    txt = "".join(lcd_byte_to_char(b) for b in fb_bytes)
    # cursor home, clear to end? Use home + 8 rows
    # Use \x1b[H to go home, then overwrite. For visibility add slice/bank header.
    out = []
    out.append("\x1b[H")  # home
    # Optional clear below? not full clear to avoid flicker
    out.append(
        f"\x1b[2K--- LCD slice {slice_idx:6d} bank {bank:02X} RAM {RAM_KB}K ---\n"
    )
    for r in range(8):
        row = txt[r * 20 : (r + 1) * 20]
        # render spaces visibly between pipes; keep exactly 20
        out.append(f"\x1b[2K|{row}|\n")
    out.append(
        f"\x1b[2K bank {bank:02X} f791={mem[0xF791]:02X} fbc9={mem[0xFBC9]:02X} ffa8={mem[0xFFA8]:02X}\n"
    )
    sys.stdout.write("".join(out))
    sys.stdout.flush()


# ---------- I/O callbacks ----------
def ich(*a):
    p = a[0]
    p = p[0] if isinstance(p, tuple) else p
    p &= 0xFF
    if p == 0x05:
        return 0x19
    if p == 0x4B:
        if not session_link_peer:
            return 0x80
        if (
            TRACE_LOADRUN_SOURCE
            and loadrun_source_link_phase in (1, 4, 6, 8, 10, 12)
            and session_link_peer.pending_rx == 1
        ):
            # LinkBlockRx consumes the final byte through its bit-2 extra INI
            # path when a seven-byte logical frame fills its descriptor.
            return 0x86
        status = session_link_peer.firmware_status()
        return status | (0x10 if session_link_peer.pending_rx else 0)
    if p == 0x28:
        return rtc.reg_read(rtc_sel) & 0xFF
    if p == 0x00:
        return 0x00
    if p == 0x49:
        return 0x00
    if p == 0x2D:
        # EXTBUS_EDGE. bit0 is the level the capture loop times; bit1 is the
        # second line the device-presence probe at ROM00:12A3 tests.
        #
        # Only the two IN A,(2Dh) sites inside the capture loop advance the
        # wand: ROM00:13CB (arm, wait for the leading edge) and ROM00:13ED
        # (time the current element). Every other read of this port -- the
        # presence probe at 12A3, the idle polls at 1302/1317/132E/1370 --
        # sees the quiet line. Without that gate those polls would eat
        # samples out of the scan and shift every recorded width.
        if BARCODE_WAND is None:
            return 0xFF
        if barcode_armed and (mach.pc & 0xFFFF) in BARCODE_CAPTURE_POLL_PCS:
            return BARCODE_WAND.read()
        return BARCODE_WAND.idle_byte()
    if p == 0x4E:
        return session_link_peer.read_rx() if session_link_peer else 0x00
    if p == 0x4C:
        return 0x00
    if p == 0x48:
        return 0x00
    return 0xFF


out_of_range_warned = set()


def select_bank(value, sync_machine=False):
    """Apply the port-47 bank-window transition."""
    global cb
    value &= 0xFF
    previous = cb
    if 2 <= previous <= BANK_MAX:
        if previous not in RAM:
            RAM[previous] = bytearray(0x8000)
        RAM[previous][:] = mem[0:0x8000]
    cb = value
    mem[0xF791] = value
    if value == 0:
        mem[0:0x8000] = B0
    elif value == 1:
        mem[0:0x8000] = B1
    elif 2 <= value <= BANK_MAX:
        mem[0:0x8000] = RAM.setdefault(value, bytearray(0x8000))
    else:
        mem[0x100:0x8000] = FF_PAGE[0x100:0x8000]
    if sync_machine:
        mach.set_memory_block(0, bytes(mem[0:0x8000]))
        mach.set_memory_block(0xF791, bytes([value]))


def och(*a):
    global cb, rtc_sel
    p, v = (a[0], a[1]) if len(a) >= 2 else (a[0], 0xFF)
    p = p[0] if isinstance(p, tuple) else p
    p &= 0xFF
    v &= 0xFF
    if len(log) < 200000:
        log.append((mach.pc & 0xFFFF, p, v))
    if p == 0x47:
        select_bank(v)
    elif p == 0x08:
        rtc_sel = v & 0xFF
    elif p == 0x28:
        rtc.reg_write(rtc_sel, v)
    elif session_link_peer and p == proto.PORT_TX:
        session_link_peer.write_tx(v)
    elif session_link_peer and p == proto.PORT_CTRL:
        session_link_peer.write_control(v)
    elif session_link_peer and p == proto.PORT_CMD:
        session_link_peer.write_command(v)
    elif session_link_peer and p == proto.PORT_PROBE:
        session_link_peer.write_probe(v)


mach = z80.Z80Machine()
mach.set_memory_block(0, bytes(mem))
mach.set_read_callback(rd)
mach.set_write_callback(wr)
mach.set_input_callback(ich)
mach.set_output_callback(och)
mach.pc = 0x014B
mach.sp = 0xF000
mem[0xFBD0:0xFBD2] = bytes([0, 0xF0])
mem[0x289E] = 0xC9
mem[0xFDB7] = 0xFF
mem[0xFDB6] = 0x00
CPU_HZ = 3_579_545
# Emulator time per slice. The peer is pumped once per slice, so this also
# sets how promptly a reply reaches the handheld; --slice-ticks exists to test
# whether a result depends on that (it should not).
SLICE_TICKS = int(get_arg("--slice-ticks", "3400"), 0)
rtc_phase = 0
rtc_phase_rate = None


CALL_SENTINEL = 0xFFFF
# The logical name lived at D600h, which is above the loader's D081h program
# ceiling but *inside the loaded program's stack*: RunLoadedProgram sets
# SP = D681h (ram:D7FA / ROM00:71A9, `31 81 D6`) and the stack grows down, so
# D600h is 81h bytes into it. Never observed failing -- the stack is shallow
# where the name is read -- but it is the same collision class as the staging
# overrun described below, so it moves to the free span under the ceiling.
# See doc/re-notes/unbanked-ram-map.md.
UPLOAD_NAME_ADDR = 0xC000
# Input chunks deliberately impersonate the service-33 receive payload object,
# so this address is correct for that path specifically and is not general
# scratch.
#
# VERSION-FRAGILE. E5C2h is where *this* ROM image puts the receive object;
# it is not an architectural constant. Another ROM version may lay its OS
# structures out differently, and nothing here would detect that -- the
# symptom would be the same silent corruption of whatever occupies the
# address instead. Anything that has to survive a ROM change should locate
# the object from the firmware rather than hard-coding it, or at minimum
# assert the surrounding structure looks as expected before writing. The
# same caveat applies to every other absolute address in this file.
UPLOAD_BUFFER_ADDR = 0xE5C2
# Cap a staged chunk at what a real receive can hold. The service-33 receive
# object is 134 bytes at ram:E5BC with its body 8 bytes in, so the firmware
# never writes past ram:E641; staging 256 bytes here reached ram:E6C1 and
# buried live Commstar session state under the host file -- among it
# ram:E69F-E6B3, the buffer SessionRxByteGet (ROM00:65C2) reads and the
# 16-bit count at ram:E6A9 it tests and decrements, called from
# SessionRxByteLoop at ROM00:5A21. What survived in that window was whatever
# the final short chunk did not overwrite, so it was a function of the image
# length, and a loaded program opening a session read it back. CONFIRMED by
# bisection: a 561-byte driver aborted its first 0064 exchange with result 4
# (SessionRxByteLoop's error, which ROM00:60D6 latches in ram:E681 and aborts
# on), and restoring ram:E6AA alone -- no other byte of the window -- fixed
# it; forcing ram:E6AA to 01h or 06h reproduced it in a 560-byte driver that
# otherwise passed, while thirteen other values did not. E6AA alone is not
# the whole rule: 569- and 577-byte drivers carry the same ram:E6A9/E6AA pair
# and pass, so other residue in the window participates. Hence the belt and
# braces -- cap the writes, then put the window back, so an upload leaves the
# session nothing to read.
UPLOAD_BUFFER_MAX = 126


def advance_rtc(elapsed_ticks):
    """Advance the RTC phase by measured CPU ticks and deliver active INTs."""
    global rtc_phase, rtc_phase_rate
    rate_hz = round(rtc.periodic_hz)
    if rate_hz != rtc_phase_rate:
        rtc_phase = 0
        rtc_phase_rate = rate_hz
    rtc_phase += elapsed_ticks * rate_hz
    while rate_hz and rtc_phase >= CPU_HZ:
        rtc_phase -= CPU_HZ
        rtc.push_tick()
        if mem[0xFFA8] != 0:
            try:
                mach.on_handle_active_int()
            except Exception:
                pass


def run_to_breakpoint(address, max_chunks=200000, drive_rtc=False):
    mach.set_breakpoint(address)
    try:
        for _ in range(max_chunks):
            mach.ticks_to_stop = SLICE_TICKS
            event = mach.run()
            if drive_rtc:
                advance_rtc(SLICE_TICKS - mach.ticks_to_stop)
            if (mach.pc & 0xFFFF) == address or event & mach._BREAKPOINT_HIT:
                return True
    finally:
        mach.clear_breakpoint(address)
    return False


def call_rom1(entry, args=()):
    """Call a verified ROM01 coroutine entry with stack-word arguments."""
    select_bank(1, sync_machine=True)
    original_sp = mach.sp
    call_sp = (original_sp - 2 * (1 + len(args))) & 0xFFFF
    host_write_word(call_sp, CALL_SENTINEL)
    for index, arg in enumerate(args):
        host_write_word(call_sp + 2 + 2 * index, arg)
    mach.sp = call_sp
    mach.pc = entry
    if not run_to_breakpoint(CALL_SENTINEL):
        raise RuntimeError(f"ROM01:{entry:04X} did not return")
    result = mach.hl
    mach.sp = original_sp
    return result


def prepare_call(bank, entry, args):
    """Prepare a coroutine entry without imposing a return condition."""
    select_bank(bank, sync_machine=True)
    original_sp = mach.sp
    call_sp = (original_sp - 2 * (1 + len(args))) & 0xFFFF
    host_write_word(call_sp, CALL_SENTINEL)
    for index, arg in enumerate(args):
        host_write_word(call_sp + 2 + 2 * index, arg)
    mach.sp = call_sp
    mach.pc = entry
    return original_sp


def trace_session_builder(form):
    """Execute a real TX builder to its service-33 dispatch boundary."""
    host_write_word(0xE6E6, 0)
    if form == 4:
        entry = 0x5BF7
        args = (1, 6, 0x22, 0x33)
        local_addr, local_len = 0xE650, 8
        preflight_call, preflight_return = 0x5C1F, 0x5C22
    else:
        entry = 0x5CD7
        args = (1, 6, 1, 0x44, 0x55)
        local_addr, local_len = 0xE65C, 13
        preflight_call, preflight_return = 0x5D05, 0x5D08
    prepare_call(0, entry, args)
    if not run_to_breakpoint(preflight_call):
        raise RuntimeError(f"session builder {form} did not reach preflight")
    # The preflight starts a separate link transaction. Bypass only that call
    # so the deterministic builder body can be observed without a peer.
    mach.hl = 0
    mach.pc = preflight_return
    if not run_to_breakpoint(0x59CD):
        raise RuntimeError(f"session builder {form} did not reach service 33")
    count = read_word(0xE530)
    payload = bytes(mem[0xE534 : 0xE534 + count])
    selector = read_word(0xE52E) & 0xFF
    print(
        f"[session-builder] form={form} device_selector={selector:02X} "
        f"payload_count={count} pointer=E534"
    )
    print(
        f"[session-builder] local {local_addr:04X}+{local_len}: "
        f"{bytes(mem[local_addr:local_addr + local_len]).hex()}"
    )
    print(f"[session-builder] session payload: {payload.hex()}")
    print(f"[session-builder] E530-E549: {bytes(mem[0xE530:0xE54A]).hex()}")
    log_start = len(log)
    if not run_to_breakpoint(0x3277):
        raise RuntimeError(f"session builder {form} did not reach LinkBlockTx")
    if not run_to_breakpoint(0x3377):
        raise RuntimeError(f"session builder {form} did not finish LinkBlockTx")
    wire = bytes(value for _, port, value in log[log_start:] if port == 0x4D)
    config_addr = 0xFE83 + selector - 1 if selector else None
    config_text = (
        f"{config_addr:04X}={mem[config_addr]:02X}" if config_addr else "none"
    )
    print(
        f"[session-builder] config={config_text} FDCA={mem[0xFDCA]:02X} "
        f"FDD4={mem[0xFDD4]:02X}"
    )
    print(f"[session-builder] LINK_TXD bytes: {wire.hex()}")
    return True


def trace_session_transaction(form):
    """Run one mechanics-only service-33 transaction through the session code."""
    if form != 4 or session_link_peer is None:
        raise RuntimeError("only session transaction form 4 is supported")

    host_write_word(0xE6E6, 0)
    prepare_call(0, 0x5BF7, (1, 6, 0x22, 0x33))
    if not run_to_breakpoint(0x5C1F):
        raise RuntimeError("transaction did not reach separate preflight")
    mach.hl = 0
    mach.pc = 0x5C22

    if not run_to_breakpoint(0x59CD):
        raise RuntimeError("transaction did not reach service-33 launch")
    payload_count = read_word(0xE530)
    rx_capacity = read_word(0xE5BA)
    payload = bytes(mem[0xE534 : 0xE534 + payload_count])
    expected_payload = bytes.fromhex("060000008000004c00002233000005")
    if payload_count != 15 or payload != expected_payload or rx_capacity != 6:
        raise RuntimeError(
            "unexpected service-33 objects: "
            f"tx_count={payload_count} rx_capacity={rx_capacity} "
            f"payload={payload.hex()}"
        )
    print(
        "[session-transaction] service33 "
        f"selector={read_word(0xE52E) & 0xFF:02X} "
        f"tx_count={payload_count} rx_capacity={rx_capacity}"
    )

    session_link_peer.drain_tx()
    if not run_to_breakpoint(0x2E02):
        raise RuntimeError("transaction did not enter service 33")
    if not run_to_breakpoint(0x3277) or not run_to_breakpoint(0x3377):
        raise RuntimeError("initial logical frame did not complete")
    initial_wire = session_link_peer.drain_tx()
    expected_initial = bytes.fromhex(
        "03150001017f00060000008000004c00002233000005"
    )
    if initial_wire != expected_initial:
        raise RuntimeError(f"unexpected initial wire bytes: {initial_wire.hex()}")
    print(f"[session-transaction] initial TX: {initial_wire.hex()}")

    link_id = mem[0xFDD4]
    sequence_addr = 0xFE43 + (link_id & 0x3F)
    sequence = mem[sequence_addr]
    phase1 = bytes(
        [
            0,
            6,
            0,
            2,
            sequence,
            link_id,
            0,
            2,
            sequence,
        ]
    )
    session_link_peer.feed_rx(phase1)
    print(f"[session-transaction] phase1 RX queue: {phase1.hex()}")
    if not run_to_breakpoint(0x31B6, drive_rtc=True):
        raise RuntimeError(
            "RX poll event not reached: "
            f"pending={session_link_peer.pending_rx} state={mem[0xFDD5]:02X}"
        )
    if not run_to_breakpoint(0x302C, drive_rtc=True):
        raise RuntimeError(
            "type-2 branch not reached: "
            f"pending={session_link_peer.pending_rx} state={mem[0xFDD5]:02X}"
        )
    if session_link_peer.pending_rx:
        raise RuntimeError("phase1 queue was not fully consumed")

    if not run_to_breakpoint(0x3277, drive_rtc=True) or not run_to_breakpoint(
        0x3377, drive_rtc=True
    ):
        raise RuntimeError("numeric type-3 reply did not complete")
    reply_wire = session_link_peer.drain_tx()
    expected_reply = bytes([link_id & 0x1F, 6, 0, 3, sequence, 0x7F, 0])
    if reply_wire != expected_reply:
        raise RuntimeError(f"unexpected numeric type-3 reply: {reply_wire.hex()}")
    print(f"[session-transaction] numeric type-3 TX: {reply_wire.hex()}")

    phase2 = bytes([0, 6, 0, 4, sequence, link_id, 0, 4, sequence])
    session_link_peer.feed_rx(phase2)
    print(f"[session-transaction] phase2 RX queue: {phase2.hex()}")
    if not run_to_breakpoint(0x3084, drive_rtc=True):
        raise RuntimeError("type-4 processing was not reached")
    if not run_to_breakpoint(0x31AB, drive_rtc=True):
        raise RuntimeError("type-4 sequence was not accepted")
    if not run_to_breakpoint(0x2E85, drive_rtc=True):
        raise RuntimeError("service-33 completion callback was not reached")
    if not run_to_breakpoint(0x31C1, drive_rtc=True):
        raise RuntimeError("completion callback did not return to RX poll")
    if session_link_peer.pending_rx:
        raise RuntimeError("phase2 queue was not fully consumed")

    received = bytes(mem[0xE5BC:0xE5C3])
    if received != bytes([0, 0, 2, sequence, 0, 0, 0]):
        raise RuntimeError(f"unexpected receive object: {received.hex()}")
    print(f"[session-transaction] receive object E5BC-E5C2: {received.hex()}")

    if not run_to_breakpoint(0x5A81, drive_rtc=True):
        raise RuntimeError(
            "session RX state machine was not entered: "
            f"E644-E64F={bytes(mem[0xE644:0xE650]).hex()}"
        )
    if not run_to_breakpoint(0x5B07, drive_rtc=True):
        raise RuntimeError("zero-payload status poll did not take its loop edge")
    if read_word(0xE644) != 0 or read_word(0xE646) != 2:
        raise RuntimeError(
            "unexpected zero-payload state: "
            f"length={read_word(0xE644):04X} numeric={read_word(0xE646):04X}"
        )
    if not run_to_breakpoint(0x5A13, drive_rtc=True):
        raise RuntimeError("zero-payload cycle did not resume internal polling")
    print(
        "[session-transaction] zero-payload poll cycle complete: "
        "length=0000 retained_numeric=0002"
    )
    return True


def bank_bytes(bank, addr, length):
    end = addr + length
    if addr >= 0x8000:
        return bytes(mem[addr:end])
    window_end = min(end, 0x8000)
    if bank == cb:
        data = bytes(mem[addr:window_end])
    else:
        data = bytes(RAM.get(bank, bytearray(0x8000))[addr:window_end])
    if end > 0x8000:
        data += bytes(mem[0x8000:end])
    return data


def run_loaded_program(name_addr, entry_addr, prefix, marker=None, marker_bank=None):
    """Invoke Program_RunByName and stop at the loaded entry/marker."""
    select_bank(1, sync_machine=True)
    original_sp = mach.sp
    call_sp = (original_sp - 4) & 0xFFFF
    host_write_word(call_sp, CALL_SENTINEL)
    host_write_word(call_sp + 2, name_addr)
    mach.sp = call_sp
    mach.pc = 0x106F
    if not run_to_breakpoint(0xD7F0):
        raise RuntimeError("Program_RunByName did not reach RunLoadedProgram")
    if not run_to_breakpoint(entry_addr):
        raise RuntimeError(f"RunLoadedProgram did not reach {entry_addr:04X}")
    print(f"[{prefix}] execution entered bank {cb} at {entry_addr:04X}")
    if marker is None:
        return True
    marker_addr, marker_value = marker
    for _ in range(20000):
        if bank_bytes(marker_bank, marker_addr, 1) == bytes([marker_value]):
            print(f"[{prefix}] marker {marker_addr:04X}={marker_value:02X} observed")
            return True
        mach.ticks_to_stop = SLICE_TICKS
        mach.run()
        # Drive the RTC here as the main loop does. Without it no periodic
        # interrupt fires, so the link receive path never runs and a loaded
        # program that starts a Commstar session can transmit but never hear
        # the reply.
        advance_rtc(SLICE_TICKS - mach.ticks_to_stop)
        # The loaded program runs in this loop, not the main one, so the
        # --watch-pc reporting has to happen here as well.
        wpc = mach.pc & 0xFFFF
        if wpc in watch_hits:
            watch_hits[wpc] += 1
            if watch_hits[wpc] <= WATCH_REPORT_LIMIT:
                print(
                    f"[watch-pc] {wpc:04X} hit#{watch_hits[wpc]} bank={cb:02X} "
                    f"AF={mach.af:04X} BC={mach.bc:04X} DE={mach.de:04X} "
                    f"HL={mach.hl:04X} SP={mach.sp:04X} F794={mem[0xF794]:02X}"
                )
        if COMMSTAR_PEER_MODE and session_link_peer is not None:
            pump_peer(_peer_state)
    raise RuntimeError(
        f"marker {marker_addr:04X}={marker_value:02X} not observed"
    )


# --------------------------------------------------------------------------
# Barcode capture driver
#
# Runs one edge capture the way ExtBusArmWindow (ROM00:1382) does: DI, then
# CALL ROM00:13B8. Interrupts must be off because the capture parks the real
# SP in FBBD and repurposes SP as the width-table pointer, so any interrupt
# push would land in the table.
#
# The trampoline lives in the dead gap at F68D-F77F (see
# doc/re-notes/unbanked-ram-map.md: no firmware reference, zero writes across
# every driven workload), so it displaces nothing.
# --------------------------------------------------------------------------
BARCODE_CAPTURE_ENTRY = 0x13B8
# The PC reported inside an input callback is the address after the IN, so
# both spellings of each of the two capture-loop poll sites are accepted.
BARCODE_CAPTURE_POLL_PCS = frozenset((0x13CB, 0x13CD, 0x13ED, 0x13EF))
# ExtBusComplete (ROM00:14A3) tail-calls LinkResetSession (ROM00:30BD), which
# posts the completion event and jumps through the device callback at FDD2.
# It never comes back, so a synthetic capture has to stop there; by that point
# the whole delivery record has already been written.
BARCODE_DELIVERY_DONE = 0x30BD
BARCODE_HOOK_THUNK = 0xFBC0     # D7 = RST 10h, bank, address lo, address hi
BARCODE_PARAM_BLOCK = 0xFBB9    # table pointer, then 16-bit element count
BARCODE_TABLE = 0xF9B5
BARCODE_RAW_COUNT = 0xF9B4
BARCODE_RESULT_BUFFER = 0xFBB7  # ExtBusArm's caller-supplied receive buffer


def barcode_install_hook():
    """Point the FBC0 thunk at whichever hook this run asked for."""
    if BARCODE_PROBE:
        code, syms = barcode.assemble_probe(BARCODE_HOOK_AT)
        kind = "probe"
    elif BARCODE_DECODE:
        code, syms = barcode.assemble_decoder(BARCODE_HOOK_AT)
        kind = "code39"
    elif BARCODE_HOOK:
        code, syms = bytes.fromhex(BARCODE_HOOK.replace(" ", "")), {}
        kind = "raw"
    else:
        return None, {}, "none (firmware discard hook at ROM00:1567)"
    host_write(BARCODE_HOOK_AT, code)
    host_write(BARCODE_HOOK_THUNK,
               bytes([0xD7, BARCODE_HOOK_BANK,
                      BARCODE_HOOK_AT & 0xFF, BARCODE_HOOK_AT >> 8]))
    print(f"[barcode] hook {kind}: {len(code)} bytes at {BARCODE_HOOK_AT:04X}, "
          f"thunk FBC0 = {bytes(mem[0xFBC0:0xFBC4]).hex()}")
    return code, syms, kind


def barcode_report_probe(syms):
    """Print the machine state the probe recorded at hook entry."""
    if not syms:
        return
    word = lambda name: read_word(syms[name])  # noqa: E731
    calls = mem[syms["p_calls"]]
    print(f"[barcode] hook entered {calls} time(s)")
    if not calls:
        return
    print(f"[barcode] hook entry AF={word('p_af'):04X} BC={word('p_bc'):04X} "
          f"DE={word('p_de'):04X} HL={word('p_hl'):04X} "
          f"IX={word('p_ix'):04X} IY={word('p_iy'):04X} "
          f"SP={word('p_sp'):04X} F791={mem[syms['p_bank']]:02X}")
    param = bytes(mem[syms["p_param"]:syms["p_param"] + 4])
    print(f"[barcode] hook entry FBB9..FBBC = {param.hex()} "
          f"(table {param[0] | param[1] << 8:04X}, count "
          f"{param[2] | param[3] << 8})")
    stack = bytes(mem[syms["p_stk"]:syms["p_stk"] + 16])
    words = " ".join(f"{stack[i] | stack[i + 1] << 8:04X}"
                     for i in range(0, 16, 2))
    print(f"[barcode] hook entry stack from SP: {words}")


def perform_barcode_bdos():
    """Read one scan out through BDOS function 03h, the way a program would.

    Nothing here is synthetic except the wand and the hook: the firmware
    selects the reader channel from the FE83 device table, arms the front
    end through ExtBusArm, runs the capture as its own work item, calls the
    decode hook, and delivers the result. This harness only calls
    CALL 0005h with C=03h, repeatedly, and records what comes back in A.
    """
    global barcode_armed
    _, syms, kind = barcode_install_hook()
    host_write(0xFBC5, bytes([BARCODE_DEVICE_SELECT]))
    index = ((BARCODE_DEVICE_SELECT >> 2) + 5) & 0x1F
    wire = mem[0xFE83 + index - 1]
    print(f"[barcode] BDOS reader channel: FBC5={BARCODE_DEVICE_SELECT:02X} "
          f"-> FE83+{index - 1} = wire {wire:02X}")

    want = BARCODE_EXPECT if BARCODE_EXPECT is not None else ""
    reads = 2 + len(want) if want else 6
    body = "".join(f"    ld  c,3\n    call 0x0005\n    ld  (buf+{k}),a\n"
                   for k in range(reads))
    tramp, tsyms = z80_assemble(
        f"{body}    ret\nbuf: ds {reads}\n", origin=BARCODE_TRAMPOLINE_AT)
    host_write(BARCODE_TRAMPOLINE_AT, tramp)

    barcode_armed = True
    original_sp = prepare_call(0, BARCODE_TRAMPOLINE_AT, ())
    mach.set_breakpoint(CALL_SENTINEL)
    returned = False
    try:
        for _ in range(BARCODE_BDOS_SLICES):
            mach.ticks_to_stop = SLICE_TICKS
            mach.run()
            advance_rtc(SLICE_TICKS - mach.ticks_to_stop)
            if (mach.pc & 0xFFFF) == CALL_SENTINEL:
                returned = True
                break
    finally:
        mach.clear_breakpoint(CALL_SENTINEL)
        barcode_armed = False
    mach.sp = original_sp
    stream = bytes(mem[tsyms["buf"]:tsyms["buf"] + reads])
    print(f"[barcode] fn 03h returned {'' if returned else '(TIMED OUT) '}"
          f"{stream.hex()}  {stream!r}")
    print(f"[barcode] wand: {BARCODE_WAND.reads} port-2Dh reads, "
          f"{BARCODE_WAND.transitions} level changes; "
          f"F9B4={mem[0xF9B4]} F9AB={mem[0xF9AB]:02X} FBB5={mem[0xFBB5]:02X}")
    print(f"[barcode] envelope F958: {bytes(mem[0xF958:0xF970]).hex()}")
    if not returned:
        return False
    if want:
        expect_stream = bytes([0x1B, len(want)]) + want.encode("ascii")
        if stream == expect_stream:
            print(f"[barcode] PASS: fn 03h stream {stream!r} == "
                  f"1Bh, count, data")
            return True
        print(f"[barcode] FAIL: fn 03h stream {stream!r} != {expect_stream!r}")
        return False
    return True


def perform_barcode_capture():
    """Drive one capture end to end and report what the firmware recorded."""
    global barcode_armed
    _, syms, kind = barcode_install_hook()

    # Give the delivery path (ROM00:1470) a buffer of its own. Without this it
    # would write through whatever ExtBusArm last left in FBB7.
    host_write_word(BARCODE_RESULT_BUFFER, BARCODE_RECORD_AT)
    host_write(BARCODE_RECORD_AT, b"\x00" * 32)

    tramp_src = f"""
        di
        call {BARCODE_CAPTURE_ENTRY:#06x}
        sbc a,a          ; FF when the capture returned carry (failed)
        ld  (result),a
        ret
result: db 0
"""
    tramp, tsyms = z80_assemble(tramp_src, origin=BARCODE_TRAMPOLINE_AT)
    host_write(BARCODE_TRAMPOLINE_AT, tramp)

    barcode_armed = True
    original_sp = prepare_call(0, BARCODE_TRAMPOLINE_AT, ())
    hook_bp = BARCODE_HOOK_AT if kind != "none" else None
    if hook_bp is not None:
        mach.set_breakpoint(hook_bp)
    mach.set_breakpoint(CALL_SENTINEL)
    mach.set_breakpoint(BARCODE_DELIVERY_DONE)
    returned = False
    delivered = False
    try:
        for _ in range(4000):
            mach.ticks_to_stop = SLICE_TICKS
            mach.run()
            pc = mach.pc & 0xFFFF
            if pc == BARCODE_DELIVERY_DONE:
                delivered = True
                print("[barcode] delivery complete: reached LinkResetSession "
                      "(ROM00:30BD); stopping before it jumps through (FDD2)")
                break
            if pc == hook_bp:
                print(f"[barcode] hook reached: PC={pc:04X} AF={mach.af:04X} "
                      f"BC={mach.bc:04X} DE={mach.de:04X} HL={mach.hl:04X} "
                      f"IX={mach.ix:04X} IY={mach.iy:04X} SP={mach.sp:04X} "
                      f"bank={cb:02X}")
                stack = [read_word(mach.sp + 2 * k) for k in range(6)]
                print("[barcode] stack at hook entry: "
                      + " ".join(f"{w:04X}" for w in stack))
                mach.clear_breakpoint(hook_bp)
                hook_bp = None
                continue
            if pc == CALL_SENTINEL:
                returned = True
                break
    finally:
        if hook_bp is not None:
            mach.clear_breakpoint(hook_bp)
        mach.clear_breakpoint(CALL_SENTINEL)
        mach.clear_breakpoint(BARCODE_DELIVERY_DONE)
        barcode_armed = False
    if not returned and not delivered:
        print(f"[barcode] capture did not return; PC={mach.pc & 0xFFFF:04X}",
              file=sys.stderr)
    mach.sp = original_sp

    failed = 0 if delivered else mem[tsyms["result"]]
    raw_count = mem[BARCODE_RAW_COUNT]
    print(f"[barcode] wand: {len(BARCODE_WIDTHS)} elements fed, "
          f"{BARCODE_WAND.reads} port-2Dh reads, "
          f"{BARCODE_WAND.transitions} level changes")
    outcome = ("delivered to the receive buffer" if delivered
               else "carry set: no data delivered" if failed
               else "carry clear")
    print(f"[barcode] capture outcome: {outcome}"
          f", F9B4 element count = {raw_count}")
    recorded = [read_word(BARCODE_TABLE + 2 * k) for k in range(min(raw_count, 128))]
    print(f"[barcode] recorded widths ({len(recorded)}): {recorded}")
    ok = recorded == BARCODE_WIDTHS
    print(f"[barcode] widths match input: {ok}")
    if not ok and len(recorded) == len(BARCODE_WIDTHS):
        diff = [(i, a, b) for i, (a, b) in
                enumerate(zip(BARCODE_WIDTHS, recorded)) if a != b]
        print(f"[barcode] first differences: {diff[:8]}")
    print(f"[barcode] parameter block FBB9..FBBC = "
          f"{bytes(mem[0xFBB9:0xFBBD]).hex()}")
    ptr = read_word(0xFBB9)
    count = read_word(0xFBBB)
    if BARCODE_PROBE:
        barcode_report_probe(syms)
    decoded = None
    if count and count < 256:
        decoded = bytes(mem[ptr:ptr + count])
        print(f"[barcode] hook returned {count} byte(s) at {ptr:04X}: "
              f"{decoded!r}")
    else:
        print("[barcode] hook returned count 0: scan rejected, capture re-armed")
    record = bytes(mem[BARCODE_RECORD_AT:BARCODE_RECORD_AT + 16])
    print(f"[barcode] delivery record at {BARCODE_RECORD_AT:04X}: {record.hex()}")
    print(f"[barcode] FBC9 event flags = {mem[0xFBC9]:02X}"
          f"  F9AB={mem[0xF9AB]:02X} FBB5={mem[0xFBB5]:02X}")
    if delivered:
        env_status = mem[BARCODE_RECORD_AT]
        env_count = read_word(BARCODE_RECORD_AT + 4)
        env_data = bytes(mem[BARCODE_RECORD_AT + 6:
                             BARCODE_RECORD_AT + 6 + min(env_count, 26)])
        print(f"[barcode] envelope: status={env_status:02X} "
              f"count={env_count} data={env_data!r}")
        decoded = env_data
    if BARCODE_EXPECT is not None:
        want = BARCODE_EXPECT.encode("ascii")
        if decoded == want:
            print(f"[barcode] PASS: decoded {decoded!r} == expected {want!r}")
            return True
        print(f"[barcode] FAIL: decoded {decoded!r} != expected {want!r}")
        return False
    return bool(ok)


def perform_upload():
    """Feed the host file according to the loader's current request word."""
    if UPLOAD_DATA is None:
        return False
    if len(UPLOAD_NAME_BYTES) > 0x80:
        raise RuntimeError("upload name exceeds scratch allocation")
    host_write(UPLOAD_NAME_ADDR, UPLOAD_NAME_BYTES)
    host_write_word(0xECD8, UPLOAD_BANK)
    result = call_rom1(0x0B82, (UPLOAD_NAME_ADDR,))
    if result != 0 or read_word(0xECC9) != 2:
        raise RuntimeError(
            f"LoadByName failed: HL={result:04X} state={read_word(0xECC9):04X}"
        )
    offset = 0
    calls = 0
    staged = bytes(mem[UPLOAD_BUFFER_ADDR:UPLOAD_BUFFER_ADDR + UPLOAD_BUFFER_MAX])
    while offset < len(UPLOAD_DATA):
        requested = read_word(0xD36C)
        if requested == 0:
            raise RuntimeError(f"loader requested zero bytes at offset {offset}")
        count = min(requested, len(UPLOAD_DATA) - offset, UPLOAD_BUFFER_MAX)
        host_write(UPLOAD_BUFFER_ADDR, UPLOAD_DATA[offset : offset + count])
        accepted = call_rom1(0x0BAC, (0, UPLOAD_BUFFER_ADDR, count))
        if accepted == 0xFFFF or accepted > count:
            raise RuntimeError(
                f"chunk rejected at {offset}: HL={accepted:04X} count={count}"
            )
        if accepted == 0:
            raise RuntimeError(f"loader accepted zero bytes at offset {offset}")
        offset += accepted
        calls += 1
        print(
            f"[upload] chunk {calls}: accepted {accepted}/{count}, "
            f"offset {offset}/{len(UPLOAD_DATA)}, next request {read_word(0xD36C)}"
        )
    result = call_rom1(0x1002, (0,))
    state = read_word(0xECC9)
    if result != 0 or state != 3:
        raise RuntimeError(f"finalize failed: HL={result:04X} state={state:04X}")
    # Leave the receive object as the boot left it -- see UPLOAD_BUFFER_MAX.
    host_write(UPLOAD_BUFFER_ADDR, staged)
    if validation.kind == "COM":
        loaded = bank_bytes(UPLOAD_BANK, 0x0100, len(UPLOAD_DATA))
        if loaded != UPLOAD_DATA:
            mismatch = next(
                index
                for index, (actual, expected) in enumerate(zip(loaded, UPLOAD_DATA))
                if actual != expected
            )
            raise RuntimeError(
                f"loaded COM differs at {0x0100 + mismatch:04X}: "
                f"got {loaded[mismatch]:02X}, expected {UPLOAD_DATA[mismatch]:02X}"
            )
    entry_addr = read_word(0xECE6)
    print(
        f"[upload] finalized {len(UPLOAD_DATA)} bytes in {calls} chunk(s); "
        f"entry={entry_addr:04X} state={state}"
    )
    if UPLOAD_NO_RUN:
        return True
    return run_loaded_program(
        UPLOAD_NAME_ADDR, entry_addr, "upload", UPLOAD_MARKER, UPLOAD_BANK
    )


def read_program_name(addr):
    raw = bytes(mem[addr : addr + 13])
    try:
        return raw[: raw.index(0)]
    except ValueError as exc:
        raise RuntimeError(f"unterminated program name at {addr:04X}") from exc

# The firmware's keyboard wait loops here until an IRQ has set the event bit.
KBD_WAIT_START = 0x16C9
KBD_WAIT_END = 0x16D2
KBD_EVENT_FLAGS = 0xFBC9
KBD_EVENT_PENDING = 0x04
KBD_RING_WRITE_PTR = 0xFBF0
KBD_RING_START = 0xFBE8

ramt = False
contig = False
banner = False
W = {
    0x2084: "RtcInit",
    0x2828: "ClockSelftest",
    0x02D8: "BannerKeyRead",
    0x3277: "LinkBlockTx",
    0x2EAB: "LinkOpen",
}
hits = {k: 0 for k in W}
last_pc = None
stall = 0
upload_status = "pending" if UPLOAD_PATH else "disabled"
builder_trace_status = "pending" if TRACE_SESSION_BUILDER else "disabled"
transaction_trace_status = (
    "pending" if TRACE_SESSION_TRANSACTION else "disabled"
)
loadrun_source_trace_status = "pending" if TRACE_LOADRUN_SOURCE else "disabled"
loadrun_source_link_phase = 0
loadrun_source_initial_tx_count = 0
loadrun_source_breakpoint = None
loadrun_source_transaction = 0
loadrun_source_next_request_offset = 0
loadrun_source_second_tx_count = 0
loadrun_source_finalizer_seen = False
loadrun_source_state44_complete = False
loadrun_source_data_offset = 0
loadrun_source_phase14_start = None

# expect / queue state
from collections import deque

legacy_queue = []
legacy_qidx = 0
if use_legacy_queue:
    legacy_queue = [0x0D] + [ord(c) for c in SERIAL_TEXT] + [0x0D]
    print(
        f"[init] legacy DRIVE_SERIAL queue {len(legacy_queue)} chars: banner ENTER + '{SERIAL_TEXT}' + ENTER"
    )

pending_keys = deque()
expect_idx = 0
expect_timeout = int(
    get_arg("--expect-timeout", "0", cast=lambda x: int(x, 0))
    if has_flag("--expect-timeout")
    else "0"
)
# 0 = no timeout; if set, it's slices to wait per step before warning+skip
expect_step_enter_slice = 0  # slice index when current step started waiting

# LCD state
prev_fb = None
if LCD_ENABLED:
    # clear screen once
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()
    # initial render
    _, fb0 = get_lcd_text()
    prev_fb = bytes(fb0)
    render_lcd(prev_fb, 0, cb)

i = 0
for _watch in WATCH_PC:
    mach.set_breakpoint(_watch)
if WATCH_PC:
    print(f"[watch-pc] armed {[f'{a:04X}' for a in WATCH_PC]}")
if WATCH_MEM_RANGES:
    print("[watch-mem] armed " + " ".join(
        f"{lo:04X}-{hi:04X}" for lo, hi in WATCH_MEM_RANGES)
        + f" (print cap {WATCH_MEM_REPORT_LIMIT}/range)")
if FILL_MEM_RANGES:
    print("[fill-mem] queued " + " ".join(
        f"{lo:04X}-{hi:04X}" for lo, hi in FILL_MEM_RANGES)
        + " (seeded when the RAM test is skipped)")

while i < MAX_SLICES and stall < 8000:
    if (i & 0xFFF) == 0:
        gc.collect()
    mach.ticks_to_stop = SLICE_TICKS
    try:
        mach.run()
    except Exception as e:
        print("run err", type(e).__name__, e)
        break
    pc = mach.pc & 0xFFFF
    if pc in watch_hits:
        watch_hits[pc] += 1
        if watch_hits[pc] <= WATCH_REPORT_LIMIT:
            print(
                f"[watch-pc] {pc:04X} hit#{watch_hits[pc]} bank={cb:02X} "
                f"AF={mach.af:04X} BC={mach.bc:04X} DE={mach.de:04X} "
                f"HL={mach.hl:04X} SP={mach.sp:04X} "
                f"F794={mem[0xF794]:02X}"
            )
    if TRACE_LOADRUN_SOURCE and loadrun_source_breakpoint == pc:
        print(
            f"[loadrun-source] breakpoint {pc:04X} "
            f"FDD5={mem[0xFDD5]:02X} FDDC={read_word(0xFDDC):04X} "
            f"AF={mach.af:04X} DE={mach.de:04X} HL={mach.hl:04X} "
            f"E5BA={bytes(mem[0xE5BA:0xE5C4]).hex()} "
            f"FE32={bytes(mem[0xFE32:0xFE3A]).hex()} "
            f"FE3A={bytes(mem[0xFE3A:0xFE43]).hex()}"
        )
        mach.clear_breakpoint(pc)
        if pc == 0x1002:
            loadrun_source_finalizer_seen = True
        loadrun_source_breakpoint = {
            0x31BE: 0x2FC4,
            0x2FC4: 0x3002,
            0x3002: 0x3084,
            0x3084: 0x2E85,
            0x5A81: 0x5B57,
            0x5A04: 0x5A2D,
            0x5A2D: 0x5A3B,
            0x5A3B: 0x5A57,
            0x5A57: 0x5B18,
            0x5B18: 0x5B57,
            0x5B57: 0x4D0E,
            0x4D0E: 0x620B,
            0x624B: 0x58D9,
            0x58D9: 0x2F78,
            0x3D71: 0x3DF5,
            0x3DF5: 0x3EAD,
            0x3EAD: 0x4FBC,
            0x4FBC: 0x5019,
            0x5019: 0x4FE5,
            0x4FE5: 0x5030,
        }.get(pc)
        if pc == 0x2E85 and loadrun_source_transaction == 0:
            loadrun_source_transaction = 1
            loadrun_source_link_phase = 3
        elif pc == 0x2E85 and loadrun_source_link_phase == 7:
            loadrun_source_breakpoint = 0x48BE
            mach.set_breakpoint(loadrun_source_breakpoint)
        elif pc == 0x2E85 and loadrun_source_link_phase == 9:
            loadrun_source_breakpoint = 0x5A81
            mach.set_breakpoint(loadrun_source_breakpoint)
        elif pc == 0x2E85 and loadrun_source_link_phase == 11:
            loadrun_source_breakpoint = 0x5A04
            mach.set_breakpoint(loadrun_source_breakpoint)
        elif pc == 0x2E85 and loadrun_source_link_phase == 13:
            loadrun_source_breakpoint = 0x5A81
            mach.set_breakpoint(loadrun_source_breakpoint)
        elif pc == 0x2E85 and loadrun_source_link_phase == 15:
            loadrun_source_breakpoint = 0x5A81
            mach.set_breakpoint(loadrun_source_breakpoint)
        elif pc == 0x5B57 and loadrun_source_link_phase == 13:
            if mach.hl == 8:
                loadrun_source_state44_complete = True
            loadrun_source_breakpoint = 0x624B
            mach.set_breakpoint(loadrun_source_breakpoint)
        elif pc == 0x5B57 and loadrun_source_link_phase == 15:
            loadrun_source_breakpoint = 0x624B
            mach.set_breakpoint(loadrun_source_breakpoint)
        elif pc == 0x624B and loadrun_source_link_phase == 13:
            pass
        elif pc == 0x2F78 and loadrun_source_link_phase == 15:
            loadrun_source_link_phase = 13
        if loadrun_source_breakpoint is not None:
            mach.set_breakpoint(loadrun_source_breakpoint)

    # ticks_to_stop is the unconsumed part of the requested execution budget.
    # Use the measured count so a future breakpoint/watchpoint cannot make the
    # RTC run faster than the emulated CPU.
    elapsed_ticks = SLICE_TICKS - mach.ticks_to_stop
    advance_rtc(elapsed_ticks)

    # ---------- LCD poll & render ----------
    if LCD_ENABLED:
        txt_now, fb_now = get_lcd_text()
        fb_bytes = bytes(fb_now)
        changed = prev_fb is None or fb_bytes != prev_fb
        heartbeat = LCD_RATE is not None and (i % LCD_RATE == 0)
        if changed or heartbeat:
            if changed:
                render_lcd(fb_bytes, i, cb)
                prev_fb = fb_bytes
            elif heartbeat:
                # still update header even if no change to show progress; but don't spam full redraw?
                # For heartbeat, also render to show slice count moving
                render_lcd(fb_bytes, i, cb)

    # ---------- paced injection ----------
    # unified injection: if pending_keys non-empty, inject one per qualifying HALT loop
    # legacy queue also uses pending_keys mechanism; we unify
    # first, manage expect step progression (only when pending empty)
    if (
        len(EXPECT_STEPS) > 0
        and expect_idx < len(EXPECT_STEPS)
        and len(pending_keys) == 0
    ):
        step = EXPECT_STEPS[expect_idx]
        txt_now, _ = get_lcd_text()
        # also consider fb as flat text without newlines; check substrs present
        matched = all(s in txt_now for s in step["need"]) if step["need"] else True
        if matched:
            if step["keys"]:
                pending_keys.extend(step["keys"])
                print(
                    f"[{i}] expect step {expect_idx} matched {step['need']!r} -> queue {step['keys']!r} (pc={pc:04X})"
                )
            else:
                print(
                    f"[{i}] expect step {expect_idx} matched {step['need']!r} (no keys, wait-only)"
                )
            # snapshot on expect match if requested
            if SNAPSHOT_RANGES:
                print(f"[{i}] --- snapshot on expect match {expect_idx} ---")
                for a, l in SNAPSHOT_RANGES:
                    hexdump_mem(f"expect{expect_idx}", a, l)
            expect_idx += 1
            expect_step_enter_slice = i
        else:
            # timeout?
            if expect_timeout and (i - expect_step_enter_slice) > expect_timeout:
                print(
                    f"[{i}] expect step {expect_idx} timeout waiting for {step['need']!r}, txt={txt_now[:60]!r}... (timeout {expect_timeout} slices)",
                    file=sys.stderr,
                )
                expect_idx += 1
                expect_step_enter_slice = i
                print(f"[{i}] expect step skip to {expect_idx}", file=sys.stderr)

    # determine which queue to inject from
    at_keyboard_wait = (
        KBD_WAIT_START <= pc <= KBD_WAIT_END
        and mem[0xFFA8] == 1
        and not mem[KBD_EVENT_FLAGS] & KBD_EVENT_PENDING
    )
    if len(pending_keys) > 0:
        # Use pending_keys from expect
        if at_keyboard_wait:
            rp = mem[KBD_RING_WRITE_PTR] | (mem[KBD_RING_WRITE_PTR + 1] << 8)
            if rp == 0:
                rp = KBD_RING_START
            ch = pending_keys.popleft()
            mem[rp] = ch & 0xFF
            mem[KBD_EVENT_FLAGS] |= KBD_EVENT_PENDING
            print(
                f"[{i}] inject expect char {chr(ch)!r} ({ch:02X}) pc={pc:04X} rp={rp:04X} remaining={len(pending_keys)}"
            )
            # also show LCD after inject?
    elif use_legacy_queue and legacy_qidx < len(legacy_queue) and at_keyboard_wait:
        rp = mem[KBD_RING_WRITE_PTR] | (mem[KBD_RING_WRITE_PTR + 1] << 8)
        if rp == 0:
            rp = KBD_RING_START
        ch = legacy_queue[legacy_qidx]
        mem[rp] = ch & 0xFF
        mem[KBD_EVENT_FLAGS] |= KBD_EVENT_PENDING
        print(
            f"[{i}] inject legacy qidx={legacy_qidx} char={chr(ch)!r} pc={pc:04X} rp={rp:04X}"
        )
        legacy_qidx += 1

    # boot skips
    if not ramt and 0x2530 <= pc <= 0x2670:
        for k in range(0x40):
            mem[0xFEB0 + k] = 0x0F
        mem[0xFDB1] = 0
        mem[0xFEAF] = 0xFF
        mem[0xFDB0] = 0
        mach.pc = 0x01D0
        ramt = True
        print(f"[{i}] skip RAM test")
        # --fill-mem seeds here: this is where ram_page_test_4banks (2530)
        # would have finished erasing 8000-FFFF, so it is the earliest point
        # a marker can survive. One fill per run; nothing re-seeds it.
        apply_fill_mem()
        continue
    if not contig and pc == 0x267A:
        for k in range(0x40):
            mem[0xFEB0 + k] = 0x0F
        mem[0xFDB1] = 0
        mach.pc = 0x26E3
        contig = True
        print(f"[{i}] contig tail")
        continue
    if pc == 0x02D8 and not banner:
        if not DRIVE_SERIAL and len(EXPECT_STEPS) == 0:
            mach.a = 0x0D
            mach.pc = 0x02DB
            banner = True
            print(f"[{i}] banner ENTER (legacy)")
            continue
    if 0x289E <= pc <= 0x28C0:
        mach.pc = 0x28C1
        continue
    if pc in W:
        if hits[pc] == 0:
            print(f"[{i}] HIT {W[pc]} PC={pc:04X} bank={cb:02X}")
        hits[pc] += 1
    # check for Main Menu reached
    # For legacy queue, check qidx progress; for expect, check txt contains Main Menu
    fb_txt, _ = get_lcd_text()
    if COMMSTAR_PEER_MODE and session_link_peer is not None:
        # Generic pump: whatever the handheld transmits, the peer answers.
        # No phases and no breakpoints -- the protocol drives itself.
        captured = session_link_peer.peek_tx()
        if len(captured) > shadow_tx_seen:
            shadow_peer.feed_tx(bytes(captured[shadow_tx_seen:]))
            shadow_tx_seen = len(captured)
            for reply in shadow_peer.take_rx():
                session_link_peer.feed_rx(reply)
                shadow_agree += 1
                print(f"[commstar-peer] replied {reply.hex()}")
    if TRACE_LOADRUN_SOURCE and loadrun_source_trace_status == "pending":
        if loadrun_source_link_phase == 0:
            request = session_link_peer.peek_tx()
            if len(request) >= 3:
                request_length = 1 + int.from_bytes(request[1:3], "little")
                if len(request) >= request_length:
                    link_id = mem[0xFDD4]
                    sequence = mem[0xFE43 + (link_id & 0x3F)]
                    phase1 = bytes(
                        [0, 7, 0, 2, sequence, link_id, 0, 0, 2, sequence]
                    )
                    loadrun_source_initial_tx_count = session_link_peer.pending_tx
                    feed_rx_checked(phase1)
                    loadrun_source_link_phase = 1
                    print(
                        f"[loadrun-source] initial TX={request[:request_length].hex()}"
                    )
                    print(f"[loadrun-source] phase1 RX={phase1.hex()}")
        elif loadrun_source_link_phase == 1:
            link_id = mem[0xFDD4]
            sequence = mem[0xFE43 + (link_id & 0x3F)]
            expected_reply = bytes(
                [link_id & 0x1F, 6, 0, 3, sequence, 0x7F, 0]
            )
            if (
                session_link_peer.pending_rx == 0
                and mem[0xFDD5] == 3
                and read_word(0xFDDC) == 0xFE32
                and session_link_peer.peek_tx()[loadrun_source_initial_tx_count:]
                == expected_reply
            ):
                # Type 4 completes the type-2 request; its response carries
                # no payload in this mechanically scoped trace.
                phase2 = bytes([0, 6, 0, 4, sequence, link_id, 0, 4, sequence])
                feed_rx_checked(phase2)
                loadrun_source_link_phase = 2
                loadrun_source_next_request_offset = session_link_peer.pending_tx
                loadrun_source_breakpoint = 0x31BE
                mach.set_breakpoint(loadrun_source_breakpoint)
                print(f"[loadrun-source] phase2 RX={phase2.hex()}")
        elif loadrun_source_link_phase == 3:
            request = session_link_peer.peek_tx()[loadrun_source_next_request_offset:]
            if len(request) >= 3:
                request_length = 1 + int.from_bytes(request[1:3], "little")
                if len(request) >= request_length:
                    link_id = mem[0xFDD4]
                    sequence = mem[0xFE43 + (link_id & 0x3F)]
                    if request[3] != 1:
                        raise RuntimeError(
                            "unexpected second source request type "
                            f"{request[3]:02X}"
                        )
                    phase1 = bytes(
                        [0, 7, 0, 2, sequence, link_id, 0, 0, 2, sequence]
                    )
                    loadrun_source_second_tx_count = session_link_peer.pending_tx
                    feed_rx_checked(phase1)
                    loadrun_source_next_request_offset += request_length
                    loadrun_source_link_phase = 4
                    print(
                        f"[loadrun-source] second TX={request[:request_length].hex()}"
                    )
                    print(f"[loadrun-source] second phase1 RX={phase1.hex()}")
        elif loadrun_source_link_phase == 4:
            link_id = mem[0xFDD4]
            sequence = mem[0xFE43 + (link_id & 0x3F)]
            expected_reply = bytes(
                [link_id & 0x1F, 6, 0, 3, sequence, 0x7F, 0]
            )
            if (
                session_link_peer.pending_rx == 0
                and mem[0xFDD5] == 3
                and read_word(0xFDDC) == 0xFE32
                and session_link_peer.peek_tx()[loadrun_source_second_tx_count:]
                == expected_reply
            ):
                phase2 = bytes([0, 6, 0, 4, sequence, link_id, 0, 4, sequence])
                feed_rx_checked(phase2)
                loadrun_source_link_phase = 5
                loadrun_source_breakpoint = 0x31BE
                mach.set_breakpoint(loadrun_source_breakpoint)
                print(f"[loadrun-source] second phase2 RX={phase2.hex()}")
        elif loadrun_source_link_phase == 5:
            request = session_link_peer.peek_tx()[loadrun_source_next_request_offset:]
            # The prior type-2 result is acknowledged by a controller type-3
            # frame before the next type-1 request is emitted.
            if len(request) >= 7 and request[0] == 3 and request[3] == 3:
                loadrun_source_next_request_offset += 7
                request = request[7:]
            if len(request) >= 3:
                request_length = 1 + int.from_bytes(request[1:3], "little")
                if len(request) >= request_length:
                    link_id = mem[0xFDD4]
                    sequence = mem[0xFE43 + (link_id & 0x3F)]
                    if request[3] != 1:
                        raise RuntimeError(
                            "unexpected third source request type "
                            f"{request[3]:02X}"
                        )
                    phase1 = bytes(
                        [0, 7, 0, 2, sequence, link_id, 0, 0, 2, sequence]
                    )
                    loadrun_source_second_tx_count = session_link_peer.pending_tx
                    feed_rx_checked(phase1)
                    loadrun_source_next_request_offset += request_length
                    loadrun_source_link_phase = 6
                    loadrun_source_breakpoint = 0x5DFD
                    mach.set_breakpoint(loadrun_source_breakpoint)
                    request_name = "state61" if request[7] == 0x61 else "third"
                    print(
                        f"[loadrun-source] {request_name} TX="
                        f"{request[:request_length].hex()}"
                    )
                    print(f"[loadrun-source] {request_name} phase1 RX={phase1.hex()}")
        elif loadrun_source_link_phase == 6:
            link_id = mem[0xFDD4]
            sequence = mem[0xFE43 + (link_id & 0x3F)]
            expected_reply = bytes(
                [link_id & 0x1F, 6, 0, 3, sequence, 0x7F, 0]
            )
            if (
                session_link_peer.pending_rx == 0
                and mem[0xFDD5] == 3
                and read_word(0xFDDC) == 0xFE32
                and session_link_peer.peek_tx()[loadrun_source_second_tx_count:]
                == expected_reply
            ):
                phase2 = bytes([0, 6, 0, 4, sequence, link_id, 0, 4, sequence])
                feed_rx_checked(phase2)
                loadrun_source_link_phase = 7
                loadrun_source_breakpoint = 0x31BE
                mach.set_breakpoint(loadrun_source_breakpoint)
                print(f"[loadrun-source] third phase2 RX={phase2.hex()}")
        elif loadrun_source_link_phase == 7:
            request = session_link_peer.peek_tx()[loadrun_source_next_request_offset:]
            if len(request) >= 7 and request[0] == 3 and request[3] == 3:
                loadrun_source_next_request_offset += 7
                request = request[7:]
            if len(request) >= 3:
                request_length = 1 + int.from_bytes(request[1:3], "little")
                if len(request) >= request_length:
                    link_id = mem[0xFDD4]
                    sequence = mem[0xFE43 + (link_id & 0x3F)]
                    if request[3] != 1 or request[7] != 0x64:
                        raise RuntimeError(
                            "unexpected state-64 source request "
                            f"{request[:request_length].hex()}"
                        )
                    phase1 = bytes(
                        [0, 7, 0, 2, sequence, link_id, 0, 0, 2, sequence]
                    )
                    loadrun_source_second_tx_count = session_link_peer.pending_tx
                    feed_rx_checked(phase1)
                    loadrun_source_next_request_offset += request_length
                    loadrun_source_link_phase = 8
                    print(
                        f"[loadrun-source] state64 TX={request[:request_length].hex()}"
                    )
                    print(f"[loadrun-source] state64 phase1 RX={phase1.hex()}")
        elif loadrun_source_link_phase == 8:
            link_id = mem[0xFDD4]
            sequence = mem[0xFE43 + (link_id & 0x3F)]
            expected_reply = bytes(
                [link_id & 0x1F, 6, 0, 3, sequence, 0x7F, 0]
            )
            if (
                session_link_peer.pending_rx == 0
                and mem[0xFDD5] == 3
                and read_word(0xFDDC) == 0xFE32
                and session_link_peer.peek_tx()[loadrun_source_second_tx_count:]
                == expected_reply
            ):
                phase2 = bytes([0, 6, 0, 4, sequence, link_id, 0, 4, sequence])
                feed_rx_checked(phase2)
                loadrun_source_link_phase = 9
                loadrun_source_breakpoint = 0x31BE
                mach.set_breakpoint(loadrun_source_breakpoint)
                print(f"[loadrun-source] state64 phase2 RX={phase2.hex()}")
        elif loadrun_source_link_phase == 9:
            request = session_link_peer.peek_tx()[loadrun_source_next_request_offset:]
            if len(request) >= 7 and request[0] == 3 and request[3] == 3:
                loadrun_source_next_request_offset += 7
                request = request[7:]
            if len(request) >= 3:
                request_length = 1 + int.from_bytes(request[1:3], "little")
                if len(request) >= request_length:
                    link_id = mem[0xFDD4]
                    sequence = mem[0xFE43 + (link_id & 0x3F)]
                    if request[3] != 1 or request[7] != 0x45:
                        raise RuntimeError(
                            "unexpected state-45 source request "
                            f"{request[:request_length].hex()}"
                        )
                    phase1 = bytes(
                        [0, 7, 0, 2, sequence, link_id, 0, 0, 2, sequence]
                    )
                    loadrun_source_second_tx_count = session_link_peer.pending_tx
                    feed_rx_checked(phase1)
                    loadrun_source_next_request_offset += request_length
                    loadrun_source_link_phase = 10
                    print(
                        f"[loadrun-source] state45 TX={request[:request_length].hex()}"
                    )
                    print(f"[loadrun-source] state45 phase1 RX={phase1.hex()}")
        elif loadrun_source_link_phase == 10:
            link_id = mem[0xFDD4]
            sequence = mem[0xFE43 + (link_id & 0x3F)]
            expected_reply = bytes(
                [link_id & 0x1F, 6, 0, 3, sequence, 0x7F, 0]
            )
            if (
                session_link_peer.pending_rx == 0
                and mem[0xFDD5] == 3
                and read_word(0xFDDC) == 0xFE32
                and session_link_peer.peek_tx()[loadrun_source_second_tx_count:]
                == expected_reply
            ):
                phase2 = bytes([0, 6, 0, 4, sequence, link_id, 0, 4, sequence])
                feed_rx_checked(phase2)
                loadrun_source_link_phase = 11
                loadrun_source_breakpoint = 0x31BE
                mach.set_breakpoint(loadrun_source_breakpoint)
                print(f"[loadrun-source] state45 phase2 RX={phase2.hex()}")
        elif loadrun_source_link_phase == 11:
            request = session_link_peer.peek_tx()[loadrun_source_next_request_offset:]
            if len(request) >= 7 and request[0] == 3 and request[3] == 3:
                loadrun_source_next_request_offset += 7
                request = request[7:]
            if len(request) >= 3:
                request_length = 1 + int.from_bytes(request[1:3], "little")
                if len(request) >= request_length:
                    link_id = mem[0xFDD4]
                    sequence = mem[0xFE43 + (link_id & 0x3F)]
                    if request[3] != 1 or request[7] != 0x44:
                        raise RuntimeError(
                            "unexpected state-44 source request "
                            f"{request[:request_length].hex()}"
                        )
                    # Phase 1 has the variable-length receive descriptor.
                    # The state-44 classifier reads this completed envelope
                    # after the fixed-size type-4 completion.
                    phase1 = bytes(
                        [
                            0, 20, 0, 2, sequence, link_id, 0,
                            0, 0, 1, 0, 6, 0,
                            0x4F, 0x4B, 0xA5, 0x5A, 0x3C, 0xC3,
                            0, 0,
                            2, sequence,
                        ]
                    )
                    loadrun_source_second_tx_count = session_link_peer.pending_tx
                    feed_rx_checked(phase1)
                    loadrun_source_link_phase = 12
                    print(
                        f"[loadrun-source] state44 TX={request[:request_length].hex()}"
                    )
                    print(f"[loadrun-source] state44 phase1 RX={phase1.hex()}")
        elif loadrun_source_link_phase == 12:
            link_id = mem[0xFDD4]
            sequence = mem[0xFE43 + (link_id & 0x3F)]
            expected_reply = bytes(
                [link_id & 0x1F, 6, 0, 3, sequence, 0x7F, 0]
            )
            if (
                session_link_peer.pending_rx == 0
                and mem[0xFDD5] == 3
                and read_word(0xFDDC) == 0xFE32
                and session_link_peer.peek_tx()[loadrun_source_second_tx_count:]
                == expected_reply
            ):
                phase2 = bytes([0, 6, 0, 4, sequence, link_id, 0, 4, sequence])
                feed_rx_checked(phase2)
                loadrun_source_link_phase = 13
                loadrun_source_breakpoint = 0x31BE
                mach.set_breakpoint(loadrun_source_breakpoint)
                print(f"[loadrun-source] state44 phase2 RX={phase2.hex()}")
        elif loadrun_source_link_phase == 13:
            if (
                loadrun_source_state44_complete
                and pc == 0x2F78
                and session_link_peer.pending_rx == 0
                and read_word(0xFDC5) == 0xE530
                and read_word(0xFDC7) == 0xE5BA
                and read_word(0xFDD2) == 0x2E85
                and read_word(0xFDDC) == 0xFE0E
                and mem[0xFDD5] == 1
            ):
                link_id = mem[0xFDD4]
                sequence = mem[0xFE43 + (link_id & 0x3F)]
                payload = bytes.fromhex("4f4ba55a3cc3")
                payload_marker = 1
                if SYNTHETIC_LOADRUN_DATA is not None:
                    # 0x7e is the largest tested chunk. ROM00:6230 passes
                    # 0x86 for state 44, but its exact payload overhead is open.
                    payload = SYNTHETIC_LOADRUN_DATA[
                        loadrun_source_data_offset : loadrun_source_data_offset + 0x7E
                    ]
                    if not payload:
                        if SYNTHETIC_LOADRUN_FINALIZE:
                            result = call_rom1(0x1002, (0,))
                            if result != 0 or read_word(0xECC9) != 3:
                                raise RuntimeError(
                                    "synthetic finalizer failed: "
                                    f"HL={result:04X} state={read_word(0xECC9)}"
                                )
                            print("[synthetic-loadrun] adapter finalizer reached loader state 3")
                            if SYNTHETIC_RUN_AFTER_LOAD:
                                requested_name = read_program_name(0xEC71)
                                loaded_name = read_program_name(0xECCB)
                                if requested_name != loaded_name:
                                    raise RuntimeError(
                                        "synthetic requested/load name mismatch: "
                                        f"{requested_name!r} != {loaded_name!r}"
                                    )
                                run_loaded_program(
                                    0xEC71,
                                    read_word(0xECE6),
                                    "synthetic-loadrun",
                                )
                            loadrun_source_trace_status = "succeeded"
                            break
                        print(
                            "[synthetic-loadrun] stream exhausted; EOF envelope "
                            "remains an explicit compatibility assumption"
                        )
                        loadrun_source_trace_status = "streamed"
                        break
                    payload_marker = int(
                        loadrun_source_data_offset + len(payload)
                        == len(SYNTHETIC_LOADRUN_DATA)
                    )
                peer_initiated = bytes(
                    [
                        0, 14 + len(payload), 0, 2, sequence, link_id, 0,
                        0, 0, payload_marker, 0, len(payload), 0,
                    ]
                ) + payload + bytes([0, 0, 2, sequence])
                loadrun_source_data_offset += len(payload)
                loadrun_source_second_tx_count = session_link_peer.pending_tx
                feed_rx_checked(peer_initiated)
                loadrun_source_link_phase = 14
                loadrun_source_phase14_start = i
                print(
                    f"[loadrun-source] receive-first RX={peer_initiated.hex()} "
                    f"payload={len(payload)} marker={payload_marker} "
                    f"offset={loadrun_source_data_offset}"
                )
        elif loadrun_source_link_phase == 14:
            link_id = mem[0xFDD4]
            sequence = mem[0xFE43 + (link_id & 0x3F)]
            expected_reply = bytes(
                [link_id & 0x1F, 6, 0, 3, sequence, 0x7F, 0]
            )
            reply_tail = session_link_peer.peek_tx()[loadrun_source_second_tx_count:]
            if (
                session_link_peer.pending_rx == 0
                and mem[0xFDD5] == 3
                and read_word(0xFDDC) == 0xFE32
                and reply_tail.endswith(expected_reply)
            ):
                completion = bytes([0, 6, 0, 4, sequence, link_id, 0, 4, sequence])
                feed_rx_checked(completion)
                loadrun_source_link_phase = 15
                loadrun_source_breakpoint = 0x31BE
                mach.set_breakpoint(loadrun_source_breakpoint)
                print(f"[loadrun-source] receive-first completion={completion.hex()}")
            elif (
                TRACE_LOADRUN_DEBUG
                and loadrun_source_phase14_start is not None
                and i - loadrun_source_phase14_start >= 3000
            ):
                loadrun_source_trace_status = "failed"
                print(
                    "[loadrun-source] state44 reply timeout "
                    f"FDD5={mem[0xFDD5]:02X} FDDC={read_word(0xFDDC):04X} "
                    f"pending_rx={session_link_peer.pending_rx} "
                    f"expected={expected_reply.hex()} tail={reply_tail.hex()}",
                    file=sys.stderr,
                )
                break
    if (
        TRACE_LOADRUN_SOURCE
        and loadrun_source_trace_status == "pending"
        and expect_idx >= len(EXPECT_STEPS)
        and not pending_keys
        and "*** ERROR ***" in fb_txt
        and loadrun_source_finalizer_seen
    ):
        source_table = read_word(0xD2CB)
        wire = session_link_peer.drain_tx()
        expected_table = 0xD121 if TRACE_LOADRUN_SOURCE == "plinth" else 0xD12F
        if source_table != expected_table:
            loadrun_source_trace_status = "failed"
            print(
                f"[loadrun-source] wrong table {source_table:04X}, "
                f"expected {expected_table:04X}",
                file=sys.stderr,
            )
        elif not wire:
            loadrun_source_trace_status = "failed"
            print("[loadrun-source] no session TX captured", file=sys.stderr)
        else:
            loadrun_source_trace_status = "captured"
            first_frame = wire[:13]
            repeats = len(wire) // len(first_frame)
            repeated = (
                repeats > 1
                and len(wire) % len(first_frame) == 0
                and wire == first_frame * repeats
            )
            wire_text = (
                f"{first_frame.hex()} x{repeats}" if repeated else wire.hex()
            )
            print(
                f"[loadrun-source] {TRACE_LOADRUN_SOURCE} "
                f"EC7E={mem[0xEC7E]:02X} table={source_table:04X} "
                f"phase={loadrun_source_link_phase} TX={wire_text}"
            )
        break
    if (
        TRACE_SESSION_TRANSACTION
        and transaction_trace_status == "pending"
        and "Main Menu" in fb_txt
        and not pending_keys
        and (not EXPECT_STEPS or expect_idx >= len(EXPECT_STEPS))
    ):
        print(f"[{i}] Main Menu reached; tracing session transaction")
        try:
            transaction_trace_status = (
                "succeeded"
                if trace_session_transaction(TRACE_SESSION_TRANSACTION)
                else "failed"
            )
        except Exception as exc:
            transaction_trace_status = "failed"
            print(f"[session-transaction] FAILED: {exc}", file=sys.stderr)
        break
    if (
        TRACE_SESSION_BUILDER
        and builder_trace_status == "pending"
        and "Main Menu" in fb_txt
        and not pending_keys
        and (not EXPECT_STEPS or expect_idx >= len(EXPECT_STEPS))
    ):
        print(f"[{i}] Main Menu reached; tracing session builder")
        try:
            builder_trace_status = (
                "succeeded"
                if trace_session_builder(TRACE_SESSION_BUILDER)
                else "failed"
            )
        except Exception as exc:
            builder_trace_status = "failed"
            print(f"[session-builder] FAILED: {exc}", file=sys.stderr)
        break
    if (
        BARCODE_ENABLED
        and barcode_status == "pending"
        and "Main Menu" in fb_txt
        and not pending_keys
        and (not EXPECT_STEPS or expect_idx >= len(EXPECT_STEPS))
    ):
        print(f"[{i}] Main Menu reached; driving barcode capture")
        try:
            driver = (perform_barcode_bdos if BARCODE_BDOS
                      else perform_barcode_capture)
            barcode_status = "succeeded" if driver() else "failed"
        except Exception as exc:
            barcode_status = "failed"
            print(f"[barcode] FAILED: {exc}", file=sys.stderr)
        break
    if UPLOAD_PATH and upload_status == "pending" and "Main Menu" in fb_txt:
        if not pending_keys and (not EXPECT_STEPS or expect_idx >= len(EXPECT_STEPS)):
            print(f"[{i}] Main Menu reached; starting host upload")
            try:
                upload_status = "succeeded" if perform_upload() else "failed"
            except Exception as exc:
                upload_status = "failed"
                print(f"[upload] FAILED: {exc}", file=sys.stderr)
            break
    if use_legacy_queue:
        if legacy_qidx >= len(legacy_queue) and legacy_qidx > 0:
            if "Main Menu" in fb_txt and i > 170000:
                print(
                    f"[{i}] Main Menu reached - boot past serial OK (legacy_qidx={legacy_qidx})"
                )
                break
    else:
        # generic: if any step waited for Main Menu or if fb contains it, report
        if "Main Menu" in fb_txt and i > 150000:
            # if we have expect steps, only break when all steps done
            if len(EXPECT_STEPS) == 0 or expect_idx >= len(EXPECT_STEPS):
                print(
                    f"[{i}] Main Menu reached (expect_idx={expect_idx}/{len(EXPECT_STEPS)})"
                )
                # give a few more slices to render final LCD then break
                if i > 170000 or expect_idx >= len(EXPECT_STEPS):
                    # allow short settle
                    if LCD_ENABLED:
                        _, fb_final = get_lcd_text()
                        render_lcd(bytes(fb_final), i, cb)
                    break
            else:
                # still have pending expect steps that wait for Main Menu; let them proceed
                pass
    if pc == last_pc:
        stall += 1
    else:
        stall = 0
        last_pc = pc
    i += 1

# final framebuffer
fb = mem[FC06 : FC06 + FB_SIZE]
txt = "".join(lcd_byte_to_char(b) for b in fb)
print("\nFramebuffer:")
for r in range(8):
    row = txt[r * 20 : (r + 1) * 20]
    print(f" row{r}: {row!r}")
# also dump raw hex for verification
print("Framebuffer raw hex:", fb[:32].hex(), "...")
print(
    "summary:",
    {v: hits[k] for k, v in W.items()},
    f"legacy_qidx={legacy_qidx}/{len(legacy_queue) if use_legacy_queue else 0} expect_idx={expect_idx}/{len(EXPECT_STEPS)} pending={len(pending_keys)}",
)
if UPLOAD_PATH:
    print(f"upload_status={upload_status}")
if TRACE_SESSION_BUILDER:
    print(f"builder_trace_status={builder_trace_status}")
if BARCODE_ENABLED:
    print(f"barcode_status={barcode_status}")
if TRACE_SESSION_TRANSACTION:
    print(f"transaction_trace_status={transaction_trace_status}")
if WATCH_PC:
    print("[watch-pc] totals: " + "  ".join(
        f"{a:04X}={watch_hits[a]}" for a in WATCH_PC))
if WATCH_MEM_RANGES:
    report_watch_mem()
if FILL_MEM_RANGES:
    if not fill_mem_done:
        print("[fill-mem] WARNING: never seeded (the RAM-test skip was not "
              "reached), so the survival report below means nothing")
    report_fill_mem()
if COMMSTAR_PEER_MODE:
    print(
        f"[commstar-peer] replies={shadow_agree + _peer_state['replies']} "
        f"records-received={len(uploaded_records)}"
    )
    if program_policy is not None:
        served = b"".join(program_policy.served)
        print(
            f"[commstar-peer] program blocks served={len(program_policy.served)} "
            f"bytes={len(served)} finished={program_policy.finished}"
        )
        print(f"[commstar-peer] program served: {served.hex()}")
        for record in program_policy.commands:
            print(
                f"[commstar-peer] command {record.operation!r} "
                f"workstation={record.workstation!r} parameter={record.parameter!r}"
            )
    for state, arg, obj in uploaded_records:
        # arg is the request's second u16 -- LIKELY a last-block marker on
        # state 0045, which a transfer spanning more than one frame settles.
        print(f"[commstar-peer] record from {state:#06x} arg={arg}: {obj.hex()}")
    seq = " ".join(f"{r.state:04x}" for r in shadow_peer.requests)
    print(f"[commstar-peer] request states seen: {seq}")
if TRACE_LOADRUN_SOURCE:
    print(f"loadrun_source_trace_status={loadrun_source_trace_status}")
if TRACE_LOADRUN_SOURCE:
    print(
        f"[shadow-peer] agreed={shadow_agree} differed={len(shadow_differ)} "
        f"unsolicited={shadow_unsolicited}"
    )
    for line in shadow_differ:
        print(f"[shadow-peer] {line}")
# final snapshot dumps (task-requested cells + any --dump-mem ranges)
if SNAPSHOT_RANGES:
    print("\n--- final memory snapshot ---")
    for a, l in SNAPSHOT_RANGES:
        hexdump_mem("final", a, l)
rt = [x for x in log if x[1] in (0x08, 0x28, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F)]
print(
    f"RTC/link transactions: {len(rt)}; RTC rate ={rtc.periodic_hz:.1f} Hz (RS={rtc.rate_select:#x})"
)
with open("/tmp/opencode/micronic_boot_io.txt", "w") as f:
    for seq, (pc, p, v) in enumerate(log):
        f.write(f"{seq:7d} PC={pc:04X} {p:02X} = {v:02X}\n")
print("WROTE /tmp/opencode/micronic_boot_io.txt", len(log), "lines")
if DUMP_BANK is not None:
    # if dumping currently mapped bank, use live window; else from storage
    if DUMP_BANK == cb:
        img = bytes(mem[0:0x8000])
    elif DUMP_BANK == 0:
        img = B0
    elif DUMP_BANK == 1:
        img = B1
    else:
        # Ensure saved window for current bank is flushed if dumping that bank's backing? Already handled cb==DUMP_BANK above.
        # For other RAM bank, ensure we have backing; if not yet created, zero
        img = RAM.get(DUMP_BANK, bytearray(0x8000))
        # If dumping a RAM bank that hasn't been switched away yet but is not current, it's stale but okay.
        # Also flush current if DUMP_BANK == prev? Already covered.
        img = bytes(img)
    path = f"/home/philpem/Micronic-1000/analysis/ram_bank_{DUMP_BANK:02x}.bin"
    with open(path, "wb") as f:
        f.write(bytes(img[:0x8000]) + bytes(max(0, 0x8000 - len(img))))
    print(
        f"DUMPED bank {DUMP_BANK} -> {path} ({len(img)} bytes actual, RAM_KB={RAM_KB}K)"
    )
if UPLOAD_PATH and upload_status != "succeeded":
    sys.exit(1)
if TRACE_SESSION_BUILDER and builder_trace_status != "succeeded":
    sys.exit(1)
if TRACE_SESSION_TRANSACTION and transaction_trace_status != "succeeded":
    sys.exit(1)
if TRACE_LOADRUN_SOURCE and loadrun_source_trace_status not in ("captured", "streamed", "succeeded"):
    sys.exit(1)
