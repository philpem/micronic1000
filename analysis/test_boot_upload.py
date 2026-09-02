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


def build_record_upload_com(payload: bytes, name: bytes = b"", buf: int = 0xE850,
                            namebuf: int = 0xE870) -> bytes:
    """A COM that drives a Commstar record upload and sends ``payload``.

    C-INIT-COMMS -> C-DIAL -> suppress validation -> C-BEGIN-FILE ->
    C-TX-REC(record) -> C-END-FILE -> C-END-TX.

    Argument slots differ per entry point: C-INIT-COMMS and friends read the
    third word down (caller SP+4), C-TX-REC reads the last word pushed.
    """
    record = bytes([len(payload)]) + payload      # [u8 count][payload]
    namerec = bytes([len(name)]) + name           # same shape for the file name

    def mark(v):
        return bytes([0x3E, v]) + bytes.fromhex("3240e8")

    def call4(slot, arg=0):                        # arg at caller SP+4
        push = bytes.fromhex("210000e5")
        argp = bytes([0x21, arg & 0xFF, arg >> 8, 0xE5])
        return (push + argp + push + push + bytes([0xCD, slot & 0xFF, slot >> 8])
                + bytes.fromhex("eb" "210800" "39" "f9" "eb"))

    def call_last(slot, arg):                      # arg pushed last
        push = bytes.fromhex("210000e5")
        argp = bytes([0x21, arg & 0xFF, arg >> 8, 0xE5])
        return (push + push + push + argp + bytes([0xCD, slot & 0xFF, slot >> 8])
                + bytes.fromhex("eb" "210800" "39" "f9" "eb"))

    com = mark(0xAA)
    ldir = len(com)
    com += (b"\x21\x00\x00" + bytes([0x11, buf & 0xFF, buf >> 8])
            + bytes([0x01, len(record), 0x00]) + bytes.fromhex("edb0"))
    ldir2 = len(com)
    com += (b"\x21\x00\x00" + bytes([0x11, namebuf & 0xFF, namebuf >> 8])
            + bytes([0x01, len(namerec), 0x00]) + bytes.fromhex("edb0"))
    com += call4(0xEE20) + call4(0xEE10)           # C-INIT-COMMS, C-DIAL
    com += bytes.fromhex("3e02" "328de4")          # E48D = 2
    com += call_last(0xEE08, namebuf)              # C-BEGIN-FILE(name)
    com += call_last(0xEE44, buf)                  # C-TX-REC(record)
    com += call4(0xEE18) + call4(0xEE1C)           # C-END-FILE, C-END-TX
    # Final marker in bank 2 as well, so --upload-marker sees the run finish
    # and the harness exits cleanly.
    com += mark(0x55) + bytes.fromhex("3e55") + bytes.fromhex("320002")
    spin = 0x100 + len(com)
    com += bytes([0xC3, spin & 0xFF, spin >> 8])
    src = 0x100 + len(com)
    com += record
    src2 = 0x100 + len(com)
    com += namerec
    com = com[:ldir + 1] + bytes([src & 0xFF, src >> 8]) + com[ldir + 3:]
    return com[:ldir2 + 1] + bytes([src2 & 0xFF, src2 >> 8]) + com[ldir2 + 3:]


