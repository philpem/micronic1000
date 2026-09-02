"""The optional symbology-identifier prefix.

Off by default, because turning it on changes the bytes an application
receives.  These tests build a second decoder with SYMBOLOGY_ID=1 and check
that every symbology announces itself and that the data is otherwise
untouched.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT.parent / "analysis"))

from conftest import requires_emulator, ORIGIN         # noqa: E402
from micronic.barcode import encode_code39             # noqa: E402
import upc                                             # noqa: E402

pytestmark = requires_emulator


@pytest.fixture(scope="module")
def id_decoder():
    build = ROOT / "build-symid"
    r = subprocess.run(["make", f"ORIGIN={ORIGIN:#06x}", f"BUILD={build.name}",
                        "SYMBOLOGY_ID=1"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        pytest.fail(f"build failed:\n{r.stdout}\n{r.stderr}")
    return (build / "decoder.bin").read_bytes()


@pytest.fixture
def decode_id(id_decoder):
    """Decode with the SYMBOLOGY_ID build."""
    from conftest import run_decoder
    return lambda widths: run_decoder(id_decoder, widths)


def upce_w(ns, six):
    d = [int(c) for c in six]
    return upc.upce_widths(ns, d), f"{ns}{six}{upc.upce_check(ns, d)}"


def ean_w(twelve):
    d = [int(c) for c in twelve]
    d.append(upc.check_digit(d))
    return upc.widths(d), "".join(map(str, d))


def upca_w(eleven):
    d = [int(c) for c in eleven]
    d.append(upc.check_digit(d))
    return upc.widths(d), "".join(map(str, d))


class TestSymbologyId:
    def test_code39(self, decode_id):
        assert decode_id(encode_code39("A1")) == b"CA1"

    def test_upc_a(self, decode_id):
        widths, text = upca_w("03600029145")
        assert decode_id(widths) == b"U" + text.encode()

    def test_ean13(self, decode_id):
        widths, text = ean_w("590123412345")
        assert decode_id(widths) == b"E" + text.encode()

    def test_upc_e(self, decode_id):
        widths, text = upce_w(0, "123456")
        assert decode_id(widths) == b"e" + text.encode()

    def test_itf(self, decode_id):
        assert decode_id(upc.itf_widths("1234")) == b"I1234"

    def test_codabar(self, decode_id):
        assert decode_id(upc.codabar_widths("A123B")) == b"KA123B"

    def test_code128(self, decode_id):
        assert decode_id(upc.code128_widths("HELLO")) == b"BHELLO"

    def test_a_rejection_is_still_a_rejection(self, decode_id):
        """No identifier on a scan that did not decode."""
        assert decode_id([12] * 59) == b""

    def test_the_data_is_otherwise_untouched(self, decode_id, decode):
        """The prefixed result is exactly the plain one with a letter added."""
        widths = encode_code39("CODE-39")
        assert decode_id(widths) == b"C" + decode(widths)
