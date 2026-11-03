#!/usr/bin/env python3
# Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
"""Qualify release wheels outside production source, with exact pinned test inputs."""

import argparse
import base64
import csv
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path

DISTRIBUTIONS = {
    "firefly-koinon": "koinon",
    "firefly-koinon-documents": "flycanon",
    "firefly-koinon-structured": "flyquery",
    "firefly-koinon-storage": "koinon_storage",
    "firefly-koinon-sdk": "koinon_sdk",
}
LANES = {
    "runtime": [
        "backend/tests/knowledge/bulk/test_real_office_parsers.py",
        "backend/tests/knowledge/bulk/test_bulk_contract.py",
        "backend/tests/knowledge/bulk/test_bulk_file_transport.py",
        "backend/tests/knowledge/bulk/test_bulk_native.py",
        "backend/tests/knowledge/bulk/test_bulk_processing_recovery.py",
        "backend/tests/knowledge/bulk/test_upload_formats.py",
        "backend/tests/assistants/test_knowledge_policy.py",
        "backend/tests/catalog/test_retired_system_folders.py",
    ],
    "postgres": [
        "backend/tests/catalog/test_retired_system_folders.py",
        "backend/tests/installation/test_installation_native_postgres.py",
        "backend/tests/knowledge/bulk/test_bulk_pinned_postgres.py",
        "backend/tests/knowledge/bulk/test_parallel_workers_postgres.py",
        "backend/tests/knowledge/bulk/test_bulk_processing_recovery_postgres.py",
        "backend/tests/knowledge/bulk/test_document_lineage_roundtrip_postgres.py",
    ],
    "sdk": ["sdk/python/tests"],
}
PG_KEYS = (
    "KOINON_INSTALLATION_ANN_TEST_PG_URL",
    "KOINON_TEST_BULK_POSTGRES_URL",
    "KOINON_MEMORY_AUTHORITY_TEST_PG_URL",
)
PG_URL = "postgresql://postgres@127.0.0.1:5439/postgres"


def require(value, message):
    if not value:
        raise ValueError(message)


def verify_namespace(wheel, site, namespace):
    """Compare every installed namespace byte, reject stale files and check wheel RECORD."""
    with zipfile.ZipFile(wheel) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        require(len(names) == len(set(names)), "Duplicate wheel member")
        payload = {name: archive.read(name) for name in names}
    expected = {
        name: data for name, data in payload.items() if name.startswith(namespace + "/")
    }
    require(expected, "Missing package namespace")
    actual = {
        p.relative_to(site).as_posix(): p.read_bytes()
        for p in (site / namespace).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }
    require(actual == expected, "Installed namespace differs from release wheel")
    record = next(name for name in payload if name.endswith(".dist-info/RECORD"))
    rows = list(csv.reader(io.StringIO(payload[record].decode())))
    require({row[0] for row in rows} == set(payload), "Incomplete wheel RECORD")
    for name, encoded, size in rows:
        if encoded:
            data = payload[name]
            algorithm, value = encoded.split("=", 1)
            require(
                algorithm == "sha256"
                and base64.urlsafe_b64encode(hashlib.sha256(data).digest())
                .rstrip(b"=")
                .decode()
                == value
                and len(data) == int(size),
                "Invalid wheel RECORD",
            )
            target = (site / name).resolve()
            require(
                target.is_relative_to(site.resolve()) and target.read_bytes() == data,
                "Installed payload differs from wheel RECORD",
            )
    return len(expected)


def snapshot(source, destination, commit):
    require(not destination.exists(), "Test snapshot must be new")
    files = (
        subprocess.check_output(
            ["git", "-C", str(source), "ls-tree", "-r", "--name-only", "-z", commit]
        )
        .decode()
        .split("\0")
    )
    prefixes = (
        "backend/tests/",
        "deploy/",
        "packages/canon/migrations/",
        "packages/structured/migrations/",
        "packages/storage/tests/",
        "sdk/python/tests/",
        "sdk/contract/",
    )
    exact = {
        "backend/pyproject.toml",
        "sdk/python/pyproject.toml",
        "frontend/e2e/office-format-capabilities.json",
    }
    hashes = {}
    for name in files:
        if name and (name.startswith(prefixes) or name in exact):
            data = subprocess.check_output(
                ["git", "-C", str(source), "show", commit + ":" + name]
            )
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            hashes[name] = hashlib.sha256(data).hexdigest()
    require(
        hashes and not list(destination.glob("**/src/koinon")),
        "Production source in test snapshot",
    )
    return hashes


