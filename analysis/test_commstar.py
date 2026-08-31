#!/usr/bin/env python3
"""Unit tests for the application-owned synthetic Commstar policy."""
import unittest

from micronic.commstar import SyntheticWorkflow


class SyntheticWorkflowTest(unittest.TestCase):
    def test_stock_check_sequence(self):
        workflow = SyntheticWorkflow.from_dict(
            {
                "source": "plinth",
                "scan_records": [{"barcode": "0123456789012"}],
                "image": "items.dip",
                "run_after_load": True,
                "feedback": "list_updated",
                "safe_to_remove": True,
            }
        )
        self.assertEqual(
            workflow.events(),
            (
                ("session", "plinth"),
                ("upload_scan", {"barcode": "0123456789012"}),
                ("download_image", "items.dip"),
                ("run_image", "items.dip"),
                ("feedback", "list_updated"),
                ("safe_to_remove", None),
            ),
        )

    def test_rejects_unknown_source(self):
        with self.assertRaises(ValueError):
            SyntheticWorkflow.from_dict({"source": "serial"})


if __name__ == "__main__":
    unittest.main()
