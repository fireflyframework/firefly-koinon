# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retained operation metadata, deliberately separate from canonical coverage."""

from typing import Any

from .schema import LICENSE, SchemaReference, code, literal, slug


def compatibility_link(operation: dict[str, Any], prefix: str = "api/") -> str:
    return f"{prefix}retained-glossary.md#{slug(operation['operation'])}"


def render_compatibility(
    operations: list[dict[str, Any]], schemas: SchemaReference
) -> str:
    lines = [
        LICENSE,
        "# Retained glossary API",
        "",
        "[API and SDK index](../sdk-api.md#qualified-retained-glossary-api)",
        "",
        "These qualified retained operations are separate from the canonical count. SDK mappings, schemas and headers come from the manifest. Parameter signatures and success statuses are read from the matching native controller source; generation rejects a controller or admission guard whose digest differs from the manifest. HTTP mappings without an explicit status use the native framework default of 200. The structured module and its native datasource must be configured.",
        "",
        "Pass the canonical tenant and workspace through `X-Tenant-ID` and `X-Workspace-ID`. For updates and deletion, preserve the exact returned `updated_at` string, including microseconds and its offset, for the `If-Match` precondition. List totals can be unknown; honor the returned `limit`, `offset` and `has_more`.",
        "",
    ]
    for operation in operations:
        name = operation["operation"]
        python = operation["sdk_python"] + (
            "(agent=True)" if operation["sdk_python_agent"] else ""
        )
        request = operation["request_schema"]
        lines += [
            f"<!-- compatibility-operation: {name} -->",
            f'<a id="{slug(name)}"></a>',
            f"## {name}",
            "",
            "```http",
            f"{operation['method']} {operation['path']}",
            "```",
            "",
            "| SDK | Method |",
            "| --- | --- |",
            f"| Python | {code(python)} |",
            f"| TypeScript | {code(operation['sdk_typescript'])} |",
            f"| Java | {code(operation['sdk_java'])} |",
            "",
            "| Contract | Value |",
            "| --- | --- |",
            f"| Request schema | {schemas.name_link(request, '../models/') if request else 'No request schema declared'} |",
            f"| Response schema | {schemas.name_link(operation['response_schema'], '../models/')} |",
            f"| Success status | {code(operation['success_status'])} |",
            f"| Encoding | {code(operation['encoding'])} |",
            "",
            "### Headers",
            "",
        ]
        lines += ["- " + code(header) for header in operation["headers"]]
        lines += [
            "",
            "### Parameters",
            "",
            "| Name | Location | Declared type | Required | Default |",
            "| --- | --- | --- | --- | --- |",
        ]
        for parameter in operation["parameters"]:
            default = (
                literal(parameter["default"])
                if "default" in parameter
                else "Not specified"
            )
            lines.append(
                f"| {code(parameter['name'])} | {parameter['location']} | {code(parameter['annotation'])} | {'Yes' if parameter['required'] else 'No'} | {default} |"
            )
        lines += [""]
    return "\n".join(lines)