def isolated(args):
    require(
        sys.flags.isolated and Path(sys.prefix).resolve() == args.environment.resolve(),
        "Use the isolated wheel environment",
    )
    site = Path(sysconfig.get_paths()["purelib"])
    require(
        site.is_relative_to(args.environment.resolve()), "Unexpected installation path"
    )
    report = {}
    for distribution, namespace in DISTRIBUTIONS.items():
        require(
            importlib.metadata.version(distribution) == args.version,
            "Wrong installed version",
        )
        wheel = (
            args.assets
            / f"{distribution.replace('-', '_')}-{args.version}-py3-none-any.whl"
        )
        count = verify_namespace(wheel, site, namespace)
        module = importlib.import_module(namespace)
        require(
            Path(module.__file__).resolve().is_relative_to(site / namespace),
            "Production import escaped installed namespace",
        )
        report[distribution] = {
            "version": args.version,
            "files": count,
            "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        }
    manifest = json.loads((args.output / "test-inputs.json").read_text())
    require(
        all(
            hashlib.sha256((args.output / "tests" / name).read_bytes()).hexdigest()
            == value
            for name, value in manifest["files"].items()
        ),
        "Pinned test inputs changed",
    )
    for key in list(os.environ):
        if key not in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}:
            os.environ.pop(key, None)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    if args.lane == "postgres":
        for key in PG_KEYS:
            os.environ[key] = PG_URL
    # No product source is copied or added to sys.path. Only the test snapshot is importable.
    tree = args.output / "tests"
    os.chdir(tree / "backend")
    sys.path.insert(0, str(tree / "backend"))
    import pytest

    xml = args.output / f"{args.lane}.xml"
    result = pytest.main(
        [
            "-p",
            "pytest_asyncio.plugin",
            "-p",
            "pytest_timeout",
            "-p",
            "no:cacheprovider",
            "--timeout=90",
            "-o",
            "pythonpath=",
            "-o",
            "asyncio_mode=auto",
            "--basetemp",
            str(args.output / ("scratch-" + args.lane)),
            "--junitxml",
            str(xml),
            "-q",
            *(str(tree / path) for path in LANES[args.lane]),
        ]
    )
    import xml.etree.ElementTree as ET

    suites = list(ET.parse(xml).getroot().iter("testsuite"))
    totals = {
        key: sum(int(suite.get(key, "0")) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    require(
        result == 0
        and totals["tests"] > totals["skipped"]
        and not totals["failures"]
        and not totals["errors"],
        "Installed lane failed or executed no tests",
    )
    if args.lane == "postgres":
        require(
            totals["skipped"] == 0,
            "Postgres qualification must execute every selected case",
        )
    (args.output / f"{args.lane}.json").write_text(
        json.dumps(
            {
                "source_commit": args.commit,
                "status": "passed",
                "lane": args.lane,
                "counts": totals,
                "distributions": report,
                "production_source_absent": True,
            },
            indent=2,
        )
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--lane", choices=LANES)
    args = parser.parse_args()
    if args.lane:
        isolated(args)
        return
    require(not args.output.exists(), "Qualification output must be new")
    require(
        shutil.disk_usage(args.output.parent).free >= 16 * 1024**3, "16 GiB disk floor"
    )
    args.output.mkdir()
    hashes = snapshot(args.source, args.output / "tests", args.commit)
    (args.output / "test-inputs.json").write_text(
        json.dumps({"source_commit": args.commit, "files": hashes}, indent=2) + "\n"
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}
    }
    for lane in LANES:
        require(
            shutil.disk_usage(args.output).free >= 16 * 1024**3, "16 GiB disk floor"
        )
        command = [
            str(args.environment / "bin/python"),
            "-I",
            "-B",
            str(Path(__file__).resolve()),
            "--source",
            str(args.source),
            "--commit",
            args.commit,
            "--version",
            args.version,
            "--assets",
            str(args.assets),
            "--output",
            str(args.output),
            "--environment",
            str(args.environment),
            "--lane",
            lane,
        ]
        with (args.output / f"{lane}.log").open("w") as log:
            subprocess.run(
                command,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=1200,
            )
    (args.output / "installed.json").write_text(
        json.dumps(
            {
                "source_commit": args.commit,
                "status": "passed",
                "lanes": list(LANES),
                "scope": "Exact installed wheels and named regression lanes; full source CI is a separate prerequisite.",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
