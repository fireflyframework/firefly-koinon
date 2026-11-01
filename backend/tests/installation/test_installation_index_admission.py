# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock

import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config
from test_installation_manifest import example

from koinon.installation.authority import InstallationError, InstallationPermit
from koinon.installation.dtos import InstallationPlan
from koinon.installation.indexes import NativeInstallationIndexes


async def test_index_operator_capability_is_checked_before_domain_resolution(tmp_path):
    admissions, reader = AsyncMock(), AsyncMock()
    admissions.require.side_effect = InstallationError("INSTALLATION_OPERATOR_REQUIRED")
    writer = NativeInstallationIndexes(admissions, reader)
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'index.db'}",
                        }
                    },
                }
            }
        )
    )
    await context.start()
    try:
        with pytest.raises(InstallationError, match="INSTALLATION_OPERATOR_REQUIRED"):
            await writer.intent(
                InstallationPermit("run", "example", 1, "owner"),
                InstallationPlan.model_validate(example()).indexes[0],
            )
    finally:
        await context.stop()
    reader.get.assert_not_called()


@pytest.fixture
async def phases(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from koinon.installation.writes import resource_id
    from koinon.knowledge.connections.service import embedding_fingerprint
    from koinon.knowledge.indexes.adapters import index_id

    permit = InstallationPermit("owned-run", "example", 1, "owner")
    value = InstallationPlan.model_validate(example()).indexes[0]
    provider = SimpleNamespace(id="provider", revision=1, kind="openai", base_url="https://api.openai.com/v1")
    native = "es-" + resource_id(permit, "index:" + value.key).replace("-", "")
    row = SimpleNamespace(
        id=index_id("example", "workspace", "documents", native),
        tenant_id="example",
        workspace_id="workspace",
        native_workspace_id="workspace",
        created_by="system:installation",
        updated_by="system:installation",
        domain="documents",
        native_id=native,
        provider_id="provider",
        model_id=value.model_id,
        dimensions=1536,
        storage_dimensions=1536,
        provider_revision=1,
        embedding_fingerprint=embedding_fingerprint(provider, value.model_id, 1536, 1536),
        cursor={},
        revision=1,
        status="queued",
        build_slot="slot",
    )
    run = SimpleNamespace(
        checkpoints={
            "catalog:space": {"status": "done", "resource_id": "workspace"},
            "provider:embedding": {"status": "done", "resource_id": "provider"},
            "index-intent:documents": {
                "status": "done",
                "resource_id": row.id,
                "revision": 1,
                "row_status": "queued",
            },
        }
    )
    admission = AsyncMock()
    admission.require.return_value = run

    async def checkpoint(permit, key, value):
        run.checkpoints[key] = value

    admission.checkpoint.side_effect = checkpoint
    reader = AsyncMock()
    reader.records.find_by_id.return_value = row
    reader.planner.provider.return_value = provider
    reader.facade._workspace.return_value = SimpleNamespace(native_workspace_id="workspace")
    reader.adapter.overview.return_value = {"active_native_id": None, "chunk_count": 0}
    reader.adapter.discover.return_value = {"items": [], "total": 0}
    reader.adapter.create.return_value = "native-fingerprint"
    reader.adapter.coverage.return_value = {"chunk_count": 0, "vector_count": 0, "complete": True}
    reader.adapter.provision_document.return_value = True
    reader.connections.selected.return_value = None
    resolver = Mock()
    resolver.get.return_value = reader
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'phases.db'}",
                        }
                    },
                }
            }
        )
    )
    await context.start()
    try:
        yield NativeInstallationIndexes(admission, resolver), permit, value, run, reader, row
    finally:
        await context.stop()


async def test_created_phase_replay_does_not_allocate_another_native_target(phases):
    writer, permit, value, run, reader, row = phases
    await writer.create(permit, value)
    await writer.create(permit, value)
    reader.adapter.create.assert_awaited_once()
    assert row.cursor["native_config_fingerprint"] == "native-fingerprint"
    assert run.checkpoints["index-created:documents"]["revision"] == 2


async def test_nonempty_scope_or_foreign_pointer_never_creates_an_index(phases):
    writer, permit, value, _, reader, _ = phases
    for overview in (
        {"active_native_id": None, "chunk_count": 1},
        {"active_native_id": "manual-index", "chunk_count": 0},
    ):
        reader.adapter.overview.return_value = overview
        with pytest.raises(InstallationError, match="INSTALLATION_INDEX_NOT_EMPTY"):
            await writer.create(permit, value)
    reader.adapter.create.assert_not_called()


async def test_unqualified_ann_is_not_recorded_ready_or_activated(phases):
    writer, permit, value, run, reader, _ = phases
    await writer.create(permit, value)
    reader.adapter.get_native.return_value = {"indexed": False, "chunk_count": 0, "vector_count": 0}
    with pytest.raises(InstallationError, match="INSTALLATION_ANN_UNQUALIFIED"):
        await writer.ready(permit, value)
    assert "index-ready:documents" not in run.checkpoints
    reader.adapter.activate.assert_not_called()


async def test_manual_revision_change_fails_before_native_mutation(phases):
    writer, permit, value, _, reader, row = phases
    row.revision += 1
    with pytest.raises(InstallationError, match="INSTALLATION_MANUAL_CHANGE"):
        await writer.create(permit, value)
    reader.adapter.create.assert_not_called()
