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
  --commstar-peer          Attach the protocol peer to a plain --upload run so
                           a loaded application can hold a Commstar session.
                           Replies come from micronic.peer.CommstarPeer.
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


def wr(a, v):
    a &= 0xFFFF
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


rtc = RTC146818()
rtc_sel = 0x00
from micronic.peer import CommstarPeer

# Shadow responder: the protocol-aware peer runs alongside the phase script
# and is asked what it would have replied at each point. It changes nothing;
# it exists to prove the two agree before the script is retired.
# Records the handheld sends us during an application-driven upload.
uploaded_records = []


def _shadow_policy(request):
    """Mirror the phase script's application policy, so any remaining
    difference is a protocol difference rather than a policy one."""
    if request.obj:
        # The handheld sent us data: this is the handheld-to-host direction.
        uploaded_records.append((request.state, request.obj))
        print(
            f"[commstar-peer] received {len(request.obj)} bytes from state "
            f"{request.state:#06x}: {request.obj[:24].hex()}"
        )
    if request.state == 0x0044:
        return (1, bytes.fromhex("4f4ba55a3cc3"))   # the OK control object
    return None                                      # plain control ack


shadow_peer = CommstarPeer(on_request=_shadow_policy)
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
SLICE_TICKS = 3400
rtc_phase = 0
rtc_phase_rate = None


CALL_SENTINEL = 0xFFFF
# Keep the short logical name above the loader's exclusive D081h program
# ceiling. Input chunks use the confirmed service-33 receive payload object.
UPLOAD_NAME_ADDR = 0xD600
UPLOAD_BUFFER_ADDR = 0xE5C2


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
            captured = session_link_peer.peek_tx()
            if len(captured) > _peer_state["tx_seen"]:
                shadow_peer.feed_tx(bytes(captured[_peer_state["tx_seen"]:]))
                _peer_state["tx_seen"] = len(captured)
                for reply in shadow_peer.take_rx():
                    session_link_peer.feed_rx(reply)
                    _peer_state["replies"] += 1
                    print(f"[commstar-peer] replied {reply.hex()}")
    raise RuntimeError(
        f"marker {marker_addr:04X}={marker_value:02X} not observed"
    )


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
    while offset < len(UPLOAD_DATA):
        requested = read_word(0xD36C)
        if requested == 0:
            raise RuntimeError(f"loader requested zero bytes at offset {offset}")
        count = min(requested, len(UPLOAD_DATA) - offset, 0x100)
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
if TRACE_SESSION_TRANSACTION:
    print(f"transaction_trace_status={transaction_trace_status}")
if WATCH_PC:
    print("[watch-pc] totals: " + "  ".join(
        f"{a:04X}={watch_hits[a]}" for a in WATCH_PC))
if COMMSTAR_PEER_MODE:
    print(
        f"[commstar-peer] replies={shadow_agree + _peer_state['replies']} "
        f"records-received={len(uploaded_records)}"
    )
    for state, obj in uploaded_records:
        print(f"[commstar-peer] record from {state:#06x}: {obj.hex()}")
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
