# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import hashlib
import json
from importlib import import_module
from types import SimpleNamespace

import pytest
from flycanon.config import CanonSettings
from flyquery.config import FlyquerySettings
from pydantic import ValidationError
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.kernel import ConflictException
from test_contract import documents, input_policy, structured

from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import AuditRepository, MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService
from koinon.organization_knowledge.dtos import (
    OrganizationKnowledgeSettings,
    OrganizationKnowledgeSettingsInput,
)


@pytest.fixture
async def knowledge(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'policy.db'}",
                        }
                    },
                }
            }
        )
    )
    docs = CanonSettings(
        answer_mode="rlm",
        retrieval_top_k=19,
        retrieval_per_query_k=47,
        retrieval_rrf_k=85,
        query_expansion_enabled=True,
        query_expansion_n=4,
        rlm_max_iters=11,
        rlm_sub_budget=21,
        rlm_max_depth=2,
        rlm_self_consistency=3,
    )
    sql = FlyquerySettings(
        top_k_schema=23,
        top_k_examples=7,
        top_k_metrics=9,
        rrf_k=91,
        generation_candidates=4,
        max_refine_retries=3,
        grounding_min_confidence=0.71,
    )
    context.container.register_instance(CanonSettings, docs)
    context.container.register_instance(FlyquerySettings, sql)
    for package in ("koinon.catalog", "koinon.organization_knowledge"):
        scan_package(package, context.container)
    await context.start()
    try:
        for tenant in ("north", "south"):
            await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant))
        for subject, tenant, role in (
            ("admin", "north", "admin"),
            ("viewer", "north", "viewer"),
            ("operator", "north", "operator"),
            ("outside", "south", "admin"),
        ):
            await context.get_bean(MembershipRepository).save(
                Membership(id=subject, subject=subject, tenant_id=tenant, role=role)
            )
        catalog = context.get_bean(CatalogService)
        workspace = await catalog.create("admin", "north", kind="workspace", name="Controlled")
        await context.get_bean(MembershipRepository).save(
            Membership(
                id="scoped", subject="scoped", tenant_id="north", workspace_id=workspace.id, role="admin"
            )
        )
        module = import_module("koinon.organization_knowledge.service")
        yield SimpleNamespace(
            context=context,
            service=context.get_bean(module.OrganizationKnowledgeService),
            catalog=catalog,
            documents=docs,
            structured=sql,
            workspace=workspace,
        )
    finally:
        await context.stop()


def update_input(**changes):
    return OrganizationKnowledgeSettingsInput.model_validate(input_policy() | changes)


async def test_absent_policy_inherits_actual_native_deployment_without_creating_a_row(knowledge):
    result = await knowledge.service.get("viewer", "north")
    assert isinstance(result, OrganizationKnowledgeSettings)
    assert (result.tenant_id, result.revision, result.schema_version, result.origin) == (
        "north",
        0,
        1,
        "deployment",
    )
    assert result.documents.model_dump() == documents() | {
        "answer_mode": "rlm",
        "retrieval_top_k": 19,
        "retrieval_per_query_k": 47,
        "retrieval_rrf_k": 85,
        "query_expansion_enabled": True,
        "query_expansion_n": 4,
        "rlm_max_iters": 11,
        "rlm_sub_budget": 21,
        "rlm_max_depth": 2,
        "rlm_self_consistency": 3,
    }
    assert result.structured.model_dump() == structured() | {
        "top_k_schema": 23,
        "top_k_examples": 7,
        "top_k_metrics": 9,
        "rrf_k": 91,
        "generation_candidates": 4,
        "max_refine_retries": 3,
        "grounding_min_confidence": 0.71,
    }
    repo = import_module("koinon.organization_knowledge.repositories").OrganizationKnowledgeRepository()
    assert await repo.find_by_id("north") is None
    assert not await knowledge.context.get_bean(AuditRepository).find_all(
        action="organization_knowledge.updated"
    )


async def test_only_tenant_admin_can_write_but_scoped_members_can_read_policy(knowledge):
    for subject in ("viewer", "operator", "scoped", "outside"):
        with pytest.raises(AccessDenied):
            await knowledge.service.update(subject, "north", update_input())
    with pytest.raises(AccessDenied):
        await knowledge.service.get("outside", "north")
    assert (await knowledge.service.get("scoped", "north")).revision == 0


async def test_policy_is_independent_per_organization_and_snapshot_is_immutable(knowledge):
    saved = await knowledge.service.update("admin", "north", update_input())
    assert (saved.revision, saved.origin, saved.documents.answer_mode) == (1, "organization", "rag")
    snapshot = await knowledge.service.snapshot("viewer", "north")
    value = snapshot.model_dump(mode="json")
    digest = value.pop("digest")
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    assert digest == hashlib.sha256(canonical.encode()).hexdigest()
    assert snapshot.documents.answer_mode == "rag"
    assert (await knowledge.service.get("outside", "south")).documents.answer_mode == "rlm"
    await knowledge.service.update(
        "admin",
        "north",
        update_input(
            expected_revision=1, documents=documents() | {"answer_mode": "rlm", "rlm_sub_budget": 2}
        ),
    )
    assert snapshot.revision == 1 and snapshot.documents.answer_mode == "rag"
    for field, changed in (("tenant_id", "south"), ("origin", "deployment"), ("digest", "0" * 64)):
        with pytest.raises(ValidationError):
            type(snapshot).model_validate(snapshot.model_dump() | {field: changed})
    with pytest.raises(ValidationError):
        snapshot.documents.rlm_sub_budget = 99


