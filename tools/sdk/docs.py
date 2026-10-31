# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Render the public SDK reference from the checked canonical operation manifest."""

import argparse
import json
from pathlib import Path

from reference import SchemaReference, render_api
from reference.api import operation_link
from reference.retained import compatibility_link
from reference.retained_source import enrich_retained

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
            f"This canonical contract contains {contract['canonical_operation_count']} operations. "
            "Resource operations require the caller's current membership, permissions and resource scope. "
            "Bearer credentials also enforce their saved expiry and bounds. "
            "Authorized-application management requires a verified interactive user session; "
            "personal tokens and application credentials cannot manage authorizations. "
            "[Read about authorized applications](../guides/authorized-applications.md)."
        ),
        "",
        (
            "[Download the operation manifest](sdk-contract.json) and "
            "[complete wire schemas](sdk-schemas.json). "
            "The maintained generator checks source mappings and schemas without starting the backend."
        ),
        "",
        "Browse [API areas](api/index.md), [wire models](models/index.md) and the [SDK runtime reference](sdk-runtime.md) for parameters, constraints and connection ownership.",
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
            + f"[`{cells[0]}`]({operation_link(operation)}) | "
            + " | ".join("`" + value.replace("|", "\\|") + "`" for value in cells[1:])
            + " |"
        )
    qualified = contract.get("qualified_compatibility_operations", [])
    if qualified:
        rows.extend(
            [
                "",
                "## Qualified retained glossary API",
                "",
                "These operations use the original structured service behind resource admission. They are separate from the canonical count and require the structured module and its configured native datasource. Pass the canonical tenant and workspace. Updates and deletion require the exact returned `updated_at` string; preserve microseconds and the offset instead of parsing through a date formatter.",
                "",
                "| API operation | Python client | TypeScript client | Java client |",
                "| --- | --- | --- | --- |",
            ]
        )
        for operation in qualified:
            py = operation["sdk_python"] + (
                "(agent=True)" if operation["sdk_python_agent"] else ""
            )
            cells = [
                operation["method"] + " " + operation["path"],
                py,
                operation["sdk_typescript"],
                operation["sdk_java"],
            ]
            rows.append(
                "| "
                + f"[`{cells[0]}`]({compatibility_link(operation)}) | "
                + " | ".join("`" + value + "`" for value in cells[1:])
                + " |"
            )
        rows.extend(
            [
                "",
                "Glossary list totals can be unknown. Honor returned `limit`, `offset` and `has_more`; do not invent a total or slice another page in the client.",
            ]
        )
    rows.extend(
        [
            "",
            "## Request behavior",
            "",
            (
                "New conversation export and share reviews save a nullable typed `identity` with product/assistant names, "
                "organization branding revision/origin and configuration digest. The review revision binds that identity; "
                "later organization changes do not rewrite saved reviews, exports or shared conversations. "
                "Historical null means not recorded. JSON exports retain machine roles and separate display names. "
                "See the [three-language export and sharing workflows](../guides/exports-sharing.md) for "
                "preview, explicit confirmation, authenticated download and recipient reads."
            ),
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


def build_reference(
    contract: dict, schemas: dict, *, source_root: Path = ROOT
) -> dict[str, str]:
    contract = {
        **contract,
        "qualified_compatibility_operations": enrich_retained(
            contract.get("qualified_compatibility_operations", []), source_root
        ),
    }
    reference = SchemaReference(schemas)
    return {
        "sdk-api.md": render(contract),
        **render_api(contract, reference),
        **reference.render_all(),
    }


def write_reference(target: Path, outputs: dict[str, str], *, check: bool) -> None:
    for relative, content in outputs.items():
        path = target / relative
        if check:
            if not path.is_file() or path.read_text() != content:
                raise ValueError(f"SDK reference drift: {relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository or isolated input/output root",
    )
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    source = root / "sdk/contract/operations.json"
    schemas = root / "sdk/contract/schemas.json"
    outputs = {
        **build_reference(
            json.loads(source.read_text()),
            json.loads(schemas.read_text()),
            source_root=root,
        ),
        "sdk-contract.json": source.read_text(),
        "sdk-schemas.json": schemas.read_text(),
    }
    try:
        write_reference(root / "docs/reference", outputs, check=arguments.check)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print("Verified SDK reference" if arguments.check else "Updated SDK reference")


if __name__ == "__main__":
    main()
