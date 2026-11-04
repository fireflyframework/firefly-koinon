# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module
from types import SimpleNamespace

import pytest
from pyfly.kernel import ConflictException
from test_mode_transitions import transitions
from test_organization_knowledge_service import update_input

from koinon.security.authority import primary_authority

pytest_plugins = ("test_organization_knowledge_service",)


async def test_activation_attempt_identity_survives_reuse_and_resolution_is_cas(knowledge):
    module = import_module("koinon.organization_knowledge.transitions.index_attempts")
    service = transitions(knowledge)
    parent = await service.request("admin", "north", update_input(), "attempt-one")
    records = module.ModeIndexAttemptRepository()
    index = SimpleNamespace(
        id="index",
        tenant_id="north",
        workspace_id=knowledge.workspace.id,
        native_workspace_id="old-workspace",
        native_id="old-set",
        revision=4,
        job_id=None,
        provider_id="provider",
        provider_revision=2,
        model_id="embedding",
        dimensions=768,
        storage_dimensions=768,
        embedding_fingerprint="fingerprint",
        updated_by="admin",
        access_token_id=None,
        transition={
            "request": {"expected_revision": 3},
            "previous_native_id": "previous",
            "activation_actor": "issuer|original-activator",
            "activation_token_id": "activation-token",
        },
    )
    async with primary_authority(read_only=False):
        first = await records.capture("north", parent.id, index)
        assert await records.capture("north", parent.id, index) == first
        index.transition = {
            **index.transition,
            "mode_activation_attempt_id": first,
            "mode_activation_attempt_revision": 4,
        }
        index.revision = 5
        await records.resolve("north", parent.id, first, index, "restored", expected_revision=1)
        await records.resolve("north", parent.id, first, index, "restored", expected_revision=1)
        with pytest.raises(ConflictException):
            await records.resolve("north", parent.id, first, index, "finished", expected_revision=1)
    await service.cancel("admin", "north", parent.id, expected_revision=parent.revision)
    next_parent = await service.request("admin", "north", update_input(), "attempt-two")
    index.native_workspace_id, index.native_id, index.revision = "new-workspace", "new-set", 9
    async with primary_authority(read_only=False):
        second = await records.capture("north", next_parent.id, index)
    assert second != first
    old = (await records.page("north", parent.id))[0]
    assert old.native_workspace_id == "old-workspace" and old.native_id == "old-set"
    assert old.attempt_revision == 4 and old.provider_revision == 2
    assert old.actor == "issuer|original-activator" and old.access_token_id == "activation-token"
    old_page = await service.recovery_page("admin", "north", parent.id)
    assert old_page.items[0].receipt_id == first
    assert old_page.items[0].native_workspace_id == "old-workspace"
    assert old_page.items[0].resolution == "restored" and old_page.items[0].actions == []
    assert not await records.page("south", parent.id)
    assert not await records.page("north", "missing")


async def test_failed_activation_transaction_does_not_leave_a_receipt(knowledge):
    module = import_module("koinon.organization_knowledge.transitions.index_attempts")
    service = transitions(knowledge)
    parent = await service.request("admin", "north", update_input(), "attempt-rollback")
    records = module.ModeIndexAttemptRepository()
    index = SimpleNamespace(
        id="index",
        tenant_id="north",
        workspace_id=knowledge.workspace.id,
        native_workspace_id="native",
        native_id="set",
        revision=2,
        job_id=None,
        provider_id="provider",
        provider_revision=1,
        model_id="embedding",
        dimensions=768,
        storage_dimensions=768,
        embedding_fingerprint="fingerprint",
        updated_by="admin",
        access_token_id=None,
        transition={"request": {}, "previous_native_id": None},
    )
    with pytest.raises(RuntimeError, match="rollback"):
        async with primary_authority(read_only=False):
            await records.capture("north", parent.id, index)
            raise RuntimeError("rollback")
    assert not await records.page("north", parent.id)


async def test_database_rejects_rewriting_or_deleting_attempt_identity(knowledge):
    from pyfly.kernel import DataIntegrityException

    from koinon.organization_knowledge.transitions.index_attempts import ModeIndexAttemptRepository

    service = transitions(knowledge)
    parent = await service.request("admin", "north", update_input(), "immutable")
    records = ModeIndexAttemptRepository()
    index = SimpleNamespace(
        id="index",
        tenant_id="north",
        workspace_id=knowledge.workspace.id,
        native_workspace_id="native",
        native_id="set",
        revision=2,
        job_id=None,
        provider_id="provider",
        provider_revision=1,
        model_id="embedding",
        dimensions=768,
        storage_dimensions=768,
        embedding_fingerprint="fingerprint",
        updated_by="admin",
        access_token_id=None,
        transition={"request": {}, "previous_native_id": None},
    )
    async with primary_authority(read_only=False):
        identifier = await records.capture("north", parent.id, index)
    row = await records.find_by_id(identifier)
    row.native_workspace_id = "forged"
    with pytest.raises(DataIntegrityException):
        await records.save(row)
    with pytest.raises(DataIntegrityException):
        await records.delete_by_id(identifier)
    preserved = await records.find_by_id(identifier)
    assert preserved.native_workspace_id == "native"


@pytest.mark.parametrize(
    "changed",
    [
        "job_id",
        "provider_revision",
        "dimensions",
        "storage_dimensions",
        "mode_revision",
        "mode_id",
        "live_revision",
    ],
)
async def test_resolution_rejects_any_changed_admitted_index_pin(knowledge, changed):
    from koinon.organization_knowledge.transitions.index_attempts import ModeIndexAttemptRepository

    service = transitions(knowledge)
    parent = await service.request("admin", "north", update_input(), "pin-" + changed)
    records = ModeIndexAttemptRepository()
    index = SimpleNamespace(
        id="index",
        tenant_id="north",
        workspace_id=knowledge.workspace.id,
        native_workspace_id="native",
        native_id="set",
        revision=4,
        job_id="original-job",
        provider_id="provider",
        provider_revision=2,
        model_id="embedding",
        dimensions=768,
        storage_dimensions=768,
        embedding_fingerprint="fingerprint",
        updated_by="admin",
        access_token_id=None,
        transition={"request": {}, "previous_native_id": None},
    )
    async with primary_authority(read_only=False):
        identifier = await records.capture("north", parent.id, index)
        index.transition = {
            **index.transition,
            "mode_activation_attempt_id": identifier,
            "mode_activation_attempt_revision": 4,
        }
        index.revision = 5
        if changed == "mode_revision":
            index.transition["mode_activation_attempt_revision"] = 3
        elif changed == "mode_id":
            index.transition["mode_activation_attempt_id"] = "another-attempt"
        elif changed == "live_revision":
            index.revision = 4
        else:
            setattr(index, changed, "different-job" if changed == "job_id" else getattr(index, changed) + 1)
        with pytest.raises(ConflictException) as error:
            await records.resolve("north", parent.id, identifier, index, "finished", expected_revision=1)
        assert error.value.code == "INDEX_MODE_RECEIPT_CHANGED"
