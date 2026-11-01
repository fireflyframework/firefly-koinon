# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Offline schema and containment checks, with explicit host-extension qualification."""

import copy
import json
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator
from plugin_profile import DeploymentProfile, secure_url

ROOT = Path(__file__).resolve().parent


def schema(name):
    value = json.loads((ROOT / "schemas" / name).read_text())
    Draft202012Validator.check_schema(value)
    return Draft202012Validator(value)


def inside(root: Path, value: str) -> Path:
    relative = PurePosixPath(value)
    if (
        not value.startswith("./")
        or ".." in relative.parts
        or relative.is_absolute()
        or "\\" in value
    ):
        raise ValueError("Package component paths must remain inside the plugin")
    target = root / relative
    if (
        target.is_symlink()
        or not target.resolve().is_relative_to(root.resolve())
        or not target.is_file()
    ):
        raise ValueError("Package component is missing or outside the plugin")
    return target


def read_json(root: Path, name: str):
    path = inside(root, "./" + name)
    if path.stat().st_size > 65536:
        raise ValueError("Package manifests must be at most64KiB")
    return json.loads(path.read_text())


def validate_package(root: Path):
    if root.is_symlink():
        raise ValueError("Plugin roots must not be symlinks")
    total = 0
    for count, path in enumerate(root.rglob("*"), start=1):
        if count > 200:
            raise ValueError("Package inventory exceeds its bound")
        if path.is_symlink():
            raise ValueError("Package symlinks are not supported")
        if path.is_file():
            total += path.stat().st_size
            if total > 8 * 1024 * 1024:
                raise ValueError("Package bytes exceed their bound")
    report = {"plugin_schema": "valid", "connection": "separate"}
    manifest = read_json(root, "plugin.json")
    schema("plugin.schema.json").validate(manifest)
    extension = manifest.get("extensions", {}).get("com.openai", {})
    if not set(extension) <= {"interface", "apps"}:
        raise ValueError("Unsupported host manifest settings")
    interface = extension.get("interface", {})
    schema("openai-interface.schema.json").validate(interface)
    for key in ("composerIcon", "logo"):
        if key in interface:
            inside(root, interface[key])
    if "apps" in extension:
        if extension["apps"] != "./.app.json":
            raise ValueError(
                "Existing application mappings use the fixed .app.json path"
            )
        app = read_json(root, ".app.json")
        if set(app) != {"apps"} or set(app["apps"]) != {"koinon"}:
            raise ValueError("Use one explicit existing application mapping")
        mapping = app["apps"]["koinon"]
        if set(mapping) != {"id", "required"} or mapping["required"] is not True:
            raise ValueError("Invalid existing application mapping")
        DeploymentProfile.existing_app(mapping["id"])
        report["connection"] = "existing_application_reference_not_registration"
    if (root / "mcp.json").exists():
        value = read_json(root, "mcp.json")
        if set(value.get("mcpServers", {})) != {"koinon"}:
            raise ValueError("Use one named remote connection")
        server = value["mcpServers"]["koinon"]
        if (
            set(server) != {"type", "url", "extensions"}
            or server["type"] != "streamable-http"
        ):
            raise ValueError("Only explicit HTTPS OAuth transport is supported")
        secure_url(server["url"])
        host = server.get("extensions", {})
        if set(host) != {"com.openai"} or set(host["com.openai"]) != {"auth"}:
            raise ValueError("Unsupported connection extension")
        schema("openai-auth.schema.json").validate(host["com.openai"]["auth"])
        core = copy.deepcopy(value)
        del core["mcpServers"]["koinon"]["extensions"]
        schema("mcp.schema.json").validate(core)
        auth = host["com.openai"]["auth"]
        DeploymentProfile.model_validate(
            {
                "name": "validation",
                "server_url": server["url"],
                "public_client_id": auth["client"]["clientId"],
                "callback_port": 1,
                "scopes": auth["defaultScopes"],
            }
        )
        report.update(
            {
                "connection": "provided_public_oauth_client",
                "mcp_base_schema": "valid",
                "host_auth_extension": "documented_strict_structure",
                "full_mcp_standard_conformance": "not_claimed_host_extension_not_in_published_schema",
            }
        )
    if (root / ".claude-plugin/plugin.json").exists():
        claude = read_json(root, ".claude-plugin/plugin.json")
        if (
            not set(claude)
            <= {
                "name",
                "version",
                "description",
                "author",
                "homepage",
                "repository",
                "license",
                "keywords",
                "displayName",
                "skills",
                "icon",
            }
            or claude.get("skills") != "./skills/"
        ):
            raise ValueError("Unsupported plugin component or executable settings")
        inside(root, claude["icon"])
    if (root / ".mcp.json").exists():
        value = read_json(root, ".mcp.json")
        if set(value) != {"mcpServers"} or set(value["mcpServers"]) != {"koinon"}:
            raise ValueError("Use one named remote connection")
        server = value["mcpServers"]["koinon"]
        if set(server) != {"type", "url", "oauth"} or server["type"] != "http":
            raise ValueError("Only explicit HTTPS OAuth transport is supported")
        auth = server["oauth"]
        if set(auth) != {"clientId", "callbackPort", "scopes"}:
            raise ValueError("Unsupported OAuth fields")
        DeploymentProfile.model_validate(
            {
                "name": "validation",
                "server_url": server["url"],
                "public_client_id": auth["clientId"],
                "callback_port": auth["callbackPort"],
                "scopes": auth["scopes"].split(" "),
            }
        )
        report["connection"] = "provided_public_oauth_client"
    return report
