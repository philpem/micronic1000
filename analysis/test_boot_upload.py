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


@unittest.skipUnless(RUN_EMULATOR, "set MICRONIC_RUN_EMULATOR_TESTS=1")
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
