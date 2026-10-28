# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request
from test_facade import context as context
from test_facade import upload
from test_legacy_read import admission

from koinon.knowledge.glossary_writes import GLOSSARY_WRITES, LegacyGlossaryWriteAdmission
from koinon.web.legacy_security import LegacyOperationPolicies


def request(method="POST", payload=None, revision=None):
    body = json.dumps(payload or {}).encode()
    receive = AsyncMock(return_value={"type": "http.request", "body": body, "more_body": False})
    headers = [] if revision is None else [(b"if-match", revision.encode())]
    value = Request(
        {"type": "http", "method": method, "path": "/", "headers": headers, "query_string": b"", "state": {}},
        receive,
    )
    return value, receive


async def prepared(context):
    facade, _, _, tree, _ = context
    await upload(context, "dataset")
    reader, _ = admission(facade)
    policies = LegacyOperationPolicies()
    guard = LegacyGlossaryWriteAdmission(
        reader, policies, SimpleNamespace(domains={"structured": {"registered": True}})
    )
    reader.verify = AsyncMock()
    guard._term = AsyncMock(
        return_value={
            "tenant_id": "north",
            "workspace_id": "native-workspace",
            "updated_at": datetime(2026, 10, 27, tzinfo=UTC),
            "related_columns_json": [],
            "related_metrics_json": [],
        }
    )
    return guard, policies, facade, tree


async def test_exact_six_writes_are_registered_and_agent_scopes_never_wildcard(context):
    _, policies, _, _ = await prepared(context)
    assert len(policies.operations) == len(GLOSSARY_WRITES) == 6
    assert policies.resolve("POST", "/api/v1/structured/glossary")
    policy, _ = policies.resolve("PUT", "/api/v1/structured/agent/glossary/id")
    assert policy.agent_scopes == ("flyquery.semantic:author",)
    assert policies.resolve("POST", "/api/v1/structured/semantic/metrics") is None


async def test_readonly_membership_denies_before_body_or_native_lookup(context):
    from koinon.catalog.errors import AccessDenied

    guard, _, _, tree = await prepared(context)
    value, receive = request(payload={"term": "Revenue", "definition": "Sales"})
    with pytest.raises(AccessDenied):
        await guard.verify(value, SimpleNamespace(subject="issuer|reader"), "north", tree["workspace"].id, {})
    receive.assert_not_awaited()
    guard.read.verify.assert_not_awaited()


async def test_body_is_bounded_and_cached_for_native_parser_and_scope_fields_are_rejected(context):
    from flyquery.core.services.glossary.errors import GlossaryPayloadInvalid
    from pyfly.kernel import PayloadTooLargeException

    guard, _, _, tree = await prepared(context)
    actor = SimpleNamespace(subject="issuer|admin")
    value, _ = request(payload={"term": "Revenue", "definition": "Sales"})
    await guard.verify(value, actor, "north", tree["workspace"].id, {})
    assert json.loads(value.scope["pyfly.request_body"])["term"] == "Revenue"
    for payload, exception in [
        ({"term": "Revenue", "definition": "Sales", "tenant_id": "foreign"}, GlossaryPayloadInvalid),
        ({"term": "Revenue", "definition": "x" * 70000}, PayloadTooLargeException),
    ]:
        value, _ = request(payload=payload)
        with pytest.raises(exception):
            await guard.verify(value, actor, "north", tree["workspace"].id, {})


async def test_mutation_requires_exact_current_revision_before_native_call(context):
    from flyquery.core.services.glossary.errors import GlossaryRevisionConflict, GlossaryRevisionRequired

    guard, _, _, tree = await prepared(context)
    actor = SimpleNamespace(subject="issuer|admin")
    for revision, exception in [
        (None, GlossaryRevisionRequired),
        ('"2020-01-01T00:00:00Z"', GlossaryRevisionConflict),
    ]:
        value, _ = request("PUT", {"definition": "Updated"}, revision)
        with pytest.raises(exception):
            await guard.verify(value, actor, "north", tree["workspace"].id, {"term_id": "term"})


async def test_related_resources_must_resolve_and_pass_original_ancestry_guard(context):
    from koinon.catalog.errors import AccessDenied

    guard, _, _, tree = await prepared(context)
    guard._reference = AsyncMock(side_effect=AccessDenied("Unknown or foreign column"))
    value, _ = request(
        payload={"term": "Revenue", "definition": "Sales", "related_columns": ["foreign.column"]}
    )
    with pytest.raises(AccessDenied):
        await guard.verify(value, SimpleNamespace(subject="issuer|admin"), "north", tree["workspace"].id, {})


async def test_exact_asset_token_denies_workspace_glossary_before_body_or_native_calls(context):
    from koinon.catalog.errors import AccessDenied

    guard, _, facade, tree = await prepared(context)
    facade.catalog.restriction = SimpleNamespace(
        grant=AsyncMock(
            return_value=SimpleNamespace(
                tenant_id="north",
                workspace_ids=[tree["workspace"].id],
                asset_ids=["selected-asset"],
                scopes=["catalog:write", "catalog:read"],
            )
        ),
        resource=AsyncMock(),
    )
    value, receive = request(payload={"term": "Revenue", "definition": "Sales"})
    with pytest.raises(AccessDenied, match="exact-asset"):
        await guard.verify(value, SimpleNamespace(subject="issuer|admin"), "north", tree["workspace"].id, {})
    receive.assert_not_awaited()
    guard.read.verify.assert_not_awaited()


async def test_archived_workspace_denies_even_valid_current_term_before_native_calls(context):
    from koinon.catalog.errors import AccessDenied

    guard, _, facade, tree = await prepared(context)
    await facade.catalog.archive("issuer|admin", "north", tree["workspace"].id)
    value, receive = request("PUT", {"definition": "Updated"}, "2026-10-27T00:00:00Z")
    with pytest.raises(AccessDenied, match="archived"):
        await guard.verify(
            value, SimpleNamespace(subject="issuer|admin"), "north", tree["workspace"].id, {"term_id": "term"}
        )
    receive.assert_not_awaited()
    guard._term.assert_not_awaited()
