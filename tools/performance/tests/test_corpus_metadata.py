# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import unittest
from pathlib import Path
from tempfile import mkdtemp

from corpus_metadata import measure


class MetadataProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_repository_batches_complete_selection_and_excludes_foreign_rows(self):
        result = await measure(201, 401, Path(mkdtemp(prefix="koinon-metadata-proof-")))
        self.assertEqual(result["selected_sources"], 201)
        self.assertEqual(result["returned_sources"], 201)
        self.assertEqual(result["sql_statements"], 2)
        self.assertEqual(result["duplicate_filename_keys"], 201)
        self.assertEqual(result["unexpected_scope_rows"], 0)
        self.assertEqual(result["object_reads"], 0)
        self.assertEqual(result["provider_calls"], 0)
        self.assertTrue(result["first_batch_query_plan"])
        self.assertGreater(result["elapsed_seconds"], 0)
        self.assertGreater(result["process_cpu_seconds"], 0)
        self.assertGreater(result["process_lifetime_peak_rss_bytes"], 0)

    async def test_invalid_sizes_fail_before_creating_a_fixture(self):
        for selected, stored in ((0, 10), (2, 1), (-1, 1), (100001, 100001)):
            with self.assertRaises(ValueError):
                await measure(selected, stored, Path("unused"))

    async def test_analyzed_fixture_preserves_scope_and_labels_statistics(self):
        result = await measure(
            10, 1000, Path(mkdtemp(prefix="koinon-metadata-analyzed-")), analyze=True,
        )
        self.assertEqual(result["returned_sources"], 10)
        self.assertEqual(result["sql_statements"], 1)
        self.assertIn("ANALYZE completed", result["statistics"])


if __name__ == "__main__":
    unittest.main()
