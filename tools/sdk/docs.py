# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Render the public SDK reference from the checked canonical operation manifest."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def render(contract: dict) -> str:
    rows = [
        "# API and SDK reference",
        "",
        (
            "Python, Java and TypeScript expose the same canonical headless API. "
            "The table records concrete SDK methods; it does not count browser-only authentication "
            "or retained domain routes outside this contract."
        ),
        "",
        (
            f"This development contract contains {contract['canonical_operation_count']} operations. "
            "Resource operations require the caller's current membership, permissions and resource scope. "
            "Bearer credentials also enforce their saved expiry and bounds. "
            "Authorized-application management requires a verified interactive user session; "
            "personal tokens and application credentials cannot manage authorizations. "
            "[Read about authorized applications](../guides/authorized-applications.md)."
        ),
        "",
        (
            "[Download the operation manifest](sdk-contract.json). "
            "The maintained generator checks source mappings and schemas without starting the backend."
        ),
        "",
        "| API operation | Python client | TypeScript client | Java client | Response |",
        "| --- | --- | --- | --- | --- |",
    ]
    for operation in contract["operations"]:
        cells = [
            operation["method"] + " " + operation["path"],
            operation["sdk_python"],
            operation["sdk_typescript"],
            operation["sdk_java"],
            operation["response_schema"],
        ]
        if any(value is None for value in cells):
            raise ValueError(
                "Public reference requires complete, verified SDK mappings"
            )
        rows.append(
            "| "
            + " | ".join("`" + value.replace("|", "\\|") + "`" for value in cells)
            + " |"
        )
    qualified = contract.get("qualified_compatibility_operations", [])
    if qualified:
        rows.extend(["", "## Qualified retained glossary API", "", "These operations use the original structured service behind resource admission. They are separate from the canonical count and require the structured module and its configured native datasource. Pass the canonical tenant and workspace. Updates and deletion require the exact returned `updated_at` string; preserve microseconds and the offset instead of parsing through a date formatter.", "", "| API operation | Python client | TypeScript client | Java client |", "| --- | --- | --- | --- |"])
        for operation in qualified:
            py = operation["sdk_python"] + ("(agent=True)" if operation["sdk_python_agent"] else "")
            cells = [operation["method"] + " " + operation["path"], py, operation["sdk_typescript"], operation["sdk_java"]]
            rows.append("| " + " | ".join("`" + value + "`" for value in cells) + " |")
        rows.extend(["", "Glossary list totals can be unknown. Honor returned `limit`, `offset` and `has_more`; do not invent a total or slice another page in the client."])
    rows.extend(
        [
            "",
            "## Request behavior",
            "",
            (
                "Dataset file append requires a stable Idempotency-Key, accepts one bounded multipart file and returns its canonical file-version "
                "and new table identities. Existing snapshots are retained. Native sections commit independently; "
                "pending or failed intake blocks dataset query/schema until reconciliation. Exact key/payload replays recheck permissions and return the stored completed receipt without native work. "
                "There is no automatic retry, bulk/async intake or public recovery helper. PostgreSQL concurrency and configured-provider "
                "acceptance remain separate qualification gates."
            ),
            "",
            (
                "Use endpoint-declared filters. Totals and page metadata are present only when the server "
                "supplies them. Cursor values are opaque. Closing a stream releases the connection; "
                "cancel the durable run separately to stop processing."
            ),
            "",
            (
                "Content writes require the caller's current revision. Optional avatar conditionals use "
                "`If-None-Match`; stream resumption uses `Last-Event-ID`. These are separate from the "
                "`If-Match` precondition on content replacement and reingestion."
            ),
            "",
            (
                "Known fields have named DTOs and typed values. Opaque business JSON preserves null, "
                "booleans, numbers and exact strings recursively. A successful SDK build or contract test "
                "does not qualify a configured model provider or a production deployment."
            ),
            "",
            (
                "Copyright 2026 Firefly Software Foundation "
                "SPDX-License-Identifier: Apache-2.0"
            ),
            "",
        ]
    )
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    source = ROOT / "sdk/contract/operations.json"
    targets = {
        ROOT / "docs/reference/sdk-api.md": render(json.loads(source.read_text())),
        ROOT / "docs/reference/sdk-contract.json": source.read_text(),
    }
    for path, content in targets.items():
        if arguments.check:
            if not path.exists() or path.read_text() != content:
                raise SystemExit(f"SDK reference drift: {path.relative_to(ROOT)}")
        else:
            path.write_text(content)
    print("Verified SDK reference" if arguments.check else "Updated SDK reference")


if __name__ == "__main__":
    main()
