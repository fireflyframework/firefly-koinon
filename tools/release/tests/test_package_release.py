# Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
"""Inert safety probes for the release operator; no product services or builds."""

import io
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from package_release import (
    clean_commit,
    main,
    members,
    retain_uv_marker,
    safe_name,
    tar_directory,
    verify_versions,
)


class ArchiveTests(unittest.TestCase):
    def test_operator_cannot_lower_disk_floor(self):
        with (
            patch(
                "sys.argv",
                [
                    "package_release.py",
                    "--checkout",
                    "/absent",
                    "--commit",
                    "a" * 40,
                    "--version",
                    "26.11.11",
                    "--output",
                    "/absent-output",
                    "--java-home",
                    "/absent-java",
                    "--min-free-gib",
                    "15",
                ],
            ),
            self.assertRaisesRegex(RuntimeError, "cannot be below 16"),
        ):
            main()

    def test_uv_control_marker_is_retained_outside_upload_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets, evidence = root / "assets", root / "evidence"
            assets.mkdir()
            evidence.mkdir()
            (assets / ".gitignore").write_text("*")
            retain_uv_marker(assets, evidence)
            self.assertFalse(list(assets.iterdir()))
            self.assertEqual((evidence / "uv-output.gitignore.txt").read_text(), "*")

    def test_traversal_and_private_inputs_are_rejected(self):
        for name in (
            "../secret",
            "/tmp/x",
            "a/../../x",
            "a\\x",
            "C:/x",
            "node_modules/x",
            "x/.env",
            "x/connection.private.json",
            ".git/config",
            "x/.npmrc",
        ):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                safe_name(name)
        safe_name("backend/.env.example")
        safe_name("assets/brand/fonts/Inter-OFL.txt")

    def test_tar_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.tar"
            with tarfile.open(path, "w") as archive:
                entry = tarfile.TarInfo("x")
                entry.type, entry.linkname = tarfile.SYMTYPE, "/etc/passwd"
                archive.addfile(entry)
            with self.assertRaises(RuntimeError):
                members(path)

    def test_tar_duplicate_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.tar"
            with tarfile.open(path, "w") as archive:
                for _ in range(2):
                    entry = tarfile.TarInfo("x")
                    entry.size = 1
                    archive.addfile(entry, io.BytesIO(b"x"))
            with self.assertRaises(RuntimeError):
                members(path)

    def test_zip_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escape", b"x")
            with self.assertRaises(RuntimeError):
                members(path)

    def test_bundle_has_reproducible_root_and_legal_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "index.html").write_text("hello")
            legal = root / "LICENSE"
            legal.write_text("license")
            first, second = root / "a.tar.gz", root / "b.tar.gz"
            for path in (first, second):
                tar_directory(source, path, 1000, {"LICENSE": legal})
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(
                members(first), {"LICENSE": b"license", "index.html": b"hello"}
            )

    def test_legal_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "LICENSE").write_text("unexpected")
            legal = root / "LICENSE"
            legal.write_text("license")
            with self.assertRaises(RuntimeError):
                tar_directory(source, root / "x.tar.gz", 1000, {"LICENSE": legal})

    def test_prerelease_is_rejected_before_manifest_reads(self):
        with self.assertRaisesRegex(RuntimeError, "prereleases rejected"):
            verify_versions(Path("/absent"), "26.10.1-alpha.1")


class CommitTests(unittest.TestCase):
    def test_mismatched_or_dirty_checkout_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output(
                    ["git", "-C", str(root), *args], text=True
                ).strip()

            git("init", "--quiet")
            (root / "a").write_text("a")
            git("add", "a")
            git(
                "-c",
                "user.name=Inert Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "fixture",
            )
            commit = git("rev-parse", "HEAD")
            self.assertEqual(
                clean_commit(root, commit), git("rev-parse", "HEAD^{tree}")
            )
            with self.assertRaises(RuntimeError):
                clean_commit(root, "0" * 40)
            (root / "a").write_text("changed")
            with self.assertRaises(RuntimeError):
                clean_commit(root, commit)
            (root / "a").write_text("a")
            (root / "untracked.secret").write_text("inert")
            with self.assertRaises(RuntimeError):
                clean_commit(root, commit)


if __name__ == "__main__":
    unittest.main()
