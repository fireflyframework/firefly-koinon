#!/usr/bin/env python3
# Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
"""Exact-source hosted qualification and release inventory; no publication commands."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from package_release import WHEELS, clean_commit, pin, verify_versions

REQUIRED_WORKFLOWS = {"Product", "Headless SDKs", "Integrations", "Documentation"}
REQUIRED_GATES = {
    "assembly",
    "installed",
    "sdk_consumers",
    "documentation",
    "source_ci",
    "independent_delivery",
}

SCHEMA_URL = "https://raw.githubusercontent.com/CycloneDX/specification/1.5/schema/bom-1.5.schema.json"
SCHEMA_SHA256 = "067f7824b08653839ea050ae9e09ca48375eadc2652b0e2a299476e7db90335b"


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_identity(commit, version):
    require(
        bool(re.fullmatch(r"[0-9a-f]{40}", commit)),
        "Full lowercase source commit required",
    )
    require(
        bool(re.fullmatch(r"\d{2}\.\d{1,2}\.\d+", version)), "Final CalVer required"
    )


def validate_runs(runs, commit):
    for name in REQUIRED_WORKFLOWS:
        candidates = [
            row
            for row in runs
            if row["name"] == name
            and row["head_sha"] == commit
            and row["event"] in {"push", "workflow_dispatch"}
        ]
        require(candidates, f"Missing exact-source CI: {name}")
        current = max(
            candidates, key=lambda row: (row["run_number"], row["run_attempt"])
        )
        require(
            current["status"] == "completed" and current["conclusion"] == "success",
            f"Exact-source CI not green: {name}",
        )


def validate_gate_receipts(gates, commit):
    require(set(gates) == REQUIRED_GATES, "Incomplete or unknown release gates")
    for name, value in gates.items():
        require(
            value["source_commit"] == commit and value["status"] == "passed",
            f"Unqualified release gate: {name}",
        )


def validate_tool_commit(admitted, actual):
    require(
        admitted == actual and re.fullmatch(r"[0-9a-f]{40}", actual),
        "Tool checkout differs from admitted workflow commit",
    )


def validate_delivery_receipt(report, commit, inventory_sha256, checksum_sha256):
    require(
        report.get("source_commit") == commit
        and report.get("status") == "passed"
        and report.get("checksums") == "passed"
        and report.get("archive_safety") == "passed"
        and report.get("source_archive_exact_commit") is True
        and report.get("inventory_sha256") == inventory_sha256
        and report.get("checksum_file_sha256") == checksum_sha256,
        "Independent delivery verification is missing, failed or mismatched",
    )


def finalized_names(version):
    return {
        f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
        for name, _ in WHEELS.values()
    } | {
        f"koinon-{version}-source.tar.gz",
        f"koinon-management-{version}.tar.gz",
        f"koinon-elements-{version}.tar.gz",
        f"koinon-docs-{version}.tar.gz",
        f"koinon-sdk-{version}.jar",
        f"koinon-sdk-{version}.pom",
        f"fireflyframework-koinon-sdk-{version}.tgz",
        f"fireflyframework-koinon-angular-{version}.tgz",
        f"firefly-koinon-desktop-{version}.mcpb",
        f"firefly-koinon-skills-{version}.zip",
        "SHA256SUMS",
        "SBOM.cdx.json",
        "RELEASE-PROVENANCE.json",
    }


def validate_bom_references(bom):
    references = [component["bom-ref"] for component in bom["components"]]
    require(
        len(references) == len(set(references)), "Duplicate SBOM component reference"
    )


def validate_sbom(bom, schema_bytes):
    from jsonschema import Draft7Validator
    from referencing import Registry

    require(
        hashlib.sha256(schema_bytes).hexdigest() == SCHEMA_SHA256,
        "Official SBOM schema digest mismatch",
    )
    validate_bom_references(bom)
    schema = json.loads(schema_bytes)
    Draft7Validator.check_schema(schema)
    # No remote reference loader: future fields needing another schema fail closed.
    Draft7Validator(schema, registry=Registry()).validate(bom)


def write_checksums(assets):
    files = sorted(path for path in assets.iterdir() if path.name != "SHA256SUMS")
    require(
        files and all(path.is_file() and not path.is_symlink() for path in files),
        "Nonregular release asset",
    )
    (assets / "SHA256SUMS").write_text(
        "".join(f"{pin(path)['sha256']}  {path.name}\n" for path in files)
    )


def verify_checksums(assets):
    rows = [
        line.split("  ", 1) for line in (assets / "SHA256SUMS").read_text().splitlines()
    ]
    require(
        all(
            len(row) == 2
            and re.fullmatch(r"[0-9a-f]{64}", row[0])
            and "/" not in row[1]
            and "\\" not in row[1]
            for row in rows
        ),
        "Invalid checksum record",
    )
    names = [row[1] for row in rows]
    require(
        len(names) == len(set(names))
        and set(names) == {path.name for path in assets.iterdir()} - {"SHA256SUMS"},
        "Incomplete checksum inventory",
    )
    for hashed, name in rows:
        path = assets / name
        require(
            path.is_file() and not path.is_symlink() and pin(path)["sha256"] == hashed,
            "Asset checksum mismatch",
        )


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def command(args, cwd, log, *, env=None):
    require(shutil.disk_usage(log.parent).free >= 16 * 1024**3, "16 GiB disk floor")
    with log.open("w") as stream:
        result = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=1800,
            check=False,
        )
    require(result.returncode == 0, f"Qualification failed: {log.name}")
    return {
        "command": args,
        "exit_code": result.returncode,
        "log": log.name,
        **pin(log),
    }


def preflight(args):
    validate_identity(args.commit, args.version)
    clean_commit(args.source, args.commit)
    verify_versions(args.source, args.version)
    subprocess.run(
        [
            "git",
            "-C",
            str(args.source),
            "merge-base",
            "--is-ancestor",
            args.commit,
            "origin/main",
        ],
        check=True,
    )
    require(
        os.environ.get("GITHUB_REPOSITORY") == "fireflyframework/firefly-koinon",
        "Unexpected repository",
    )
    runs = json.loads(
        subprocess.check_output(
            [
                "gh",
                "api",
                f"repos/fireflyframework/firefly-koinon/actions/runs?head_sha={args.commit}&per_page=100",
            ],
            text=True,
        )
    )["workflow_runs"]
    validate_runs(runs, args.commit)
    write_json(
        args.receipt,
        {
            "source_commit": args.commit,
            "version": args.version,
            "status": "passed",
            "workflow_commit": os.environ.get("GITHUB_WORKFLOW_SHA"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "runs": [
                {
                    key: row[key]
                    for key in (
                        "name",
                        "head_sha",
                        "event",
                        "status",
                        "conclusion",
                        "run_number",
                        "run_attempt",
                        "html_url",
                    )
                }
                for row in runs
            ],
        },
    )


def consumers(args):
    delivery = args.delivery
    build = delivery / "build" / ("koinon-" + args.version)
    evidence = delivery / "evidence"
    assets = delivery / "assets"
    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "JAVA_HOME", "LANG", "LC_ALL", "TMPDIR"}
    }
    env.update({"CI": "true", "NG_CLI_ANALYTICS": "false", "PYTHONNOUSERSITE": "1"})
    records = []
    records.append(
        command(
            [
                "node",
                str(build / "tools/sdk/check_npm_consumer.mjs"),
                str(assets / f"fireflyframework-koinon-sdk-{args.version}.tgz"),
            ],
            build,
            evidence / "typescript-consumer.log",
            env=env,
        )
    )
    jar = f"koinon-sdk-{args.version}.jar"
    require(
        (assets / jar).read_bytes() == (build / "sdk/java/target" / jar).read_bytes(),
        "Java consumer must use release JAR",
    )
    records.append(
        command(
            [sys.executable, str(build / "tools/sdk/check_java_consumer.py")],
            build,
            evidence / "java-consumer.log",
            env=env,
        )
    )
    records.append(
        command(
            [
                "mvn",
                "--batch-mode",
                "--no-transfer-progress",
                "-f",
                str(build / "sdk/java/pom.xml"),
                "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree",
                "-DoutputType=json",
                "-DoutputFile=" + str(evidence / "java-dependencies.json"),
            ],
            build,
            evidence / "java-dependencies.log",
            env=env,
        )
    )
    frontend = build / "frontend"
    host = frontend / "smoke/angular-host"
    # Preserve the source fixture lock. Explicit archive install is the existing consumer workflow.
    records.append(
        command(
            [
                "npm",
                "install",
                "--ignore-scripts",
                "--no-save",
                "--no-package-lock",
                "--no-audit",
                "--no-fund",
                str(assets / f"fireflyframework-koinon-angular-{args.version}.tgz"),
                str(assets / f"fireflyframework-koinon-sdk-{args.version}.tgz"),
            ],
            host,
            evidence / "angular-consumer-install.log",
            env=env,
        )
    )
    from package_release import members

    angular = members(assets / f"fireflyframework-koinon-angular-{args.version}.tgz")
    installed = host / "node_modules/@fireflyframework/koinon-angular"
    for name, data in angular.items():
        require(
            (installed / name.removeprefix("package/")).read_bytes() == data,
            "Angular installed payload differs",
        )
    records.append(
        command(
            ["npm", "run", "build"], host, evidence / "angular-consumer.log", env=env
        )
    )
    records.append(
        command(
            ["npm", "test"],
            build / "integrations/mcp-desktop",
            evidence / "mcp-installed-tests.log",
            env=env,
        )
    )
    desktop = members(assets / f"firefly-koinon-desktop-{args.version}.mcpb")
    for name, data in desktop.items():
        require(
            (build / "integrations/mcp-desktop/build" / name).read_bytes() == data,
            "Tested desktop build differs from release MCPB",
        )
    write_json(
        evidence / "sdk-consumers.json",
        {"source_commit": args.commit, "status": "passed", "commands": records},
    )


def sbom(source, assets, version, evidence):
    """Declared lock inventory, with scopes explicit; not a claim all options ship at runtime."""
    components = []
    for path in sorted(assets.iterdir()):
        if path.name != "SHA256SUMS":
            components.append(
                {
                    "type": "file",
                    "name": path.name,
                    "version": version,
                    "bom-ref": "asset:" + path.name,
                    "hashes": [{"alg": "SHA-256", "content": pin(path)["sha256"]}],
                }
            )
    for relative in (
        "backend/uv.lock",
        "packages/canon/uv.lock",
        "packages/structured/uv.lock",
        "packages/storage/uv.lock",
    ):
        for package in tomllib.loads((source / relative).read_text())["package"]:
            components.append(
                {
                    "type": "library",
                    "name": package["name"],
                    "version": package["version"],
                    "bom-ref": relative
                    + ":"
                    + package["name"]
                    + "@"
                    + package["version"],
                    "properties": [
                        {
                            "name": "koinon:inventory",
                            "value": "Locked Python dependencies including optional and development packages",
                        },
                        {
                            "name": "koinon:source",
                            "value": json.dumps(package["source"], sort_keys=True),
                        },
                    ],
                }
            )
    for relative in (
        "sdk/typescript/package-lock.json",
        "frontend/package-lock.json",
        "integrations/mcp-desktop/package-lock.json",
    ):
        for location, package in json.loads((source / relative).read_text())[
            "packages"
        ].items():
            if not location or "version" not in package:
                continue
            components.append(
                {
                    "type": "library",
                    "name": package.get("name") or location.split("node_modules/")[-1],
                    "version": package["version"],
                    "bom-ref": relative + ":" + location,
                    "properties": [
                        {
                            "name": "koinon:inventory",
                            "value": "Locked npm dependencies including build and development packages",
                        },
                        {
                            "name": "koinon:integrity",
                            "value": package.get("integrity", "local path dependency"),
                        },
                    ],
                }
            )
    seen = set()

    def maven(node):
        identifier = ":".join(node[key] for key in ("groupId", "artifactId", "version"))
        if identifier not in seen:
            seen.add(identifier)
            components.append(
                {
                    "type": "library",
                    "group": node["groupId"],
                    "name": node["artifactId"],
                    "version": node["version"],
                    "bom-ref": "maven:" + identifier,
                    "properties": [
                        {
                            "name": "koinon:inventory",
                            "value": "Resolved Maven dependency tree including test scope",
                        },
                        {"name": "koinon:scope", "value": node.get("scope") or "root"},
                    ],
                }
            )
        for child in node.get("children", []):
            maven(child)

    maven(json.loads((evidence / "java-dependencies.json").read_text()))
    for package in json.loads((evidence / "installed-dependencies.json").read_text()):
        components.append(
            {
                "type": "library",
                "name": package["name"],
                "version": package["version"],
                "bom-ref": "installed-python:" + package["name"],
                "properties": [
                    {
                        "name": "koinon:inventory",
                        "value": "Observed installed qualification environment, including test dependencies",
                    }
                ],
            }
        )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "firefly koinon",
                "version": version,
            },
            "properties": [
                {
                    "name": "koinon:scope",
                    "value": "Release payload hashes and declared lock dependency inventory. Includes optional/development packages, not a runtime-only inventory.",
                }
            ],
        },
        "components": components,
    }


def finalize(args):
    validate_identity(args.commit, args.version)
    source_tree = clean_commit(args.source, args.commit)
    evidence = args.delivery / "evidence"
    assets = args.delivery / "assets"
    initial = json.loads((evidence / "inventory.json").read_text())
    require(
        initial["source_commit"] == args.commit
        and initial["version"] == args.version
        and initial["source_tree"] == source_tree,
        "Assembly identity mismatch",
    )
    require(
        set(initial["assets"]) == {p.name for p in assets.iterdir()} - {"SHA256SUMS"},
        "Unexpected pre-finalization inventory",
    )
    verify_checksums(assets)
    expected_initial = finalized_names(args.version) - {
        "SHA256SUMS",
        "SBOM.cdx.json",
        "RELEASE-PROVENANCE.json",
        f"koinon-sdk-{args.version}.pom",
    }
    require(
        set(initial["assets"]) == expected_initial, "Release payload allowlist differs"
    )
    for name, info in initial["assets"].items():
        require(pin(assets / name)["sha256"] == info["sha256"], "Assembly asset drift")
    source_ci = json.loads(args.receipt.read_text())
    validate_runs(source_ci["runs"], args.commit)
    independent = json.loads((evidence / "independent-delivery.json").read_text())
    validate_delivery_receipt(
        independent,
        args.commit,
        pin(evidence / "inventory.json")["sha256"],
        pin(assets / "SHA256SUMS")["sha256"],
    )
    gates = {
        "assembly": {
            "source_commit": args.commit,
            "status": "passed",
            "inventory_sha256": pin(evidence / "inventory.json")["sha256"],
        },
        "installed": json.loads((evidence / "installed/installed.json").read_text()),
        "sdk_consumers": json.loads((evidence / "sdk-consumers.json").read_text()),
        "documentation": json.loads((evidence / "documentation.json").read_text()),
        "source_ci": source_ci,
        "independent_delivery": independent,
    }
    validate_gate_receipts(gates, args.commit)
    tools_commit = subprocess.check_output(
        ["git", "-C", str(Path(__file__).parent), "rev-parse", "HEAD"], text=True
    ).strip()
    validate_tool_commit(source_ci["workflow_commit"], tools_commit)
    require(
        not (assets / "SBOM.cdx.json").exists(), "Never replace a finalized inventory"
    )
    shutil.copyfile(
        args.source / "sdk/java/pom.xml", assets / f"koinon-sdk-{args.version}.pom"
    )
    import urllib.request

    with urllib.request.urlopen(SCHEMA_URL, timeout=30) as response:
        schema_bytes = response.read(1_000_000)
    document = sbom(args.source, assets, args.version, evidence)
    validate_sbom(document, schema_bytes)
    (evidence / "bom-1.5.schema.json").write_bytes(schema_bytes)
    write_json(
        evidence / "sbom-validation.json",
        {
            "status": "passed",
            "schema_url": SCHEMA_URL,
            "schema_sha256": SCHEMA_SHA256,
            "unique_component_references": len(document["components"]),
        },
    )
    write_json(assets / "SBOM.cdx.json", document)
    subjects = [
        {"name": path.name, "digest": {"sha256": pin(path)["sha256"]}}
        for path in sorted(assets.iterdir())
        if path.name != "SHA256SUMS"
    ]
    write_json(
        assets / "RELEASE-PROVENANCE.json",
        {
            "_type": "https://in-toto.io/Statement/v1",
            "subject": subjects,
            "predicateType": "https://slsa.dev/provenance/v1",
            "predicate": {
                "buildDefinition": {
                    "buildType": "https://fireflyframework.org/koinon/hosted-qualification/v1",
                    "externalParameters": {
                        "source_commit": args.commit,
                        "version": args.version,
                    },
                    "resolvedDependencies": [
                        {
                            "uri": "git+https://github.com/fireflyframework/firefly-koinon",
                            "digest": {"gitCommit": args.commit},
                        },
                        {
                            "uri": "git+https://github.com/fireflyframework/firefly-koinon/tools/release",
                            "digest": {"gitCommit": tools_commit},
                        },
                    ],
                    "internalParameters": {
                        "qualification": "Unsigned provenance. Source CI and named installed regression gates passed. No publication or external-client acceptance."
                    },
                },
                "runDetails": {
                    "builder": {
                        "id": "https://github.com/fireflyframework/firefly-koinon/actions/workflows/release-assembly.yml"
                    },
                    "metadata": {"invocationId": str(source_ci["run_id"])},
                },
            },
        },
    )
    write_checksums(assets)
    verify_checksums(assets)
    require(
        {path.name for path in assets.iterdir()} == finalized_names(args.version),
        "Final release must contain exactly the eighteen named assets",
    )
    write_json(
        evidence / "qualification.json",
        {
            "source_commit": args.commit,
            "tool_commit": tools_commit,
            "version": args.version,
            "status": "passed",
            "gates": gates,
            "assets": {p.name: pin(p) for p in sorted(assets.iterdir())},
            "publication": "not performed",
            "live_acceptance": "not performed",
        },
    )
    print(
        json.dumps(
            {
                "source_commit": args.commit,
                "assets": len(list(assets.iterdir())),
                "qualification": "passed",
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("preflight", "consumers", "finalize"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--delivery", type=Path)
    args = parser.parse_args()
    validate_identity(args.commit, args.version)
    {"preflight": preflight, "consumers": consumers, "finalize": finalize}[
        args.operation
    ](args)


if __name__ == "__main__":
    main()