async def test_first_create_and_update_cas_have_one_winner_without_stale_audits(knowledge):
    for revision in (0, 1):
        values = [
            update_input(expected_revision=revision, documents=documents() | {"rlm_max_iters": n})
            for n in (4, 7)
        ]
        results = await asyncio.gather(
            *(knowledge.service.update("admin", "north", value) for value in values), return_exceptions=True
        )
        assert sum(isinstance(value, OrganizationKnowledgeSettings) for value in results) == 1, results
        assert sum(isinstance(value, ConflictException) for value in results) == 1, results
        current = await knowledge.service.get("viewer", "north")
        assert current.revision == revision + 1
        audits = await knowledge.context.get_bean(AuditRepository).find_all(
            action="organization_knowledge.updated"
        )
        assert len(audits) == revision + 1
    repo = import_module("koinon.organization_knowledge.repositories").OrganizationKnowledgeRepository()
    row = await repo.find_by_id("north")
    assert row.updated_by == "admin" and row.updated_at.tzinfo is not None


async def test_audit_failure_rolls_back_the_policy_write(knowledge, monkeypatch):
    async def failure(*args, **kwargs):
        raise RuntimeError("Controlled audit failure")

    monkeypatch.setattr(knowledge.catalog, "_audit", failure)
    with pytest.raises(RuntimeError, match="Controlled audit failure"):
        await knowledge.service.update("admin", "north", update_input())
    assert (await knowledge.service.get("viewer", "north")).revision == 0


async def test_server_capabilities_publish_actual_limits_without_claiming_model_readiness(knowledge):
    value = (await knowledge.service.get("viewer", "north")).capabilities
    assert value.documents.answer_modes == ["rag", "rlm"]
    assert value.documents.rlm_curated_knowledge_supported is False
    assert value.documents.rlm_curated_knowledge_reason == "KNOWLEDGE_RLM_UNQUALIFIED"
    assert value.documents.rlm_model_role == "documents.rlm"
    assert value.documents.bounds.answer_top_k.model_dump() == {"minimum": 1, "maximum": 40}
    assert value.documents.bounds.rlm_sub_budget.model_dump() == {"minimum": 0, "maximum": 128}
    assert value.structured.bounds.grounding_min_confidence.model_dump() == {"minimum": 0.0, "maximum": 1.0}
    assert set(value.model_dump()) == {"documents", "structured"}


async def test_inherited_snapshot_is_a_value_not_a_live_deployment_settings_reference(knowledge):
    snapshot = await knowledge.service.snapshot("viewer", "north")
    knowledge.documents.answer_mode = "rag"
    knowledge.documents.rlm_sub_budget = 2
    knowledge.structured.max_refine_retries = 0
    assert snapshot.documents.answer_mode == "rlm" and snapshot.documents.rlm_sub_budget == 21
    assert snapshot.structured.max_refine_retries == 3
    assert (await knowledge.service.snapshot("viewer", "north")).documents.answer_mode == "rag"


async def test_invalid_native_baseline_fails_explicitly_instead_of_changing_configuration(knowledge):
    from pyfly.kernel import ServiceUnavailableException

    knowledge.structured.top_k_schema = 101
    with pytest.raises(ServiceUnavailableException) as error:
        await knowledge.service.get("viewer", "north")
    assert error.value.code == "KNOWLEDGE_SETTINGS_UNAVAILABLE"
    assert knowledge.structured.top_k_schema == 101


async def test_empty_organization_global_admin_can_read_and_snapshot_without_workspace(knowledge):
    value = await knowledge.service.get("outside", "south")
    snapshot = await knowledge.service.snapshot("outside", "south")
    assert value.tenant_id == snapshot.tenant_id == "south"
    assert value.revision == snapshot.revision == 0
    assert snapshot.origin == "deployment"


async def test_audit_failure_rolls_back_existing_policy_revision_and_values(knowledge, monkeypatch):
    saved = await knowledge.service.update("admin", "north", update_input())

    async def failure(*args, **kwargs):
        raise RuntimeError("Controlled update audit failure")

    monkeypatch.setattr(knowledge.catalog, "_audit", failure)
    with pytest.raises(RuntimeError, match="Controlled update audit failure"):
        await knowledge.service.update(
            "admin", "north", update_input(expected_revision=1, documents=documents() | {"rlm_max_iters": 2})
        )
    current = await knowledge.service.get("viewer", "north")
    assert current == saved
    audits = await knowledge.context.get_bean(AuditRepository).find_all(
        action="organization_knowledge.updated"
    )
    assert len(audits) == 1


async def test_concurrent_independent_organizations_keep_distinct_policies(knowledge):
    north, south = await asyncio.gather(
        knowledge.service.update("admin", "north", update_input()),
        knowledge.service.update(
            "outside",
            "south",
            update_input(
                documents=documents() | {"answer_mode": "rlm", "rlm_max_iters": 31},
                structured=structured() | {"max_refine_retries": 0},
            ),
        ),
    )
    assert north.documents.answer_mode == "rag" and north.documents.rlm_max_iters == 8
    assert south.documents.answer_mode == "rlm" and south.documents.rlm_max_iters == 31
    assert north.structured.max_refine_retries == 2 and south.structured.max_refine_retries == 0
    assert (await knowledge.service.get("viewer", "north")) == north
    assert (await knowledge.service.get("outside", "south")) == south


async def test_rlm_capability_requires_exact_recorded_document_views(knowledge):
    value = (await knowledge.service.get("viewer", "north")).capabilities.documents
    assert value.rlm_recorded_views_required is True
    assert value.rlm_recorded_views_reason == "RLM_DOCUMENT_VIEWS_REQUIRED"