@unittest.skipUnless(RUN_EMULATOR, "set MICRONIC_RUN_EMULATOR_TESTS=1")
class CommstarRecordUploadTest(unittest.TestCase):
    """A loaded application uploads a record to the host.

    This is the handheld-to-host direction: the application nominates a
    counted buffer, the firmware transmits it, and the peer receives it.
    """

    def _upload(self, payload: bytes, name: bytes = b"FILE1") -> bytes:
        with tempfile.TemporaryDirectory() as tmp:
            com = Path(tmp) / "rec.com"
            com.write_bytes(build_record_upload_com(payload, name))
            proc = subprocess.run(
                [str(PYTHON), str(HARNESS), "--commstar-peer",
                 "--upload", str(com), "--upload-marker", "0200:55"],
                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=300, check=False,
            )
        # The harness exits non-zero because C-END-TX does not return, so the
        # program never reaches its final marker. The record is flushed during
        # C-END-TX regardless, which is what this test is about; a clean
        # session teardown is still open.
        line = next((l for l in proc.stdout.splitlines()
                     if "record from 0x0045" in l), None)
        self.assertIsNotNone(line, f"no record reached the host:\n{proc.stdout}")
        return bytes.fromhex(line.split(": ")[1])

    def _upload_frames(self, payload: bytes, name: bytes,
                       buf: int = 0xE850, namebuf: int = 0xE830):
        """Every state-0045 frame of one upload, as (arg, bytes).

        ``namebuf`` sits *below* ``buf`` here: a record long enough to span
        more than one frame would otherwise run over the name buffer, which
        is a property of these test addresses and not of the firmware.
        """
        with tempfile.TemporaryDirectory() as tmp:
            com = Path(tmp) / "rec.com"
            com.write_bytes(build_record_upload_com(payload, name, buf=buf,
                                                    namebuf=namebuf))
            proc = subprocess.run(
                [str(PYTHON), str(HARNESS), "--commstar-peer",
                 "--upload", str(com), "--upload-marker", "0200:55"],
                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=600, check=False,
            )
        frames = [(int(l.split("arg=")[1].split(":")[0]),
                   bytes.fromhex(l.split(": ")[1]))
                  for l in proc.stdout.splitlines()
                  if "record from 0x0045" in l]
        self.assertTrue(frames, f"no state-0045 frame reached the host:\n{proc.stdout}")
        return frames

    def test_multi_frame_transfer_marks_only_the_last_frame(self):
        """The state-0045 arg field is a last-block marker.

        A payload longer than the 128-byte wire buffer is segmented, so this
        is the case that tells a last-block marker apart from a constant. The
        static prediction was that the automatic flush (ROM00:6187) passes 0
        and the explicit end-of-transmission flush (ROM00:61F9) passes 1.
        """
        payload = bytes(0x41 + (i % 26) for i in range(200))
        frames = self._upload_frames(payload, b"LONGFILE")
        self.assertGreater(len(frames), 1, "payload did not span two frames")
        args = [a for a, _ in frames]
        self.assertEqual(args, [0] * (len(frames) - 1) + [1], args)
        self.assertEqual(frames[0][1].__len__(), 128, "first frame is not a full buffer")

    def test_multi_frame_stream_reassembles_by_concatenation(self):
        """Frames carry no internal headers: joining them yields the stream."""
        payload = bytes(0x41 + (i % 26) for i in range(200))
        frames = self._upload_frames(payload, b"LONGFILE")
        joined = b"".join(f for _, f in frames)
        expected = bytes([8]) + b"LONGFILE" + b"\x1e" + payload + b"\x1c"
        self.assertEqual(joined, expected)

    def test_upload_stream_format(self):
        """[u8 namelen][name] 1Eh [record] 1Ch"""
        obj = self._upload(b"HELLO-FROM-M1000", name=b"MYFILE")
        n = obj[0]
        self.assertEqual(n, len(b"MYFILE"), obj.hex())
        self.assertEqual(obj[1:1 + n], b"MYFILE", obj.hex())
        self.assertEqual(obj[1 + n], 0x1E, obj.hex())    # C-TX-REC's marker
        self.assertEqual(obj[2 + n:-1], b"HELLO-FROM-M1000", obj.hex())
        self.assertEqual(obj[-1], 0x1C, obj.hex())       # C-END-FILE's marker

    def test_name_and_payload_are_both_carried_verbatim(self):
        obj = self._upload(b"SCAN:0042:WIDGET", name=b"STOCK")
        self.assertEqual(obj[1:6], b"STOCK", obj.hex())
        self.assertEqual(obj[7:-1], b"SCAN:0042:WIDGET", obj.hex())


# ---------------------------------------------------------------------------
# Application-driven Commstar sessions: a tiny assembler and two drivers.
#
# A loaded program's own page (0000-7FFF) is banked out while a firmware entry
# point runs, so every pointer handed to the session has to live in the fixed
# half above 8000h; private scratch can stay in the program's page, where
# nothing else can touch it.
# ---------------------------------------------------------------------------

