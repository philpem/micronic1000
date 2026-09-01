#!/usr/bin/env python3
"""Opt-in bounded integration tests for the ROM Load/Run path.

Run with:

  MICRONIC_RUN_EMULATOR_TESTS=1 analysis/venv/bin/python3 \
    analysis/test_boot_upload.py
"""

from __future__ import annotations

import os
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from micronic.program import build_dip_file


ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / "analysis" / "venv" / "bin" / "python3"
HARNESS = ROOT / "analysis" / "boot_hw.py"
RUN_EMULATOR = os.environ.get("MICRONIC_RUN_EMULATOR_TESTS") == "1"

HELLO_COM = (
    bytes.fromhex("1110010e09cd05003ea5320002c30d01")
    + b"Hello World$"
)


def capture_tx(stdout: str, label: str) -> str:
    """Return the whole hex capture printed as ``<label> TX=...``.

    Asserting the full value keeps the tail of every capture pinned; the
    frames documented in doc/protocol/commstar.md are transcribed from these.
    """
    prefix = f"{label} TX="
    for line in stdout.splitlines():
        index = line.find(prefix)
        if index != -1:
            return line[index + len(prefix):].strip()
    raise AssertionError(f"no {prefix!r} line in harness output:\n{stdout}")


@unittest.skipUnless(RUN_EMULATOR, "set MICRONIC_RUN_EMULATOR_TESTS=1")
class BootUploadTest(unittest.TestCase):
    def run_upload(self, suffix, data):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / f"hello.{suffix}"
            image.write_bytes(data)
            proc = subprocess.run(
                [
                    str(PYTHON),
                    str(HARNESS),
                    "--no-lcd",
                    "--max-slices",
                    "100000",
                    "--upload",
                    str(image),
                    "--upload-marker",
                    "0200:A5",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("upload_status=succeeded", proc.stdout)
        self.assertIn("execution entered bank 2 at 0100", proc.stdout)
        self.assertIn("marker 0200=A5 observed", proc.stdout)
        self.assertIn("Main MenuHello World", proc.stdout)

    def test_raw_com(self):
        self.run_upload("com", HELLO_COM)

    def test_single_block_dip(self):
        image = build_dip_file(
            header_kwargs={
                "system_id": 0x00E5,
                "entry_bank_offset": 0,
                "image_size": len(HELLO_COM),
                "run_bank_offset": 0,
                "entry_address": 0x0100,
            },
            blocks=[(0, 0, 0x0100, HELLO_COM)],
        )
        self.run_upload("dip", image)

    def test_maximum_size_com(self):
        data = bytes(index & 0xFF for index in range(0xCF81))
        self.assertEqual(len(data), 0xCF81)
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "maximum.com"
            image.write_bytes(data)
            proc = subprocess.run(
                [
                    str(PYTHON),
                    str(HARNESS),
                    "--no-lcd",
                    "--max-slices",
                    "100000",
                    "--upload",
                    str(image),
                    "--upload-no-run",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("finalized 53121 bytes", proc.stdout)
        self.assertIn("upload_status=succeeded", proc.stdout)


# Arms the Commstar session state machine through the application API entry
# point at ram:EE24, with a marker before the call and another after it.
COMMSTAR_API_COM = bytes.fromhex(
    "3eaa"      # 0100 LD A,0AAh
    "320002"    # 0102 LD (0200h),A   ; reached the call
    "cd24ee"    # 0105 CALL 0EE24h    ; arm the state machine
    "3e55"      # 0108 LD A,055h
    "320002"    # 010A LD (0200h),A   ; would mark a normal return
    "c30d01"    # 010D JP $
)


@unittest.skipUnless(RUN_EMULATOR, "set MICRONIC_RUN_EMULATOR_TESTS=1")
class CommstarApplicationApiTest(unittest.TestCase):
    """A loaded application can drive Commstar through the EExx entry points.

    The firmware itself never calls fifteen of the twenty entry points, so
    this is the only demonstrated route to the operations its UI does not
    offer -- including the handheld-to-host direction.
    """

    def _run(self, com: bytes, marker: str):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "t.com"
            image.write_bytes(com)
            proc = subprocess.run(
                [str(PYTHON), str(HARNESS), "--upload", str(image),
                 "--upload-marker", marker,
                 "--dump-mem", "e48d:1", "--dump-mem", "e6fc:1"],
                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=300, check=False,
            )
        self.assertIn("execution entered bank 2 at 0100", proc.stdout)
        return proc.stdout

    @staticmethod
    def _cell(stdout: str, name: str) -> int:
        for line in stdout.splitlines():
            if f"[mem] final {name}:" in line:
                return int(line.split(f"{name}:")[1].split()[1], 16)
        raise AssertionError(f"no final dump of {name}:\n{stdout}")

    def test_control_program_leaves_commstar_untouched(self):
        out = self._run(HELLO_COM, "0200:A5")
        self.assertIn("marker 0200=A5 observed", out)
        self.assertEqual(self._cell(out, "E48D"), 0x00)
        self.assertEqual(self._cell(out, "E6FC"), 0x00)

    def test_application_can_arm_the_state_machine(self):
        # The post-call marker never lands: the entry point transfers control
        # rather than returning, so 0200h keeps the pre-call value.
        out = self._run(COMMSTAR_API_COM, "0200:55")
        self.assertIn("marker 0200=55 not observed", out)
        # Both side effects of ROM00:46E9 are present.
        self.assertEqual(self._cell(out, "E48D"), 0x02)
        self.assertEqual(self._cell(out, "E6FC"), 0x37)


@unittest.skipUnless(RUN_EMULATOR, "set MICRONIC_RUN_EMULATOR_TESTS=1")
class BootSessionTransactionTest(unittest.TestCase):
    def test_form4_transport_transaction(self):
        proc = subprocess.run(
            [
                str(PYTHON),
                str(HARNESS),
                "--no-lcd",
                "--max-slices",
                "100000",
                "--trace-session-transaction",
                "4",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("numeric type-3 TX", proc.stdout)
        self.assertIn("receive object E5BC-E5C2", proc.stdout)
        self.assertIn("zero-payload poll cycle complete", proc.stdout)
        self.assertIn("transaction_trace_status=succeeded", proc.stdout)

    def test_synthetic_loadrun_streams_dip_payload(self):
        image_data = build_dip_file(
            header_kwargs={
                "system_id": 0x00E5,
                "entry_bank_offset": 0,
                "image_size": len(HELLO_COM),
                "run_bank_offset": 0,
                "entry_address": 0x0100,
            },
            blocks=[(0, 0, 0x0100, HELLO_COM)],
        )
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "hello.dip"
            image.write_bytes(image_data)
            proc = subprocess.run(
                [
                    str(PYTHON),
                    str(HARNESS),
                    "--no-lcd",
                    "--trace-loadrun-source",
                    "plinth",
                    "--synthetic-loadrun",
                    str(image),
                    "--synthetic-loadrun-finalize",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("[synthetic-loadrun] prepared", proc.stdout)
        self.assertIn("payload=50 marker=1 offset=50", proc.stdout)
        self.assertIn("adapter finalizer reached loader state 3", proc.stdout)
        self.assertIn("loadrun_source_trace_status=succeeded", proc.stdout)

    def test_v24_mode1_reaches_loader(self):
        image_data = build_dip_file(
            header_kwargs={
                "system_id": 0x00E5,
                "entry_bank_offset": 0,
                "image_size": len(HELLO_COM),
                "run_bank_offset": 0,
                "entry_address": 0x0100,
            },
            blocks=[(0, 0, 0x0100, HELLO_COM)],
        )
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "hello.dip"
            image.write_bytes(image_data)
            proc = subprocess.run(
                [
                    str(PYTHON),
                    str(HARNESS),
                    "--no-lcd",
                    "--trace-loadrun-source",
                    "v24",
                    "--trace-loadrun-v24-mode",
                    "1",
                    "--synthetic-loadrun",
                    str(image),
                    "--synthetic-loadrun-finalize",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        # Compare whole captures, not prefixes: a substring match leaves the
        # tail of a capture unpinned, and the documented frame is transcribed
        # from these values.
        self.assertEqual(
            capture_tx(proc.stdout, "initial"), "030c0001007f00000000000000"
        )
        self.assertEqual(
            capture_tx(proc.stdout, "second"),
            "03150001017f00060000008000004c0000073c000005",
        )
        self.assertEqual(
            capture_tx(proc.stdout, "state61"), "030c0001017f00610000000000"
        )
        self.assertEqual(
            capture_tx(proc.stdout, "state64"), "030c0001017f00640000000000"
        )
        self.assertEqual(
            capture_tx(proc.stdout, "state45"),
            "03420001017f0045000100360000000000000000000000000000004c4f41"
            "443132333435363738000000000000000000000000000000000000000000"
            "00000000000000"
        )
        self.assertEqual(
            capture_tx(proc.stdout, "state44"), "030c0001017f0044000000ff00"
        )
        self.assertIn("adapter finalizer reached loader state 3", proc.stdout)
        self.assertIn("loadrun_source_trace_status=succeeded", proc.stdout)

    def test_state45_field_offsets(self):
        """Pin the state-45 object field offsets by input variation.

        Varying one input at a time must move exactly one field and leave the
        frame length unchanged. This is the measurement behind the object
        layout table in doc/protocol/commstar.md.
        """
        image_data = build_dip_file(
            header_kwargs={
                "system_id": 0x00E5,
                "entry_bank_offset": 0,
                "image_size": len(HELLO_COM),
                "run_bank_offset": 0,
                "entry_address": 0x0100,
            },
            blocks=[(0, 0, 0x0100, HELLO_COM)],
        )

        def capture(serial, name):
            with tempfile.TemporaryDirectory() as tmp:
                image = Path(tmp) / "hello.dip"
                image.write_bytes(image_data)
                proc = subprocess.run(
                    [
                        str(PYTHON), str(HARNESS),
                        "--trace-loadrun-source", "v24",
                        "--trace-loadrun-v24-mode", "1",
                        "--serial", serial,
                        "--trace-loadrun-name", name,
                        "--synthetic-loadrun", str(image),
                        "--synthetic-loadrun-finalize",
                    ],
                    cwd=ROOT, text=True, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, timeout=180, check=False,
                )
            self.assertEqual(proc.returncode, 0, proc.stdout)
            raw = bytes.fromhex(capture_tx(proc.stdout, "state45"))
            return raw[1:]  # drop the controller prelude

        base = capture("12345678", "")
        self.assertEqual(len(base), 66)
        self.assertEqual(base[0] | base[1] << 8, 66)
        self.assertEqual(base[26:30], b"LOAD")
        self.assertEqual(base[30:38], b"12345678")

        # Workstation number: 8 bytes at +30, right-justified space-padded.
        moved = capture("ABC", "")
        self.assertEqual(len(moved), 66)
        self.assertEqual(moved[30:38], b"     ABC")
        self.assertEqual(
            [i for i in range(66) if moved[i] != base[i]], list(range(30, 38))
        )

        # Program name: 8 bytes at +54, left-justified NUL-padded.
        named = capture("12345678", "PROG1234")
        self.assertEqual(len(named), 66)
        self.assertEqual(named[54:62], b"PROG1234")
        self.assertEqual(
            [i for i in range(66) if named[i] != base[i]], list(range(54, 62))
        )

        short = capture("12345678", "XY")
        self.assertEqual(short[54:62], b"XY\x00\x00\x00\x00\x00\x00")

        # LOAD is a runtime constant, not user data.
        for frame in (moved, named, short):
            self.assertEqual(frame[26:30], b"LOAD")

    def test_synthetic_loadrun_streams_multichunk_com(self):
        data = bytes(index & 0xFF for index in range(200))
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "two-chunk.com"
            image.write_bytes(data)
            proc = subprocess.run(
                [
                    str(PYTHON),
                    str(HARNESS),
                    "--trace-loadrun-source",
                    "plinth",
                    "--synthetic-loadrun",
                    str(image),
                    "--synthetic-loadrun-finalize",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("payload=126 marker=0 offset=126", proc.stdout)
        self.assertIn("payload=74 marker=1 offset=200", proc.stdout)
        self.assertIn("adapter finalizer reached loader state 3", proc.stdout)
        self.assertIn("loadrun_source_trace_status=succeeded", proc.stdout)

    def test_synthetic_workflow_serves_relative_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "hello.com"
            image.write_bytes(HELLO_COM)
            manifest = root / "workflow.json"
            manifest.write_text(
                json.dumps(
                    {
                        "source": "plinth",
                        "scan_records": [{"barcode": "0123456789012"}],
                        "image": image.name,
                        "run_after_load": True,
                        "feedback": "list_updated",
                        "safe_to_remove": True,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    str(PYTHON),
                    str(HARNESS),
                    "--synthetic-workflow",
                    str(manifest),
                    "--synthetic-loadrun-finalize",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("[synthetic-workflow] scan_records=1", proc.stdout)
        self.assertIn("payload=28 marker=1 offset=28", proc.stdout)
        self.assertIn("adapter finalizer reached loader state 3", proc.stdout)
        self.assertIn("[synthetic-loadrun] execution entered bank 2 at 0100", proc.stdout)

    def test_v24_mode_counter_edit(self):
        proc = subprocess.run(
            [
                str(PYTHON),
                str(HARNESS),
                "--no-lcd",
                "--max-slices",
                "50000",
                "--expect-timeout",
                "45000",
                "--expect",
                "To Continue Press>>:\r",
                "--expect",
                "Enter the,Workstation:\r12345678\r",
                "--expect",
                "Main Menu:1",
                "--expect",
                "Name,From:\x06\x06\r",
                "--expect",
                r"Log-on information:\xDB",
                "--expect",
                "MODEM_A/ANS:\r",
                "--dump-mem",
                "ec97:2",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("expect step 5 matched ['MODEM_A/ANS']", proc.stdout)
        self.assertIn("[mem] final EC97:02 01 FF", proc.stdout)
        self.assertIn("8000", proc.stdout)
        self.assertIn("Plinth not connected", proc.stdout)


if __name__ == "__main__":
    unittest.main()
