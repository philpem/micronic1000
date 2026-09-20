"""Regression cases for defects that a strict MkDocs build accepts."""

import tempfile
import unittest
from pathlib import Path

from check_docs import check_site


class CheckDocsTest(unittest.TestCase):
    def check(self, files):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename, contents in files.items():
                target = root / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(contents, encoding="utf-8")
            return check_site(root)

    def test_empty_site_fails(self):
        self.assertIn("no generated HTML", self.check({})[0])

    def test_unrendered_table_fails(self):
        issues = self.check({"index.html": "<article><p>| A | B |\n|---|\n| 1 | 2 |</p></article>"})
        self.assertIn("did not render", issues[0])

    def test_ragged_table_fails(self):
        issues = self.check({"index.html": "<article><table><tr><th>A</th><th>B</th></tr><tr><td>1</td></tr></table></article>"})
        self.assertIn("column counts", issues[0])

    def test_colspan_and_valid_fragment(self):
        self.assertEqual(self.check({
            "index.html": '<article><a href="page/#a%20b">Go</a><table><tr><th>A</th><th>B</th></tr><tr><td colspan="2">Both</td></tr></table></article>',
            "page/index.html": '<article><h1 id="a b">Page</h1><a href="../">Home</a></article>',
        }), [])

    def test_missing_directory_and_fragment(self):
        issues = self.check({"index.html": '<article><a href="reviews/">Missing</a><a href="#absent">Missing</a></article>'})
        self.assertEqual(len(issues), 2)
        self.assertIn("missing local target", issues[0])
        self.assertIn("missing fragment", issues[1])

    def test_assets_and_external_links(self):
        issues = self.check({"index.html": '<script src="missing.js"></script><article><a href="https://example.com/missing">External</a><a href="mailto:owner@example.com">Mail</a><pre>| A |\n| B |</pre></article>'})
        self.assertEqual(len(issues), 1)
        self.assertIn("missing.js", issues[0])


if __name__ == "__main__":
    unittest.main()