# Fixed-RAM scratch. The loaded program's own page (0000-7FFF) is banked out
# while a firmware entry point runs, so every pointer handed to the session
# must live in the fixed half above 8000h. The stack is at D681 on entry and
# the transfer-vector table starts at ED1C, so E800-EBFF is clear of both.
NAMEPARM = 0xE800   # 12-byte C-COMMAND parameter: the program name
WSBUF    = 0xE810   # workstation id for C-INIT-COMMS
NULSTR   = 0xE820   # one NUL: the unused identity strings and C-DIAL's number
REPLY    = 0xE830   # C-COMMAND reply buffer, [u8 count][data], 256 bytes
BLKBUF   = 0xE930   # C-RX-BLK destination, [u8 count][<=128 data], 129 bytes
# The LCD's 20x20 text buffer starts at EA53 (read back out of a live run), so
# E800-EA4F is clear of it as well as of the stack and the vector table.

# Private scratch: nothing the firmware ever sees, so it can live in the
# loaded program's own page.
STATUS   = 0x0600
NBLK     = 0x0602
TOTAL    = 0x0604
DSTPTR   = 0x0606
PROGRESS = 0x0608
ACC      = 0x0800   # where the received program accumulates

EE_INIT_COMMS = 0xEE20
EE_DIAL       = 0xEE10
EE_COMMAND    = 0xEE0C
EE_RX_BLK     = 0xEE2C
EE_BEGIN_FILE = 0xEE08
EE_TX_REC     = 0xEE44
EE_END_FILE   = 0xEE18
EE_END_TX     = 0xEE1C

OP_SEND, OP_LOAD, OP_PROG = 2, 3, 4


class Asm:
    """Just enough Z80 to write these drivers with labels instead of offsets."""

    def __init__(self, org=0x0100):
        self.org = org
        self.buf = bytearray()
        self.labels = {}
        self.patches = []       # (offset, label)

    # -------------------------------------------------------------- primitives
    def db(self, *b):
        self.buf.extend(bytes(b) if not isinstance(b[0], (bytes, bytearray)) else b[0])
        return self

    def here(self):
        return self.org + len(self.buf)

    def label(self, name):
        self.labels[name] = self.here()
        return self

    def _word(self, value):
        if isinstance(value, str):
            self.patches.append((len(self.buf), value))
            self.buf.extend(b"\0\0")
        else:
            self.buf.extend(bytes([value & 0xFF, (value >> 8) & 0xFF]))

    def link(self) -> bytes:
        out = bytearray(self.buf)
        for offset, name in self.patches:
            addr = self.labels[name]
            out[offset] = addr & 0xFF
            out[offset + 1] = (addr >> 8) & 0xFF
        return bytes(out)

    # ------------------------------------------------------------ instructions
    def ld_hl(self, v):     self.db(0x21); self._word(v); return self
    def ld_de(self, v):     self.db(0x11); self._word(v); return self
    def ld_bc(self, v):     self.db(0x01); self._word(v); return self
    def ld_a(self, v):      return self.db(0x3E, v & 0xFF)
    def ld_a_mem(self, a):  self.db(0x3A); self._word(a); return self
    def ld_mem_a(self, a):  self.db(0x32); self._word(a); return self
    def ld_hl_mem(self, a): self.db(0x2A); self._word(a); return self
    def ld_mem_hl(self, a): self.db(0x22); self._word(a); return self
    def ld_de_mem(self, a): self.db(0xED, 0x5B); self._word(a); return self
    def ld_mem_de(self, a): self.db(0xED, 0x53); self._word(a); return self
    def push_hl(self):      return self.db(0xE5)
    def ldir(self):         return self.db(0xED, 0xB0)
    def ex_de_hl(self):     return self.db(0xEB)
    def add_hl_de(self):    return self.db(0x19)
    def add_hl_sp(self):    return self.db(0x39)
    def ld_sp_hl(self):     return self.db(0xF9)
    def inc_hl(self):       return self.db(0x23)
    def or_a(self):         return self.db(0xB7)
    def or_l(self):         return self.db(0xB5)
    def ld_a_h(self):       return self.db(0x7C)
    def ld_a_l(self):       return self.db(0x7D)
    def ld_l_a(self):       return self.db(0x6F)
    def ld_h(self, v):      return self.db(0x26, v & 0xFF)
    def ld_c_a(self):       return self.db(0x4F)
    def ld_b(self, v):      return self.db(0x06, v & 0xFF)
    def cp(self, v):        return self.db(0xFE, v & 0xFF)
    def jp(self, t):        self.db(0xC3); self._word(t); return self
    def jp_z(self, t):      self.db(0xCA); self._word(t); return self
    def jp_nz(self, t):     self.db(0xC2); self._word(t); return self
    def jp_nc(self, t):     self.db(0xD2); self._word(t); return self
    def call(self, t):      self.db(0xCD); self._word(t); return self
    def ret(self):          return self.db(0xC9)

    # --------------------------------------------------------------- idioms
    def entry(self, slot, args=()):
        """Call a transfer-vector entry point; ``args[0]`` lands at caller SP+0.

        Arguments go on the stack and the caller removes them; the result
        comes back in HL, so the cleanup parks it in DE and puts it back.
        """
        for value in reversed(args):
            self.ld_hl(value).push_hl()
        self.call(slot)
        self.ex_de_hl().ld_hl(2 * len(args)).add_hl_sp().ld_sp_hl().ex_de_hl()
        return self

    def store_progress(self, value):
        return self.ld_a(value).ld_mem_a(PROGRESS)


