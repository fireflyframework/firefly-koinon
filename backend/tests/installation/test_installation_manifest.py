# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

import pytest
from pydantic import ValidationError

from koinon.installation.dtos import InstallationPlan


def example():
    return {
        "schema_version": 1,
        "plan_key": "initial-knowledge",
        "tenant_id": "example",
        "providers": [
            {
                "key": "chat",
                "name": "Chat",
                "kind": "openai",
                "api": "chat",
                "base_url": "https://api.openai.com/v1",
                "model_ids": ["chat-model"],
                "secret_env": "INSTALL_CHAT_KEY",
            },
            {
                "key": "embedding",
                "name": "Embeddings",
                "kind": "openai",
                "api": "chat",
                "base_url": "https://api.openai.com/v1",
                "model_ids": ["embedding-model"],
                "secret_env": "INSTALL_EMBEDDING_KEY",
            },
        ],
        "catalog": [
            {"key": "space", "kind": "workspace", "name": "Company knowledge"},
            {"key": "project", "kind": "project", "name": "Shared", "parent_key": "space"},
            {"key": "folder", "kind": "collection", "name": "Documents", "parent_key": "project"},
        ],
        "connections": [
            {"key": "answer", "role": "documents.answer", "provider_key": "chat", "model_id": "chat-model"}
        ],
        "indexes": [
            {
                "key": "documents",
                "workspace_key": "space",
                "domain": "documents",
                "provider_key": "embedding",
                "model_id": "embedding-model",
                "dimensions": 1536,
            }
        ],
        "agent": {
            "key": "guide",
            "name": "Knowledge guide",
            "provider_key": "chat",
            "model_id": "chat-model",
            "tools": ["search_knowledge"],
            "set_default_if_empty": True,
        },
    }


def test_manifest_resolves_native_hierarchy_roles_and_stable_fingerprint():
    plan = InstallationPlan.model_validate(example())
    assert plan.catalog_order() == ["space", "project", "folder"]
    assert plan.fingerprint() == InstallationPlan.model_validate(deepcopy(example())).fingerprint()
    assert "INSTALL_CHAT_KEY" in plan.model_dump_json()


@pytest.mark.parametrize(
    "change",
    [
        lambda v: v["providers"][0].update(secret="must-never-appear"),
        lambda v: v["providers"][0].update(secret_env="../../credentials"),
        lambda v: v["providers"].append(deepcopy(v["providers"][0])),
        lambda v: v["catalog"][1].update(parent_key="missing"),
        lambda v: v["catalog"][0].update(parent_key="folder"),
        lambda v: v["catalog"][2].update(kind="folder"),
        lambda v: v["agent"].update(provider_key="missing"),
        lambda v: v["agent"].update(model_id="undeclared-model"),
        lambda v: v["connections"][0].update(role="documents.embedding"),
        lambda v: v["indexes"][0].update(workspace_key="folder"),
        lambda v: v["indexes"].append(deepcopy(v["indexes"][0])),
    ],
)
def test_manifest_rejects_unsafe_or_unresolvable_plans_before_any_io(change):
    value = example()
    change(value)
    with pytest.raises(ValidationError):
        InstallationPlan.model_validate(value)


def test_shipped_installation_example_is_a_valid_native_plan():
    from pathlib import Path

    plan = InstallationPlan.model_validate_json(
        (Path(__file__).parents[3] / "deploy/production/installation-plan.json.example").read_bytes()
    )
    assert {node.kind for node in plan.catalog} == {"workspace", "project", "collection", "corpus"}
    assert len(plan.indexes) == 2
