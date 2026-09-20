"""Assemble the documented example and verify its packaging and operands."""

import unittest
from pathlib import Path

from micronic.program import build_dip_file, validate
from micronic.z80asm import assemble


class DocExampleTest(unittest.TestCase):
    def test_hello_image_and_dip(self):
        source = Path(__file__).parent / "examples" / "hello.asm"
        manual = source.parents[2] / "doc" / "manual" / "first-program.md"
        listing = manual.read_text().split("```asm\n", 1)[1].split("```", 1)[0]
        self.assertEqual(listing.strip(), source.read_text().strip())
        image, symbols = assemble(source.read_text(), origin=0x100)
        self.assertEqual(len(image), 30)
        self.assertEqual(symbols["message"], 0x110)
        self.assertEqual(image[:16], bytes.fromhex("1110010e09cd05003ea5320002c30000"))
        self.assertEqual(image[16:], b"Hello World\r\n$")
        self.assertTrue(validate(image).valid)
        package = build_dip_file(
            header_kwargs={"image_size": len(image), "entry_address": 0x100},
            blocks=[(0, 0, 0x100, image)],
        )
        result = validate(package)
        self.assertTrue(result.valid)
        self.assertEqual(result.blocks[0].payload, image)
        self.assertEqual(len(package), 52)


if __name__ == "__main__":
    unittest.main()