def build_program_download_com(name: bytes = b"HELLO", workstation: bytes = b"12345678",
                               operation: int = OP_LOAD):
    """A COM that drives a Commstar **program download** to completion.

    C-INIT-COMMS -> C-DIAL -> C-COMMAND(LOAD, name) -> C-RX-BLK until the
    status is 8, appending every block to ``ACC``. Returns (image, marker
    address); the marker is the last byte of the image so it can never collide
    with the code.
    """
    a = Asm()
    a.ld_hl("name_data").ld_de(NAMEPARM).ld_bc(16).ldir()
    a.ld_hl("ws_data").ld_de(WSBUF).ld_bc(16).ldir()
    a.ld_a(0).ld_mem_a(NULSTR)
    a.ld_hl(0).ld_mem_hl(STATUS)
    a.ld_hl(0).ld_mem_hl(NBLK)
    a.ld_hl(0).ld_mem_hl(TOTAL)
    a.ld_hl(ACC).ld_mem_hl(DSTPTR)

    a.store_progress(0x10)
    # Ten arguments, in the firmware's own order (ROM01:12AD-1304): the third
    # slot is the session mode -> ram:E48D, and the second is the link type
    # -> ram:E520, 4 = LOCAL LINK, the IR path.
    a.entry(EE_INIT_COMMS, [0, 4, 0, 0x0E, 0x3C,
                            NULSTR, NULSTR, WSBUF, NULSTR, NULSTR])
    a.ld_mem_hl(STATUS).ld_a_h().or_l().jp_nz("fail_init")

    a.store_progress(0x20)
    a.entry(EE_DIAL, [NULSTR])
    a.ld_mem_hl(STATUS).ld_a_h().or_l().jp_nz("fail_dial")

    a.store_progress(0x30)
    # SP+0 operation index, SP+2 the 12-byte parameter (the program name),
    # SP+4 the reply buffer the host's OK/NO/DM answer is read into.
    a.entry(EE_COMMAND, [operation, NAMEPARM, REPLY])
    a.ld_mem_hl(STATUS).ld_a_h().or_l().jp_nz("fail_cmd")

    a.store_progress(0x40)
    a.label("loop")
    a.entry(EE_RX_BLK, [BLKBUF])
    a.ld_mem_hl(STATUS)
    a.ld_a_h().or_a().jp_nz("fail_blk")
    a.ld_a_l().cp(8).jp_z("last")
    a.or_a().jp_nz("fail_blk")
    a.call("take_block")
    a.ld_a_mem(NBLK).cp(64).jp_nc("fail_runaway")
    a.jp("loop")

    a.label("last").call("take_block").store_progress(0x55).jp("done")
    for label, code in (("fail_init", 0xE1), ("fail_dial", 0xE2),
                        ("fail_cmd", 0xE3), ("fail_blk", 0xE4),
                        ("fail_runaway", 0xE5)):
        a.label(label).store_progress(code).jp("done")

    a.label("done").ld_a(0x5A).ld_mem_a("marker")
    a.label("spin").jp("spin")

    # Append BLKBUF's payload to ACC and count the block.
    a.label("take_block")
    a.ld_a_mem(BLKBUF).or_a().jp_z("tb_count")
    a.ld_c_a().ld_b(0)
    a.ld_hl(BLKBUF + 1).ld_de_mem(DSTPTR).ldir().ld_mem_de(DSTPTR)
    a.ld_a_mem(BLKBUF).ld_l_a().ld_h(0)
    a.ld_de_mem(TOTAL).add_hl_de().ld_mem_hl(TOTAL)
    a.label("tb_count")
    a.ld_hl_mem(NBLK).inc_hl().ld_mem_hl(NBLK).ret()

    a.label("name_data").db(name[:12].ljust(16, b"\0"))
    a.label("ws_data").db(workstation[:15].ljust(16, b"\0"))
    a.label("marker").db(0x00)
    return a.link(), a.labels["marker"]


