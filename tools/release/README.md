<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Hosted release assembly and qualification

This operator assembles release candidates and retains their evidence. It never creates a tag, publishes a release, uploads packages to a registry, changes a product service or deletes retained data. Publication and external-client acceptance remain separate gates.

The product source commit and the workflow-tools commit are different inputs. A new workflow can qualify the frozen `26.11.11` product commit `8baa0b2172de7d266b0b0bb9d60ee0466d1c2aa3` without adding release tooling to that product archive. Both revisions are recorded in provenance. Do not substitute the current main commit merely because it contains newer tooling.

## Before dispatch

1. Review and merge the operator changes. The workflow must be available in the repository; pull requests execute only its inert operator tests.
2. Choose a full 40-character product commit already merged into main. Every product/SDK/desktop manifest must contain the requested final CalVer. Its exact-commit Product, Headless SDKs, Integrations and Documentation workflows must have completed successfully. A green run for a different commit is insufficient. The latest matching workflow attempt is authoritative.
3. Confirm the reviewed tools revision and available hosted-runner capacity. The minimum free-disk floor is **16 GiB**, checked before assembly commands and qualification stages. The workflow does not remove preinstalled runner tools or lower this floor to make a build fit. An insufficient runner fails explicitly.
4. Dispatch the workflow from the reviewed branch, then record the resulting workflow SHA and run ID:

```sh
gh workflow run release-assembly.yml \
  --repo fireflyframework/firefly-koinon --ref main \
  -f source_commit=8baa0b2172de7d266b0b0bb9d60ee0466d1c2aa3 \
  -f version=26.11.11
```

The example selects a product revision; it does not assert that its hosted qualification or publication has completed. Check the current run before making that claim. Source and operator checkout credentials are not persisted. The only token-bearing step queries source CI with read-only permissions. Build and installed-test subprocesses receive restricted environments without provider credentials or source `PYTHONPATH`.

## Gates and retained evidence

| Gate | What it proves |
| --- | --- |
| Source admission | Exact clean commit, main ancestry, consistent final versions and successful exact-source CI. |
| Asset assembly | Git-archive source snapshot, source unchanged by builds, legal notices, archive safety, wheel payload/RECORD checks, Java 21 bytecode and explicit payload allowlist. |
| Independent delivery check | Separate reread of archive contents, source identity and all original checksums; finalization binds the report to the original inventory and checksum-file hashes. |
| Installed runtime | Five exact release wheels installed without dependency resolution against the exported locked backend dependencies. Installed namespaces and wheel RECORD entries match bytes, import origins stay inside the isolated environment, and pinned tests run outside production source. |
| Named installed lanes | Real Office parsers, intake/processing, policy snapshots, ordinary folders, real PostgreSQL/pgvector installation and workers, and Python SDK tests. The selected PostgreSQL lane must execute every case without skips. Full source CI is a separate prerequisite, not relabeled as installed-wheel testing. |
| External SDK consumers | The released TypeScript archive, Java JAR and Angular archive compile/run through existing consumer fixtures. Angular installed payload bytes are compared with the archive. MCP tests execute the built bridge, which is compared with the released MCPB. These are controlled tests, not actual Claude-client acceptance. |
| Documentation | Strict packaged MkDocs build and the repository's rendered-site link, branding and font checks. |
| Final inventory | Exactly 18 named files, complete checksums, unique SBOM references and validation against the SHA-256-pinned official CycloneDX 1.5 schema. |

The five-wheel environment includes the four runtime distributions and the Python SDK. Its dependency export retains the backend lock's exact PyFly Git revision and registry hashes. It excludes editable local projects; release wheels are installed with `--no-deps`. The package manager's dependency check must pass. No production package source is copied into the test snapshot. Test files, migration/operator fixtures and SDK contract fixtures come from exact Git blobs, with hashes retained.

The runner owns a temporary PostgreSQL service exposed only on loopback port `5439`. Only the named PostgreSQL lane receives its test URLs. Tests use the existing owned fixture lifecycle; no Azure, external model, mail or user database credentials are supplied. Test subprocesses have per-test and per-lane time limits. The workflow has a 120-minute overall limit. Failures and skips are recorded, not converted into acceptance.

## Asset and dependency boundaries

`package_release.py` is the reviewed local control packager, moved into the repository with its safety tests. Its default remains offline. Fresh hosted runners explicitly enable npm lockfile downloads and uv/Maven build dependencies. Dependency installation occurs in the new archived build snapshot. A failed run retains diagnostics and is never reused as a completed candidate.

The initial packager produces 14 payloads. Finalization adds the Java POM, `SBOM.cdx.json` and `RELEASE-PROVENANCE.json`, then rewrites `SHA256SUMS` to cover all 17 payload files. The final receipt records all 18 files, including the checksum file itself. Only a completely successful run uploads the qualified candidate artifact. Failure uploads contain diagnostics, not advertised release payloads.

The SBOM distinguishes declared Python/npm locks, resolved Maven dependencies and the observed installed qualification environment. Optional, test and build dependencies are labeled; this is not presented as a runtime-only dependency graph. The official schema is downloaded from its versioned URL, checked against a fixed SHA-256 and retained in evidence. Schema references are not fetched dynamically. New fields requiring additional schemas must be explicitly reviewed.

Provenance is an **unsigned** in-toto/SLSA-shaped statement, not a signed GitHub attestation or a claim of a SLSA assurance level. It identifies the source and tooling commits, workflow run and payload hashes. Archive timestamps and Java output timestamps use the source commit epoch; observed package hashes remain authoritative. A successful build does not by itself prove bit-for-bit reproducibility across different toolchains.

The qualified artifact retains assets, command logs, dependency observations, test-input hashes, JUnit reports and qualification receipts for 14 days. Build snapshots, virtual environments and dependency directories are excluded. Download the qualified artifact and independently verify its complete inventory before any later publication. Publish those exact bytes; rebuilding later produces a different candidate requiring qualification.

## Local operator checks

These tests use small inert fixtures and do not install dependencies, assemble packages, open product services or publish:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/release \
  python3 -m unittest discover -s tools/release/tests -v
actionlint .github/workflows/release-assembly.yml
```

Run the repository Python linter against `tools/release` as well. The hosted assembly environment additionally installs `jsonschema==4.26.0` for official SBOM validation. The real hosted job must complete before claiming installed-artifact or end-to-end release qualification; passing operator tests establishes only the operator's tested invariants.
