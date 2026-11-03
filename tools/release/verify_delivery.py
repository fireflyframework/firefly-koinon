#!/usr/bin/env python3
# Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
"""Read-only independent checksum/archive/source reconciliation for staged assets."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from package_release import WHEELS, clean_commit, members, pin, require, verify_wheel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    args = parser.parse_args()
    delivery = args.delivery.resolve()
    receipt = json.loads((delivery / "evidence/inventory.json").read_text())
    checkout = args.checkout.resolve()
    commit, version = receipt["source_commit"], receipt["version"]
    require(
        clean_commit(checkout, commit) == receipt["source_tree"], "Source tree changed"
    )
    assets = delivery / "assets"
    require(
        {p.name for p in assets.iterdir()} == set(receipt["assets"]) | {"SHA256SUMS"},
        "Asset inventory mismatch",
    )
    require(
        pin(assets / "SHA256SUMS") == receipt["SHA256SUMS"], "Checksum file mismatch"
    )
    checksums = {}
    for line in (assets / "SHA256SUMS").read_text().splitlines():
        checksum, name = line.split("  ", 1)
        require(
            name not in checksums and "/" not in name and "alpha" not in name.lower(),
            "Invalid checksum entry",
        )
        checksums[name] = checksum
    require(set(checksums) == set(receipt["assets"]), "Checksum coverage mismatch")
    for name, expected in receipt["assets"].items():
        actual = pin(assets / name)
        require(
            actual["sha256"] == checksums[name] == expected["sha256"]
            and actual["bytes"] == expected["bytes"],
            name,
        )
        require(
            len(members(assets / name)) == expected["archive_files"],
            f"Archive count {name}",
        )
    with tempfile.TemporaryDirectory(prefix="koinon-source-audit-") as temporary:
        archive = Path(temporary) / "expected.tar"
        with archive.open("wb") as stream:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(checkout),
                    "archive",
                    "--format=tar",
                    f"--prefix=koinon-{version}/",
                    commit,
                ],
                stdout=stream,
                check=True,
            )
        expected = members(archive)
        require(
            expected == members(assets / f"koinon-{version}-source.tar.gz"),
            "Source archive differs from exact git commit",
        )
    wheels = {}
    for directory, (name, _) in WHEELS.items():
        wheel = assets / f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
        wheels[wheel.name] = verify_wheel(wheel, checkout, directory, version)
    for app in ("management", "elements"):
        payload = members(assets / f"koinon-{app}-{version}.tar.gz")
        for name in (
            "index.html",
            "LICENSE",
            "NOTICE",
            "3rdpartylicenses.txt",
            "assets/brand/NOTICE.md",
            "assets/brand/OFL.txt",
            "assets/brand/fonts/Inter-OFL.txt",
        ):
            require(payload.get(name), f"Missing {app} legal/runtime file {name}")
        for name in ("LICENSE", "NOTICE"):
            require(
                payload[name] == (checkout / name).read_bytes(),
                f"Legal mismatch {app}:{name}",
            )
    print(
        json.dumps(
            {
                "source_commit": commit,
                "status": "passed",
                "inventory_sha256": pin(delivery / "evidence/inventory.json")["sha256"],
                "checksum_file_sha256": pin(assets / "SHA256SUMS")["sha256"],
                "source_tree": receipt["source_tree"],
                "version": version,
                "assets": len(receipt["assets"]),
                "checksums": "passed",
                "archive_safety": "passed",
                "source_archive_exact_commit": True,
                "wheel_payload_and_RECORD": wheels,
                "static_distribution_legal": "passed",
                "source_checkout_clean": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