# ---------------------------------------------------------------- Task B ----
NAMEREC = 0xE830    # [u8 len][file name]  for C-BEGIN-FILE
RECBUF  = 0xE860    # [u8 count][record]   for C-TX-REC
DISPBUF = 0xE8C0    # C-END-TX's disposition argument
BIGREPLY = 0xE900   # C-COMMAND reply buffer for the teardown driver
TRACE   = 0x0620    # {u8 state, u8 mode, u16 result} per step, in our own page

G_SESSION_STATE = 0xE22D    # Session_SetState's only cell (ROM00:3BF5)
G_SESSION_MODE = 0xE48D     # the mode gate C-END-TX's completion path tests


def build_clean_teardown_com(name: bytes = b"STOCK", record: bytes = b"REC-ONE",
                             workstation: bytes = b"12345678",
                             parameter: bytes = b"DATA1",
                             mode: int = 1, operation: int = OP_SEND,
                             mode_before_end_tx: int | None = None,
                             pad: int = 0):
    """A COM that drives a data upload and ends it through ``C-END-TX``'s
    *clean completion* path rather than the abort path.

    The two things that path needs (``ROM00:530D``-``5337``) are
    ``ram:E48D == 1`` and a session state from which ``C-END-TX`` is legal.
    ``C-INIT-COMMS``'s third argument sets the first; ``C-COMMAND`` with the
    ``SEND`` operation index sets the second, writing ``READY-TX-DATA``
    straight out of ``tbl_sess_operations`` (``ROM00:4B3D`` stages it in
    ``ram:E491``, ``ROM00:4C69`` -- or ``4B56`` when the mode is 1 -- commits
    it) without consulting the transition table.

    After every step it records the session state, the mode byte and the
    result, so a run that diverges says exactly where.

    ``pad`` prepends that many NOPs, which is how the length-dependence
    regression below varies the image length without changing its meaning.

    A 561-byte build of this driver used to fail reproducibly -- the first
    0064 exchange after ``C-DIAL`` returned 4 and the session ended "Session
    aborted" -- while 556-560 and 562 succeeded. It was a harness bug, not a
    firmware one: ``boot_hw.py`` staged each upload chunk as 256 bytes at
    ``ram:E5C2``, which runs to ``ram:E6C1`` and so buries live Commstar
    session state (``ram:E69F``-``E6B3``, ``SessionRxByteGet``'s pushback
    buffer and its count word at ``ram:E6A9``) under image bytes that the
    session then read back. Which bytes survived depended on how much of the
    window the final short chunk overwrote -- that is, on the image length.
    Chunks are now capped to the 126-byte real receive object and the window
    is restored after the upload; see ``UPLOAD_BUFFER_MAX`` in the harness.
    """
    namerec = bytes([len(name)]) + name
    recbuf = bytes([len(record)]) + record

    a = Asm()
    for _ in range(pad):
        a.db(0x00)          # NOP padding, to vary code length without meaning
    a.ld_hl("name_data").ld_de(NAMEPARM).ld_bc(16).ldir()
    a.ld_hl("ws_data").ld_de(WSBUF).ld_bc(16).ldir()
    a.ld_hl("name_rec").ld_de(NAMEREC).ld_bc(len(namerec)).ldir()
    a.ld_hl("rec_data").ld_de(RECBUF).ld_bc(len(recbuf)).ldir()
    a.ld_a(0).ld_mem_a(NULSTR)
    a.ld_hl(0).ld_mem_hl(DISPBUF)
    a.ld_hl(0).ld_mem_hl(STATUS)

    def step(index, slot, args, failcode):
        a.store_progress(0x10 * (index + 1))
        a.entry(slot, args)
        a.ld_mem_hl(STATUS)
        # {state, mode, result} for this step
        a.ld_a_mem(G_SESSION_STATE).ld_mem_a(TRACE + 4 * index)
        a.ld_a_mem(G_SESSION_MODE).ld_mem_a(TRACE + 4 * index + 1)
        a.ld_hl_mem(STATUS).ld_mem_hl(TRACE + 4 * index + 2)
        a.ld_hl_mem(STATUS).ld_a_h().or_l().jp_nz(failcode)

    step(0, EE_INIT_COMMS,
         [0, 4, mode, 0x0E, 0x3C, NULSTR, NULSTR, WSBUF, NULSTR, NULSTR], "fail0")
    step(1, EE_DIAL, [NULSTR], "fail1")
    step(2, EE_COMMAND, [operation, NAMEPARM, BIGREPLY], "fail2")
    step(3, EE_BEGIN_FILE, [NAMEREC], "fail3")
    step(4, EE_TX_REC, [RECBUF], "fail4")
    step(5, EE_END_FILE, [], "fail5")
    if mode_before_end_tx is not None:
        # Switch the mode gate to 1 for the teardown only, so C-COMMAND still
        # transmits its command record but C-END-TX still finishes cleanly.
        a.ld_a(mode_before_end_tx).ld_mem_a(G_SESSION_MODE)
    step(6, EE_END_TX, [DISPBUF], "fail6")

    a.store_progress(0x55).jp("done")
    for index in range(7):
        a.label(f"fail{index}").store_progress(0xE0 + index).jp("done")
    a.label("done").ld_a(0x5A).ld_mem_a("marker")
    a.label("spin").jp("spin")

    a.label("name_data").db(parameter[:12].ljust(16, b"\0"))
    a.label("ws_data").db(workstation[:15].ljust(16, b"\0"))
    a.label("name_rec").db(namerec)
    a.label("rec_data").db(recbuf)
    a.label("marker").db(0x00)
    return a.link(), a.labels["marker"]


