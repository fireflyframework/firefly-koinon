# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
import sys
import zipfile
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError as SchemaValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugin_build import build, catalog_files, check_catalog, safe_tree
from plugin_profile import DeploymentProfile
from plugin_validation import validate_package


def profile(**changes):
    return DeploymentProfile.model_validate(
        {
            "name": "example",
            "server_url": "https://knowledge.example.com/mcp",
            "public_client_id": "operator-registered-public-client",
            "callback_port": 8765,
            **changes,
        }
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/mcp",
        "https://user:private@example.com/mcp",
        "https://example.com/mcp?token=private",
        "https://example.com/mcp#private",
        "file:///mcp",
        "https://example.com/\nsecret",
        "https://example.com/\\mcp",
        " https://example.com/mcp",
        "https:///mcp",
        "https://example.com:bad/mcp",
    ],
)
def test_profile_rejects_unsafe_endpoint_without_echoing_secrets(url):
    with pytest.raises(ValueError) as error:
        profile(server_url=url)
    assert "private" not in str(error.value) and "secret" not in str(error.value)


@pytest.mark.parametrize(
    "change",
    [
        {"client_secret": "private"},
        {"token": "private"},
        {"public_client_id": "bad\nheader"},
        {"callback_port": True},
        {"callback_port": 0},
        {"callback_port": 65536},
        {"scopes": ["audit:read"]},
        {"scopes": ["jobs:manage"]},
        {"scopes": ["catalog:write"]},
        {"scopes": ["catalog:read", "catalog:read"]},
        {"name": "../../escape"},
    ],
)
def test_profile_has_no_secret_or_scope_expansion_input(change):
    with pytest.raises(ValueError):
        profile(**change)


def test_checked_in_marketplace_has_exact_canonical_skills_brand_and_legal():
    check_catalog()
    files = catalog_files()
    assert "skills/koinon-evidence/SKILL.md" in files
    assert "assets/icon.png" in files and "LICENSE" in files and "NOTICE" in files
    assert "mcp.json" not in files and ".mcp.json" not in files


def test_artifacts_are_deterministic_and_relocatable(tmp_path):
    first, second = tmp_path / "first", tmp_path / "relocated"
    one = build(first, profile())
    two = build(second, profile())
    assert one == two
    assert {p.name: p.read_bytes() for p in first.glob("*.zip")} == {
        p.name: p.read_bytes() for p in second.glob("*.zip")
    }
    for archive in first.glob("*.zip"):
        with zipfile.ZipFile(archive) as opened:
            assert all(
                not name.startswith("/") and ".." not in Path(name).parts
                for name in opened.namelist()
            )
            assert not any(
                "hooks/" in name or "node_modules/" in name
                for name in opened.namelist()
            )


def test_explicit_oauth_variants_preserve_url_client_and_least_scope(tmp_path):
    build(tmp_path / "result", profile())
    claude = json.loads((tmp_path / "result/claude/.mcp.json").read_text())[
        "mcpServers"
    ]["koinon"]
    assert claude == {
        "type": "http",
        "url": profile().server_url,
        "oauth": {
            "clientId": profile().public_client_id,
            "callbackPort": 8765,
            "scopes": "catalog:read",
        },
    }
    portable = json.loads((tmp_path / "result/portable/mcp.json").read_text())[
        "mcpServers"
    ]["koinon"]
    assert (
        portable["url"] == profile().server_url
        and portable["type"] == "streamable-http"
    )
    auth = portable["extensions"]["com.openai"]["auth"]
    assert auth["client"] == {
        "mode": "provided",
        "clientId": profile().public_client_id,
        "tokenEndpointAuthMethod": "none",
    }
    assert auth["defaultScopes"] == ["catalog:read"]
    report = validate_package(tmp_path / "result/portable")
    assert report["mcp_base_schema"] == "valid"
    assert report["host_auth_extension"] == "documented_strict_structure"
    assert (
        report["full_mcp_standard_conformance"]
        == "not_claimed_host_extension_not_in_published_schema"
    )


def test_existing_app_variant_requires_real_operator_supplied_mapping(tmp_path):
    with pytest.raises(ValueError):
        build(tmp_path / "missing", profile(), include_app=True)
    build(
        tmp_path / "configured",
        profile(application_id="plugin_asdk_app_operatorprovided"),
        include_app=True,
    )
    app = tmp_path / "configured/registered-app"
    assert json.loads((app / ".app.json").read_text()) == {
        "apps": {"koinon": {"id": "plugin_asdk_app_operatorprovided", "required": True}}
    }
    assert not (app / "mcp.json").exists()


def test_existing_output_is_preserved_and_not_overwritten(tmp_path):
    out = tmp_path / "existing"
    out.mkdir()
    (out / "retained").write_text("original")
    with pytest.raises(FileExistsError):
        build(out, profile())
    assert (out / "retained").read_text() == "original"


def test_symlink_and_escaping_asset_paths_are_rejected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "external").symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError):
        safe_tree(source)
    build(tmp_path / "built", profile())
    manifest = tmp_path / "built/portable/plugin.json"
    content = json.loads(manifest.read_text())
    content["extensions"]["com.openai"]["interface"]["composerIcon"] = "../outside.png"
    manifest.write_text(json.dumps(content))
    with pytest.raises(ValueError):
        validate_package(manifest.parent)


def test_requestable_scopes_match_the_current_native_oauth_inventory():
    import ast

    from plugin_profile import OAUTH_SCOPES

    root = Path(__file__).resolve().parents[3]
    parsed = ast.parse((root / "backend/src/koinon/mcp_auth/settings.py").read_text())
    values = [
        node.value.args[0]
        for node in parsed.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "MCP_SCOPES"
            for target in node.targets
        )
    ]
    assert len(values) == 1
    assert OAUTH_SCOPES == frozenset(ast.literal_eval(values[0]))


@pytest.mark.parametrize("tamper", ["header", "client_secret", "hook", "oversized"])
def test_validation_rejects_executable_credential_and_oversized_manifests(
    tmp_path, tamper
):
    build(tmp_path / "built", profile())
    root = tmp_path / "built/portable"
    if tamper == "hook":
        path = root / "plugin.json"
        value = json.loads(path.read_text())
        value["extensions"]["com.openai"]["hooks"] = "./run.json"
    else:
        path = root / "mcp.json"
        value = json.loads(path.read_text())
        server = value["mcpServers"]["koinon"]
        if tamper == "header":
            server["headers"] = {"Authorization": "Bearer fixture"}
        if tamper == "client_secret":
            server["extensions"]["com.openai"]["auth"]["client"]["clientSecret"] = (
                "fixture"
            )
    path.write_text("x" * 65537 if tamper == "oversized" else json.dumps(value))
    with pytest.raises((ValueError, SchemaValidationError)):
        validate_package(root)
