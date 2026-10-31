# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Enrich retained reference details from hash-verified controller source only."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

from compatibility import qualified_glossary


def _context_headers(root: Path) -> list[dict[str, Any]]:
    tree = ast.parse((root / "backend/src/koinon/web/legacy_security.py").read_text())
    controller = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "LegacyMembershipFilter"
    )
    method = next(
        node
        for node in controller.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "do_filter"
    )
    assignments = {
        target.id: ast.unparse(node.value)
        for node in ast.walk(method)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    required = any(
        isinstance(node, ast.If)
        and ast.unparse(node.test) == "not tenant or not workspace_id"
        and any(isinstance(child, ast.Raise) for child in node.body)
        for node in ast.walk(method)
    )
    if (
        not required
        or assignments.get("tenant") != "request.headers.get('x-tenant-id')"
        or assignments.get("workspace_id") != "request.headers.get('x-workspace-id')"
    ):
        raise ValueError(
            "Retained context header admission changed; review its source before publishing"
        )
    return [
        {"name": name, "annotation": "str", "location": "header", "required": True}
        for name in ("X-Tenant-ID", "X-Workspace-ID")
    ]


def _requires_revision(root: Path, guard: str) -> None:
    tree = ast.parse((root / guard).read_text())
    required = any(
        isinstance(node, ast.If)
        and ast.unparse(node.test) == "expected is None"
        and any(
            isinstance(child, ast.Raise)
            and isinstance(child.exc, ast.Call)
            and isinstance(child.exc.func, ast.Name)
            and child.exc.func.id == "GlossaryRevisionRequired"
            for child in node.body
        )
        for node in ast.walk(tree)
    )
    if not required:
        raise ValueError(
            "Retained revision admission changed; review its source before publishing"
        )


def enrich_retained(
    operations: list[dict[str, Any]], root: Path
) -> list[dict[str, Any]]:
    if not operations:
        return []
    actual = {value["operation"]: value for value in qualified_glossary(root)}
    headers = _context_headers(root)
    result: list[dict[str, Any]] = []
    for operation in operations:
        name = operation["operation"]
        inventory = actual.get(name)
        if inventory is None:
            raise ValueError(f"Retained operation is not admitted: {name}")
        for key in inventory:
            if operation[key] != inventory[key]:
                raise ValueError(
                    f"Retained source pin or route mismatch: {name} ({key})"
                )
        agent = operation["native_controller"] == "AgentGlossaryController"
        relative = (
            "packages/structured/src/flyquery/web/controllers/"
            + ("agent/" if agent else "")
            + "glossary_controller.py"
        )
        raw = (root / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != operation["native_source_sha256"]:
            raise ValueError(f"Retained native source pin mismatch: {name}")
        tree = ast.parse(raw)
        controller = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == operation["native_controller"]
        )
        method = next(
            node
            for node in controller.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == operation["native_method"]
        )
        mapping = next(
            node
            for node in method.decorator_list
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == operation["method"].lower() + "_mapping"
        )
        status = next(
            (
                ast.literal_eval(keyword.value)
                for keyword in mapping.keywords
                if keyword.arg == "status_code"
            ),
            200,
        )
        defaults = (
            {
                argument.arg: ast.literal_eval(default)
                for argument, default in zip(
                    method.args.args[-len(method.args.defaults) :], method.args.defaults
                )
            }
            if method.args.defaults
            else {}
        )
        parameters = [dict(value) for value in headers]
        for argument in method.args.args:
            if argument.arg == "self":
                continue
            annotation = (
                ast.unparse(argument.annotation)
                if argument.annotation is not None
                else ""
            )
            if annotation == "Request":
                continue
            location = (
                "query"
                if annotation.startswith("QueryParam[")
                else "path"
                if annotation.startswith("PathVar[")
                else "body"
                if "Body[" in annotation
                else None
            )
            if location is None:
                raise ValueError(
                    f"Unclassified retained parameter: {name}.{argument.arg}"
                )
            parameter = {
                "name": argument.arg,
                "annotation": annotation,
                "location": location,
                "required": argument.arg not in defaults,
            }
            if argument.arg in defaults:
                parameter["default"] = defaults[argument.arg]
            parameters.append(parameter)
        if operation["method"] in {"PUT", "DELETE"}:
            _requires_revision(root, operation["guard"])
            parameters.append(
                {
                    "name": "If-Match",
                    "annotation": "str",
                    "location": "header",
                    "required": True,
                }
            )
        result.append(
            {
                **operation,
                "parameters": parameters,
                "success_status": status,
                "encoding": "application/json",
            }
        )
    return result