@unittest.skipUnless(RUN_EMULATOR, "set MICRONIC_RUN_EMULATOR_TESTS=1")
class CommstarProgramDownloadTest(unittest.TestCase):
    """The host-to-handheld direction, driven from a loaded application.

    C-INIT-COMMS -> C-DIAL -> C-COMMAND "LOAD" -> C-RX-BLK until the status is
    8, with micronic.peer.ProgramDownloadPolicy supplying the image. This is
    the path a Commstar server has to serve first, and the assertion is that
    what arrived is what was sent, byte for byte.
    """

    IMAGE = bytes(0x41 + (index % 26) for index in range(300))

    def _download(self, image: bytes, name: bytes = b"HELLO", chunk: int = 126):
        com, marker = build_program_download_com(name=name)
        with tempfile.TemporaryDirectory() as tmp:
            com_path = Path(tmp) / "dl.com"
            com_path.write_bytes(com)
            img_path = Path(tmp) / "image.bin"
            img_path.write_bytes(image)
            proc = subprocess.run(
                [str(PYTHON), str(HARNESS), "--commstar-peer",
                 "--commstar-serve-program", str(img_path),
                 "--commstar-program-name", name.decode(),
                 "--commstar-chunk", str(chunk),
                 "--upload", str(com_path),
                 "--upload-marker", f"{marker:04x}:5A",
                 "--dump-mem", f"{STATUS:04x}:10",
                 "--dump-mem", f"{ACC:04x}:{len(image)}"],
                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=900, check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        return proc.stdout

    @staticmethod
    def _dump(stdout: str, addr: int, length: int) -> bytes:
        prefix = f"[mem] final {addr:04X}:{length}"
        for line in stdout.splitlines():
            if line.startswith(prefix):
                return bytes(int(x, 16)
                             for x in line[len(prefix):].split(" |")[0].split())
        raise AssertionError(f"no dump of {addr:04X}:\n{stdout}")

    def test_a_download_spanning_several_blocks_arrives_intact(self):
        out = self._download(self.IMAGE)
        # {result, blocks, total, write pointer, progress} the driver kept.
        state = self._dump(out, STATUS, 10)
        self.assertEqual(state[8], 0x55, f"driver stopped early: {state.hex()}")
        result = state[0] | state[1] << 8
        blocks = state[2] | state[3] << 8
        total = state[4] | state[5] << 8
        self.assertEqual(result, 8, "the last C-RX-BLK did not return end-of-data")
        self.assertEqual(total, len(self.IMAGE))
        self.assertGreater(blocks, 1, "the image did not span more than one block")
        self.assertEqual(self._dump(out, ACC, len(self.IMAGE)), self.IMAGE)

    def test_the_firmware_says_program_received(self):
        out = self._download(self.IMAGE)
        self.assertIn("Program received", out)
        self.assertNotIn("Abort pending", out)

    def test_the_peer_sees_the_load_command_and_the_program_name(self):
        out = self._download(self.IMAGE, name=b"PROG1")
        self.assertIn("[commstar-peer] command 'LOAD' workstation='12345678' "
                      "parameter='PROG1'", out)

    def test_the_wire_states_are_the_documented_download_sequence(self):
        """0044 appears once for the command reply and once per block."""
        out = self._download(self.IMAGE)
        line = next(l for l in out.splitlines() if "request states seen:" in l)
        states = line.split("seen: ")[1].split()
        self.assertEqual(states[:5], ["0000", "0006", "0062", "0064", "0045"])
        self.assertEqual(set(states[5:]), {"0044"})
        # one reply to C-COMMAND plus three blocks for 300 bytes at 126.
        self.assertEqual(len(states[5:]), 4, states)

    def test_the_served_blocks_are_the_image(self):
        out = self._download(self.IMAGE)
        served = next(l for l in out.splitlines()
                      if "[commstar-peer] program served: " in l)
        self.assertEqual(bytes.fromhex(served.split(": ")[1]), self.IMAGE)


@unittest.skipUnless(RUN_EMULATOR, "set MICRONIC_RUN_EMULATOR_TESTS=1")
class CommstarCleanTeardownTest(unittest.TestCase):
    """A session that ends on ``Data transmitted``, not ``Abort pending``.

    C-END-TX's completion path needs a session state from which it is legal.
    C-COMMAND reaches one by writing the operation table's target state
    directly -- index 2 ``SEND`` gives READY-TX-DATA, which no transition in
    the matrix produces. Both dispositions of the completion are exercised:
    mode 1 takes the branch at ROM00:531C, mode 0 takes the argument branch at
    533E, and both end by committing ram:E48C and showing ram:E516.
    """

    def _run(self, **kwargs):
        com, marker = build_clean_teardown_com(**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            com_path = Path(tmp) / "tx.com"
            com_path.write_bytes(com)
            proc = subprocess.run(
                [str(PYTHON), str(HARNESS), "--commstar-peer",
                 "--upload", str(com_path),
                 "--upload-marker", f"{marker:04x}:5A",
                 "--dump-mem", f"{PROGRESS:04x}:1",
                 "--dump-mem", f"{TRACE:04x}:28",
                 "--dump-mem", "e48d:1"],
                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=900, check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        return proc.stdout

    @staticmethod
    def _trace(stdout: str):
        """The {state, mode, result} the driver recorded after each command."""
        prefix = f"[mem] final {TRACE:04X}:28"
        line = next(l for l in stdout.splitlines() if l.startswith(prefix))
        raw = bytes(int(x, 16)
                    for x in line[len(prefix):].split(" |")[0].split())
        return [(raw[i], raw[i + 1], raw[i + 2] | raw[i + 3] << 8)
                for i in range(0, 28, 4)]

    def test_mode_one_reaches_the_completion_at_531c(self):
        out = self._run(mode=1)
        self.assertIn("Data transmitted", out)
        self.assertNotIn("Abort pending", out)
        self.assertNotIn("Session aborted", out)
        states = [entry[0] for entry in self._trace(out)]
        # DISCONNECTED, CONNECTED, READY-TX-DATA, RECORD-TX, RECORD-TX,
        # DATA-SET-TX, back to CONNECTED.
        self.assertEqual(states, [1, 2, 5, 9, 9, 10, 2])
        self.assertTrue(all(entry[1] == 1 for entry in self._trace(out)),
                        "the mode gate did not stay at 1")
        self.assertTrue(all(entry[2] == 0 for entry in self._trace(out)),
                        "a command reported an error")

    def test_mode_one_keeps_c_command_off_the_wire(self):
        """With the gate at 1, C-COMMAND returns at ROM00:4B4F without sending.

        This is the cost of the clean teardown: the host never sees the SEND
        command record, only the file it produces.
        """
        out = self._run(mode=1)
        line = next(l for l in out.splitlines() if "request states seen:" in l)
        self.assertEqual(line.split("seen: ")[1].split(),
                         ["0000", "0006", "0062", "0064", "0045"])

    def test_mode_zero_sends_the_command_record_and_still_finishes_cleanly(self):
        out = self._run(mode=0)
        self.assertIn("Data transmitted", out)
        self.assertNotIn("Abort pending", out)
        states = [entry[0] for entry in self._trace(out)]
        self.assertEqual(states, [1, 2, 5, 9, 9, 10, 2])
        # Two command records: C-COMMAND's 54-byte one and the file itself.
        self.assertIn("[commstar-peer] record from 0x0045 arg=1: "
                      "0553544f434b1e5245432d4f4e451c", out)

    def test_the_uploaded_file_is_the_documented_record_stream(self):
        out = self._run(mode=1)
        self.assertIn("[commstar-peer] record from 0x0045 arg=1: "
                      "0553544f434b1e5245432d4f4e451c", out)

    def test_the_image_length_does_not_change_the_outcome(self):
        """The same driver, padded to six lengths, must finish the same way.

        This is the regression for the harness bug described on
        build_clean_teardown_com: staging upload chunks over ``ram:E5C2`` in
        256-byte writes left image bytes in the session's own RAM, and 561
        bytes was the length at which the residue broke the first 0064
        exchange. Any length dependence here means the harness is writing
        somewhere the session can see it.
        """
        for pad in range(6):
            with self.subTest(length=556 + pad):
                out = self._run(mode=1, pad=pad)
                self.assertIn("Data transmitted", out)
                self.assertNotIn("Session aborted", out)
                self.assertEqual([entry[0] for entry in self._trace(out)],
                                 [1, 2, 5, 9, 9, 10, 2])


@unittest.skipUnless(RUN_EMULATOR, "set MICRONIC_RUN_EMULATOR_TESTS=1")
class CommstarShadowPeerTest(unittest.TestCase):
    """The protocol-aware peer must agree with the hand-written phase script.

    micronic.peer.CommstarPeer runs alongside the scripted responder during a
    real trace and is asked what it would have replied at each point. Until it
    agrees everywhere, it cannot replace the script.
    """

    def _trace(self, *extra):
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
                [str(PYTHON), str(HARNESS), *extra,
                 "--synthetic-loadrun", str(image), "--synthetic-loadrun-finalize"],
                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=300, check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("loadrun_source_trace_status=succeeded", proc.stdout)
        line = next(l for l in proc.stdout.splitlines() if "[shadow-peer] agreed=" in l)
        fields = dict(p.split("=") for p in line.split("] ")[1].split())
        return {k: int(v) for k, v in fields.items()}, proc.stdout

    def test_agrees_on_the_v24_route(self):
        counts, out = self._trace("--trace-loadrun-source", "v24",
                                  "--trace-loadrun-v24-mode", "1")
        self.assertEqual(counts["differed"], 0, out)
        self.assertGreaterEqual(counts["agreed"], 12)

    def test_agrees_on_the_plinth_route(self):
        counts, out = self._trace("--trace-loadrun-source", "plinth")
        self.assertEqual(counts["differed"], 0, out)
        self.assertGreaterEqual(counts["agreed"], 13)


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
