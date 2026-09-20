# Build and run a first COM program

This walkthrough builds a small Z80 program, validates its image, and runs
it through the real ROM loader in the emulator. It uses the supplied ROM
dumps and the repository's small assembler. No physical adapter is needed.
Physical transfer compatibility is a separate
[open wire-protocol problem](../protocol/commstar.md#historical-server-readiness).

## Prerequisites

Run commands from the repository root with Python 3. The assembler and
image validator use only the standard library. The emulator additionally
uses the `z80` package (tested with version `1.0.0`):

```sh
python3 -m venv analysis/venv
analysis/venv/bin/pip install z80==1.0.0
```

If `analysis/venv` already exists with the emulator installed, use it as is.
Keep one emulator process at a time and retain the timeout on a small-memory
machine. The supplied ROMs must be present as `micronic/micron1.bin` and
`micronic/micron2.bin`.

## Source and assembly

The source is `analysis/examples/hello.asm`:

```asm
        org 0100h
        ld de,message
        ld c,09h
        call 0005h
        ld a,0a5h
        ld (0200h),a
        jp 0000h
message:
        db 'Hello World',13,10,'$'
```

The program uses the inherited stack. BDOS `09h` prints the
`$`-terminated string through the active console route. It then writes
`A5h` at its bank-local `0200h` as a harness-visible completion marker and
requests warm restart through page zero. The marker is outside this
30-byte image; do not reuse it blindly in a larger application.

Assemble and validate:

```sh
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "analysis")
from micronic.z80asm import assemble
from micronic.program import validate

image, symbols = assemble(Path("analysis/examples/hello.asm").read_text(), origin=0x100)
result = validate(image)
assert result.kind == "COM" and result.valid, result.errors
assert len(image) == 30
Path("/tmp/hello.com").write_bytes(image)
print("hello.com:", len(image), "bytes; message at", hex(symbols["message"]))
PY
```

Expected: `hello.com: 30 bytes; message at 0x110`. The bytes are:

```text
11 10 01 0E 09 CD 05 00 3E A5 32 00 02 C3 00 00
48 65 6C 6C 6F 20 57 6F 72 6C 64 0D 0A 24
```

## Run through the ROM loader

```sh
timeout 45s analysis/venv/bin/python3 analysis/boot_hw.py \
  --no-lcd --max-slices 100000 \
  --upload /tmp/hello.com --upload-marker 0200:A5
```

The harness boots to the menu, feeds the image through the firmware's
Load/Run callbacks, verifies it, and invokes the program. This direct
callback injection is not a physical IR transfer or a Commstar wire test.

Expected output includes:

```text
[upload] execution entered bank 2 at 0100
[upload] marker 0200=A5 observed
upload_status=succeeded
```

The final LCD text dump contains `Hello World`. **CONFIRMED by a bounded
emulator run on 2026-09-20:** these entry/marker messages and the text were
observed. The marker check establishes execution beyond the print call;
it does not separately test completion of the final warm restart.

## Package as DIP

Use the [producer example](../reference/program-formats.md#building-and-validating-images)
to wrap `/tmp/hello.com` in one type-0 block. The result is a 52-byte DIP:
14-byte header, 8-byte block header, and 30-byte payload. Use the same run
command with `--upload /tmp/hello.dip` to exercise DIP loading; the
walkthrough's recorded execution above is for COM. The format reference
states which constraints the validator does and does not check.

## Troubleshooting

| Symptom | Check |
|---|---|
| `No module named z80` | Use the configured virtual environment and install the emulator dependency there |
| ROM file not found | Run from the repository root and check both dump paths |
| Timeout or no marker | Read the loader error and final LCD dump; do not treat process termination as success |
| Entry reached, no text | Confirm console routing and the string pointer/terminator; the marker alone does not prove visible output |
| Wrong size or message address | Reassemble the checked-in source; a COM has no extra header |

Next, read the [supported profile](supported-profile.md), the
[BDOS contracts](../reference/bdos.md), and the
[memory ownership rules](../reference/memory-map.md#61-where-to-put-it).
