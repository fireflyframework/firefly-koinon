# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Qualify probe receipts against real native parsers and Office originals."""

import tempfile
import unittest
from pathlib import Path

from office_files import digest, make_fixture, measure


class OfficeFilesProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_formats_preserve_every_marker_and_original(self):
        with tempfile.TemporaryDirectory() as directory:
            for kind in ("docx", "xlsx", "csv", "pptx"):
                with self.subTest(kind=kind):
                    path = Path(directory) / f"evidence.{kind}"
                    make_fixture(path, kind, 3)
                    original_hash = digest(path)
                    receipt = await measure(path, 3)
                    self.assertEqual(receipt["markers_verified"], 3)
                    self.assertEqual(receipt["original_sha256"], original_hash)
                    self.assertEqual(digest(path), original_hash)
                    self.assertEqual(receipt["original_bytes"], path.stat().st_size)
                    self.assertGreater(receipt["elapsed_seconds"], 0)
                    self.assertGreater(receipt["child_cpu_seconds"], 0)
                    self.assertGreater(receipt["child_peak_rss_bytes"], 0)
                    self.assertGreater(receipt["text_bytes"], 0)
                    self.assertEqual(receipt["policy"]["raw_max_bytes"], 128 * 1024**2)

    def test_fixture_refuses_overwrite_or_unbounded_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "retained.csv"
            make_fixture(path, "csv", 2)
            original_hash = digest(path)
            with self.assertRaises(FileExistsError):
                make_fixture(path, "csv", 3)
            with self.assertRaises(ValueError):
                make_fixture(Path(directory) / "oversized.csv", "csv", 50001)
            self.assertEqual(digest(path), original_hash)


if __name__ == "__main__":
    unittest.main()
