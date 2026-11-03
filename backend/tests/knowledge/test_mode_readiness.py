# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module

import pytest
from pyfly.kernel import ServiceUnavailableException
from test_knowledge_connections import values

from koinon.assistants.repositories import ProviderRepository

pytest_plugins = ("test_knowledge_connections",)


def readiness(configured):
    service, _, _, _, _ = configured
    return import_module("koinon.organization_knowledge.transitions.readiness").ModeRoleReadiness(service)


async def test_rlm_readiness_requires_selected_role_and_current_provider(configured):
    service, _, _, tree, context = configured
    checker = readiness(configured)
    with pytest.raises(ServiceUnavailableException) as error:
        await checker.check("issuer|admin", "north", tree["workspace"].id, "rlm")
    assert error.value.code == "KNOWLEDGE_MODEL_BINDING_REQUIRED"
    await service.save("issuer|admin", "north", values(role="documents.rlm"))
    checked = await checker.check("issuer|admin", "north", tree["workspace"].id, "rlm")
    assert checked["documents.rlm"]["provider_id"] == "north-provider"
    provider = await context.get_bean(ProviderRepository).find_by_id("north-provider")
    provider.enabled = False
    await context.get_bean(ProviderRepository).save(provider)
    with pytest.raises(ServiceUnavailableException) as error:
        await checker.check("issuer|admin", "north", tree["workspace"].id, "rlm")
    assert error.value.code == "KNOWLEDGE_PROVIDER_UNAVAILABLE"


async def test_disabled_workspace_override_does_not_fall_back_to_tenant_role(configured):
    service, _, _, tree, _ = configured
    await service.save("issuer|admin", "north", values(role="documents.rlm"))
    await service.save(
        "issuer|admin",
        "north",
        values(role="documents.rlm", workspace_id=tree["workspace"].id, enabled=False),
    )
    with pytest.raises(ServiceUnavailableException) as error:
        await readiness(configured).check("issuer|admin", "north", tree["workspace"].id, "rlm")
    assert error.value.code == "KNOWLEDGE_MODEL_BINDING_REQUIRED"


async def test_current_agent_role_is_explicitly_conditional_not_provider_qualified(configured):
    service, _, _, tree, _ = configured
    await service.save(
        "issuer|admin",
        "north",
        values(
            role="documents.rlm", mode="current_agent", provider_id=None, model_id=None, model_options=None
        ),
    )
    checked = await readiness(configured).check("issuer|admin", "north", tree["workspace"].id, "rlm")
    assert checked["documents.rlm"]["requires_current_agent"] is True
    assert checked["documents.rlm"]["provider_id"] is None


async def test_curated_only_rag_does_not_require_an_unused_embedding_role(configured):
    service, _, _, tree, _ = configured
    await service.save("issuer|admin", "north", values(role="documents.answer"))
    checked = await readiness(configured).check(
        "issuer|admin", "north", tree["workspace"].id, "rag", has_documents=False
    )
    assert set(checked) == {"documents.answer"}
