# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Compression resource regressions runnable without application fixtures or services."""

import asyncio
import bz2
import gzip
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from flyquery.core.services.ingestion import compression


class _CompressionResources:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="compression-ownership-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.outputs = self.root / "outputs"
        self.outputs.mkdir()
        mkstemp = tempfile.mkstemp
        self.enterContext(
            patch.object(compression.tempfile, "mkstemp", side_effect=lambda **kw: mkstemp(dir=self.outputs, **kw))
        )
        self.enterContext(patch.object(compression, "MAX_DECOMPRESSED_BYTES", 65536))

    def archive(self, format, payload):
        source = self.root / ("data.csv." + format)
        if format == "gz":
            source.write_bytes(gzip.compress(payload))
        elif format == "bz2":
            source.write_bytes(bz2.compress(payload))
        elif format == "zip":
            with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("data.csv", payload)
        return source


class CompressionOwnershipTests(_CompressionResources, unittest.TestCase):
    def test_expansion_rejection_removes_partial_output(self):
        for format in ("gz", "bz2", "zip"):
            with self.subTest(format=format):
                source = self.archive(format, b"0" * 131072)
                existing = set(self.outputs.iterdir())
                with self.assertRaisesRegex(ValueError, "decompressed size exceeded cap"):
                    compression._sync(str(source), format)
                self.assertEqual(set(self.outputs.iterdir()), existing)
                self.assertTrue(source.is_file())

    def test_malformed_stream_removes_allocated_output(self):
        for format in ("gz", "bz2", "zip"):
            with self.subTest(format=format):
                source = self.root / ("damaged.csv." + format)
                source.write_bytes(b"not an archive")
                existing = set(self.outputs.iterdir())
                with self.assertRaises((OSError, EOFError, zipfile.BadZipFile)):
                    compression._sync(str(source), format)
                self.assertEqual(set(self.outputs.iterdir()), existing)
                self.assertEqual(source.read_bytes(), b"not an archive")

    def test_multifile_zip_rejection_removes_allocated_output(self):
        source = self.root / "multiple.csv.zip"
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("a.csv", b"one")
            archive.writestr("b.csv", b"two")
        with self.assertRaisesRegex(ValueError, "multiple files"):
            compression._sync(str(source), "zip")
        self.assertEqual(list(self.outputs.iterdir()), [])

    def test_success_transfers_exact_output_to_caller(self):
        payload = b"column\nvalue\n"
        for format in ("gz", "bz2", "zip", "none"):
            with self.subTest(format=format):
                source = self.archive(format, payload)
                if format == "none":
                    source.write_bytes(payload)
                output = Path(compression._sync(str(source), format))
                self.assertNotEqual(output, source)
                self.assertEqual(output.read_bytes(), payload)
                self.assertTrue(source.is_file())
                output.unlink()
                self.assertEqual(list(self.outputs.iterdir()), [])

    def test_copy_failure_removes_allocated_output(self):
        with self.assertRaises(FileNotFoundError):
            compression._sync(str(self.root / "missing.csv"), "none")
        self.assertEqual(list(self.outputs.iterdir()), [])


class CompressionCancellationTests(_CompressionResources, unittest.IsolatedAsyncioTestCase):
    async def test_async_success_transfers_exact_output_to_caller(self):
        source = self.archive("gz", b"column\nvalue\n")
        output = Path(await compression.decompress_to_temp(str(source), "gz"))
        self.assertEqual(output.read_bytes(), b"column\nvalue\n")
        self.assertNotEqual(output, source)
        output.unlink()
        self.assertEqual(list(self.outputs.iterdir()), [])
        self.assertTrue(source.is_file())

    async def cancelled_worker(self, payload):
        source = self.archive("gz", payload)
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        copy, sync = compression._bounded_copy, compression._sync

        def blocked_copy(*arguments):
            started.set()
            if not release.wait(5):
                raise AssertionError("Test did not release its worker")
            return copy(*arguments)

        def tracked_sync(*arguments):
            try:
                return sync(*arguments)
            finally:
                finished.set()

        with patch.object(compression, "_bounded_copy", blocked_copy), patch.object(
            compression, "_sync", tracked_sync
        ):
            task = asyncio.create_task(compression.decompress_to_temp(str(source), "gz"))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 5))
                task.cancel()
                await asyncio.sleep(0)
                self.assertFalse(task.done(), "Cancellation abandoned the live decompression worker")
                task.cancel()
                await asyncio.sleep(0)
                self.assertFalse(task.done(), "Repeated cancellation abandoned worker ownership")
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 5)
                self.assertTrue(finished.is_set())
                self.assertEqual(list(self.outputs.iterdir()), [])
                self.assertTrue(source.is_file())
            finally:
                release.set()
                await asyncio.gather(task, return_exceptions=True)
                self.assertTrue(await asyncio.to_thread(finished.wait, 5))

    async def test_cancellation_waits_for_worker_and_reclaims_successful_output(self):
        await self.cancelled_worker(b"column\nvalue\n")

    async def test_cancellation_waits_for_failed_worker_cleanup(self):
        await self.cancelled_worker(b"0" * 131072)


class CompressionShutdownTests(_CompressionResources, unittest.TestCase):
    def shutdown_worker(self, *, returned):
        source = self.archive("gz", b"column\nvalue\n")
        started, release, finished, wrapper_done = (
            threading.Event(), threading.Event(), threading.Event(), threading.Event()
        )
        copy, sync = compression._bounded_copy, compression._sync

        def blocked_copy(*arguments):
            started.set()
            if not release.wait(5):
                raise AssertionError("Test did not release its worker")
            return copy(*arguments)

        def tracked_sync(*arguments):
            try:
                return sync(*arguments)
            finally:
                finished.set()

        def release_after_wrapper_shutdown():
            wrapper_done.wait(5)
            release.set()

        async def leave_pending_worker():
            task = asyncio.create_task(compression.decompress_to_temp(str(source), "gz"))
            task.add_done_callback(lambda _: wrapper_done.set())
            self.assertTrue(await asyncio.to_thread(started.wait, 5))
            if returned:
                release.set()
                # Keep the loop from delivering the worker result before runner shutdown.
                self.assertTrue(finished.wait(5))

        controller = threading.Thread(target=release_after_wrapper_shutdown)
        with patch.object(compression, "_bounded_copy", blocked_copy), patch.object(
            compression, "_sync", tracked_sync
        ):
            controller.start()
            try:
                asyncio.run(leave_pending_worker())
            finally:
                release.set()
                controller.join(5)
        self.assertFalse(controller.is_alive())
        self.assertTrue(wrapper_done.is_set())
        self.assertTrue(finished.is_set())
        self.assertEqual(list(self.outputs.iterdir()), [])
        self.assertTrue(source.is_file())

    def test_graceful_runner_shutdown_cleans_output_from_live_thread(self):
        self.shutdown_worker(returned=False)

    def test_graceful_runner_shutdown_cleans_output_returned_before_parent_claim(self):
        self.shutdown_worker(returned=True)
