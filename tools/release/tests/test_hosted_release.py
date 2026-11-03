# Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
"""Inert release gates; never build, install, publish or contact a service."""

import base64
import hashlib
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from hosted_release import (
    finalized_names,
    validate_bom_references,
    validate_delivery_receipt,
    validate_gate_receipts,
    validate_identity,
    validate_runs,
    validate_tool_commit,
    verify_checksums,
    write_checksums,
)
from qualify_installed import snapshot, verify_namespace


class HostedGatesTests(unittest.TestCase):
    def test_workflow_has_no_publish_permission_or_untrusted_shell_interpolation(self):
        root = Path(__file__).resolve().parents[3]
        workflow = (root / ".github/workflows/release-assembly.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("gh release", workflow)
        self.assertNotIn("git push", workflow)
        self.assertIn(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", workflow
        )
        self.assertIn("if: success()", workflow)
        self.assertIn(
            "python operator/tools/release/hosted_release.py finalize", workflow
        )

    def test_only_full_commit_and_final_version_are_accepted(self):
        validate_identity("a" * 40, "26.11.11")
        for commit, version in [
            ("main", "26.11.11"),
            ("a" * 40, "26.11.11-alpha"),
            ("a;echo x", "26.11.11"),
        ]:
            with self.assertRaises(ValueError):
                validate_identity(commit, version)

    def test_every_exact_source_workflow_must_be_successful(self):
        rows = [
            {
                "name": name,
                "head_sha": "a" * 40,
                "event": "push",
                "status": "completed",
                "conclusion": "success",
                "run_attempt": 1,
                "run_number": 1,
            }
            for name in ("Product", "Headless SDKs", "Integrations", "Documentation")
        ]
        validate_runs(rows, "a" * 40)
        for bad in (
            [*rows[:-1]],
            [*rows, {**rows[0], "run_number": 2, "conclusion": "failure"}],
            [{**row, "head_sha": "b" * 40} for row in rows],
        ):
            with self.assertRaises(ValueError):
                validate_runs(bad, "a" * 40)

    def test_receipts_cannot_substitute_other_source_or_missing_gate(self):
        gates = {
            name: {"source_commit": "a" * 40, "status": "passed"}
            for name in (
                "assembly",
                "installed",
                "sdk_consumers",
                "documentation",
                "source_ci",
                "independent_delivery",
            )
        }
        validate_gate_receipts(gates, "a" * 40)
        for bad in (
            {**gates, "installed": {"source_commit": "b" * 40, "status": "passed"}},
            {key: value for key, value in gates.items() if key != "installed"},
        ):
            with self.assertRaises(ValueError):
                validate_gate_receipts(bad, "a" * 40)

    def test_tool_commit_cannot_drift_from_workflow_admission(self):
        validate_tool_commit("a" * 40, "a" * 40)
        with self.assertRaises(ValueError):
            validate_tool_commit("a" * 40, "b" * 40)

    def test_independent_delivery_must_pass_and_match_original_hashes(self):
        report = {
            "source_commit": "a" * 40,
            "status": "passed",
            "checksums": "passed",
            "archive_safety": "passed",
            "source_archive_exact_commit": True,
            "inventory_sha256": "b" * 64,
            "checksum_file_sha256": "c" * 64,
        }
        validate_delivery_receipt(report, "a" * 40, "b" * 64, "c" * 64)
        for bad in (
            {**report, "checksums": "failed"},
            {**report, "inventory_sha256": "d" * 64},
            {**report, "source_commit": "e" * 40},
        ):
            with self.assertRaises(ValueError):
                validate_delivery_receipt(bad, "a" * 40, "b" * 64, "c" * 64)

    def test_final_inventory_is_exactly_eighteen_named_files(self):
        names = finalized_names("26.11.11")
        self.assertEqual(len(names), 18)
        self.assertIn("koinon-sdk-26.11.11.pom", names)
        self.assertIn("RELEASE-PROVENANCE.json", names)
        self.assertNotIn("unexpected.whl", names)

    def test_sbom_rejects_duplicate_component_identity(self):
        validate_bom_references({"components": [{"bom-ref": "a"}, {"bom-ref": "b"}]})
        with self.assertRaises(ValueError):
            validate_bom_references(
                {"components": [{"bom-ref": "a"}, {"bom-ref": "a"}]}
            )

    def test_test_snapshot_uses_commit_bytes_and_excludes_product_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()

            def git(*arguments):
                return subprocess.check_output(
                    ["git", "-C", str(source), *arguments], text=True
                ).strip()

            git("init", "--quiet")
            for name in (
                "backend/tests/test_sample.py",
                "backend/src/koinon/private.py",
                "deploy/migrations/sample.py",
            ):
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("original")
            git("add", ".")
            git(
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "fixture",
            )
            commit = git("rev-parse", "HEAD")
            (source / "backend/tests/test_sample.py").write_text("changed after commit")
            manifest = snapshot(source, root / "tests", commit)
            self.assertEqual(
                (root / "tests/backend/tests/test_sample.py").read_text(), "original"
            )
            self.assertEqual(
                set(manifest),
                {"backend/tests/test_sample.py", "deploy/migrations/sample.py"},
            )
            self.assertFalse((root / "tests/backend/src").exists())
            with self.assertRaises(ValueError):
                snapshot(source, root / "tests", commit)

    def test_full_inventory_detects_tamper_and_extra_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            assets = Path(temporary)
            (assets / "payload.whl").write_bytes(b"payload")
            (assets / "SBOM.cdx.json").write_text("{}")
            write_checksums(assets)
            verify_checksums(assets)
            (assets / "payload.whl").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                verify_checksums(assets)
            (assets / "payload.whl").write_bytes(b"payload")
            (assets / "unexpected.secret").write_text("inert")
            with self.assertRaises(ValueError):
                verify_checksums(assets)

    def test_installed_namespace_is_exact_and_not_editable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site = root / "site"
            (site / "sample").mkdir(parents=True)
            payload = b"value = 1\n"
            (site / "sample/__init__.py").write_bytes(payload)
            hashed = (
                base64.urlsafe_b64encode(hashlib.sha256(payload).digest())
                .rstrip(b"=")
                .decode()
            )
            record = f"sample/__init__.py,sha256={hashed},{len(payload)}\nsample-1.dist-info/RECORD,,\n"
            wheel = root / "sample.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("sample/__init__.py", payload)
                archive.writestr("sample-1.dist-info/RECORD", record)
            self.assertEqual(verify_namespace(wheel, site, "sample"), 1)
            (site / "sample/stale.py").write_text("stale")
            with self.assertRaises(ValueError):
                verify_namespace(wheel, site, "sample")


if __name__ == "__main__":
    unittest.main()
