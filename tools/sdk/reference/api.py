# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Operation areas and exact canonical request/response documentation."""

from __future__ import annotations

import re
from typing import Any

from .retained import render_compatibility
from .schema import LICENSE, SchemaReference, code, literal, slug

AREAS = (
    (
        "catalog",
        "Catalog and proposals",
        ("CatalogController", "CatalogProposalController"),
    ),
    (
        "sources",
        "Sources, files and lineage",
        (
            "DocumentHistoryController",
            "ContentController",
            "DatasetFilesController",
            "TableProvenanceController",
            "TableCoordinateController",
        ),
    ),
    ("queries", "Search and queries", ()),
    ("curated-knowledge", "Curated knowledge", ("CuratedKnowledgeController",)),
    (
        "chat",
        "Chat and attachments",
        (
            "AssistantController",
            "ChatHistoryController",
            "ChatAttachmentsController",
            "OrganizationChatController",
        ),
    ),
    ("exports-sharing", "Exports and sharing", ("ExportController", "ShareController")),
    (
        "knowledge-services",
        "Knowledge connections and indexes",
        (
            "KnowledgeConnectionsController",
            "KnowledgeIndexesController",
            "OrganizationKnowledgeController",
        ),
    ),
    ("models-agents", "Models and agents", ("ProviderController", "AgentController")),
    (
        "people-access",
        "People and access",
        ("OrganizationPeopleController", "MembershipController"),
    ),
    (
        "corporate-identity",
        "Corporate identity",
        ("CorporateIdentityController", "CorporateProfilesController"),
    ),
    (
        "account",
        "Personal profiles and tokens",
        ("ProfileController", "PersonalTokenController"),
    ),
    (
        "applications-mcp",
        "Applications and MCP",
        (
            "AuthorizedApplicationController",
            "McpOAuthClientController",
            "McpConnectionController",
            "McpOrganizationConnectionController",
            "ExternalKnowledgeReviewController",
            "ExternalFileReviewController",
        ),
    ),
    (
        "platform",
        "Platform configuration and operations",
        (
            "ContextController",
            "CapabilitiesController",
            "OrganizationBrandingController",
            "BrandingDefaultsController",
            "JobController",
            "AuditController",
            "EvidenceController",
        ),
    ),
)


def area_for(operation: dict[str, Any]) -> str:
    controller, action = operation["operation"].split(".")
    if controller == "KnowledgeController":
        return "queries" if action in {"query", "search"} else "sources"
    for key, _, controllers in AREAS:
        if controller in controllers:
            return key
    raise ValueError(f"Unclassified operation: {operation['operation']}")


def operation_link(operation: dict[str, Any], prefix: str = "api/") -> str:
    return f"{prefix}{area_for(operation)}.md#{slug(operation['operation'])}"


def operation_title(name: str) -> str:
    return (
        re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name.split(".")[1])
        .replace("_", " ")
        .capitalize()
    )


def render_operation(operation: dict[str, Any], schemas: SchemaReference) -> list[str]:
    name = operation["operation"]
    title = operation_title(name)
    lines = [
        f"<!-- operation: {name} -->",
        f'<a id="{slug(name)}"></a>',
        f"## {title}",
        "",
        "```http",
        f"{operation['method']} {operation['path']}",
        "```",
        "",
        f"Contract operation: {code(name)}.",
        "",
        "| SDK | Method |",
        "| --- | --- |",
    ]
    for label, key in (
        ("Python", "sdk_python"),
        ("TypeScript", "sdk_typescript"),
        ("Java", "sdk_java"),
    ):
        if not operation.get(key):
            raise ValueError(f"Missing {label} mapping: {name}")
        lines.append(f"| {label} | {code(operation[key])} |")
    lines += ["", "### Parameters", ""]
    if operation["parameters"]:
        lines += [
            "These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.",
            "",
            "| Name | Location | Declared type | Required | Default |",
            "| --- | --- | --- | --- | --- |",
        ]
        for parameter in operation["parameters"]:
            if parameter["location"] not in {"path", "query", "body"}:
                raise ValueError(
                    f"Unsupported parameter location: {parameter['location']}"
                )
            default = (
                literal(parameter["default"])
                if "default" in parameter
                else "Not specified"
            )
            lines.append(
                f"| {code(parameter['name'])} | {parameter['location']} | {code(parameter['annotation'])} | {'Yes' if parameter['required'] else 'No'} | {default} |"
            )
    else:
        lines += [
            "No path, query or body arguments are declared in the canonical operation metadata."
        ]
    request = operation["request_schema"]
    statuses = operation.get("success_statuses", [operation["success_status"]])
    lines += [
        "",
        "### Request and response",
        "",
        "| Contract | Value |",
        "| --- | --- |",
        f"| Request schema | {schemas.name_link(request, '../models/') if request else 'No request schema declared'} |",
        f"| Response schema | {schemas.name_link(operation['response_schema'], '../models/')} |",
        f"| Success status | {', '.join(code(s) for s in statuses)} |",
        f"| Declared encoding | {code(operation['encoding'])} |",
        "",
        "Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.",
        "",
        "### Headers",
        "",
    ]
    lines += (
        ["- " + code(header) for header in operation["headers"]]
        if operation["headers"]
        else ["No operation-specific headers are declared in the canonical metadata."]
    )
    lines += [
        "",
        "Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).",
        "",
    ]
    return lines


def render_api(contract: dict[str, Any], schemas: SchemaReference) -> dict[str, str]:
    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key, _, _ in AREAS}
    seen: set[str] = set()
    for operation in contract["operations"]:
        name = operation["operation"]
        if name in seen:
            raise ValueError(f"Duplicate operation: {name}")
        seen.add(name)
        grouped[area_for(operation)].append(operation)
    if len(seen) != contract["canonical_operation_count"]:
        raise ValueError("Canonical operation count does not match the manifest")
    index = [
        LICENSE,
        "# API operations",
        "",
        "Choose an area, then an operation. Each operation records its exact SDK mappings, declared parameters, request and response types, success statuses and header requirements.",
        "",
        "| Area | Operations |",
        "| --- | --- |",
    ]
    pages: dict[str, str] = {}
    for key, title, _ in AREAS:
        operations = grouped[key]
        if not operations:
            continue
        index.append(f"| [{title}]({key}.md) | {len(operations)} |")
        rows = [
            LICENSE,
            f"# {title}",
            "",
            "[All API areas](index.md)",
            "",
            "Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.",
            "",
            "## On this page",
            "",
        ]
        rows += [
            f"- [{operation_title(operation['operation'])}](#{slug(operation['operation'])}) ({operation['method']})"
            for operation in operations
        ]
        rows += [""]
        for operation in operations:
            rows += render_operation(operation, schemas)
        pages[f"api/{key}.md"] = "\n".join(rows)
    index += [
        "",
        f"These {len(seen)} canonical operations are separate from the [qualified retained glossary API](../sdk-api.md#qualified-retained-glossary-api).",
        "",
    ]
    if contract.get("qualified_compatibility_operations"):
        pages["api/retained-glossary.md"] = render_compatibility(
            contract["qualified_compatibility_operations"], schemas
        )
        index += [
            "[Browse retained glossary operation details](retained-glossary.md).",
            "",
        ]
    pages["api/index.md"] = "\n".join(index)
    return pages
