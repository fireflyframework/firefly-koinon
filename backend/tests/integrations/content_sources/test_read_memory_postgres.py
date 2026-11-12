# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Stored-memory identities cannot cross owner, tenant or originating run boundaries."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_repository import SourceReadRepository

spec = importlib.util.spec_from_file_location(
    "reader_memory_fixture", Path(__file__).parents[2] / "exports/test_source_release_postgres.py"
)
assert spec and spec.loader
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
reviews = fixtures.reviews
postgres_reviews = fixtures.postgres_reviews
pytestmark = pytest.mark.integration


@pytest.fixture
async def remembered(reviews):
    from koinon.assistants.entities import (
        AgentConfiguration,
        ChatMessage,
        ChatRun,
        ChatThread,
        Provider,
        ToolResult,
    )
    from koinon.assistants.memory.entities import ChatMemoryManifest

    sessions = reviews[2].get_bean(DataSourceRegistry).primary.sessionmaker
    async with sessions.begin() as session:
        session.add(
            Provider(
                id="provider",
                tenant_id="north",
                name="Controlled",
                kind="openai",
                base_url="https://fixture.invalid",
            )
        )
        await session.flush()
        session.add(
            AgentConfiguration(
                id="agent", tenant_id="north", provider_id="provider", name="Agent", model_id="fixture"
            )
        )
        await session.flush()
        for run_id in ("one", "two"):
            session.add(ChatThread(id=run_id, tenant_id="north", subject="owner", title="Private title"))
            await session.flush()
            session.add_all(
                [
                    ChatMessage(id=run_id + "-user", thread_id=run_id, role="user", text="Private prompt"),
                    ChatMessage(
                        id=run_id + "-answer", thread_id=run_id, role="assistant", text="Private answer"
                    ),
                ]
            )
            await session.flush()
            session.add(
                ChatRun(
                    id=run_id,
                    tenant_id="north",
                    thread_id=run_id,
                    message_id=run_id + "-answer",
                    user_message_id=run_id + "-user",
                    agent_id="agent",
                    agent_revision=1,
                    provider_revision=1,
                    client_request_id=run_id,
                    payload_hash="a" * 64,
                )
            )
            await session.flush()
        session.add_all(
            [
                ToolResult(
                    id="result",
                    run_id="one",
                    kind="search",
                    payload={
                        "source_manifest": {
                            "complete": True,
                            "sources": [
                                {
                                    "id": "source",
                                    "asset_id": "asset",
                                    "kind": "document",
                                    "source_version_id": "version",
                                    "extraction_id": "extraction",
                                    "source_part_id": "part",
                                    "title": "Never hydrate",
                                    "quote": "Never hydrate text",
                                }
                            ],
                        }
                    },
                ),
                ToolResult(id="generation", run_id="two", kind="generation", payload={}),
            ]
        )
        await session.flush()
        session.add(
            ChatMemoryManifest(
                id="manifest",
                generation_id="generation",
                run_id="two",
                tenant_id="north",
                subject="owner",
                thread_id="two",
                policy_version=1,
                start_sequence=0,
                scope_sha256="b" * 64,
                manifest_sha256="c" * 64,
                manifest_json={
                    "dependencies": [
                        {
                            "run_id": "two",
                            "conversation_title": "Hidden",
                            "result_pins": [{"id": "result", "sha256": "d" * 64}],
                        }
                    ]
                },
                created_at=datetime.now(UTC),
            )
        )
    return sessions


async def test_source_projection_is_exact_and_wrong_owner_or_tenant_is_denied(remembered):
    async with remembered() as session:
        repository = SourceReadRepository(session=session)
        sources = await repository.result_references(
            "north", ("result",), owner="owner", expected_runs={"result": "one"}
        )
        assert len(sources) == 1 and sources[0].source_part_id == "part"
        assert not hasattr(sources[0], "title") and not hasattr(sources[0], "quote")
        for tenant, owner in (("south", "owner"), ("north", "other-reader")):
            with pytest.raises(SourceError, match="access_denied"):
                await repository.result_references(tenant, ("result",), owner=owner)


async def test_remembered_result_must_belong_to_recorded_dependency_run(remembered):
    binding = SimpleNamespace(run_id="two", generation_id="generation", manifest_sha256="c" * 64, results=())
    async with remembered() as session:
        with pytest.raises(SourceError, match="access_denied"):
            await SourceReadRepository(session=session).memory_references("north", (binding,), "owner")


async def test_incomplete_source_manifest_cannot_be_classified_as_local(remembered):
    from sqlalchemy import update

    from koinon.assistants.entities import ToolResult

    async with remembered.begin() as session:
        await session.execute(
            update(ToolResult)
            .where(ToolResult.id == "result")
            .values(payload={"source_manifest": {"complete": False, "sources": []}})
        )
    async with remembered() as session:
        with pytest.raises(SourceError, match="unavailable"):
            await SourceReadRepository(session=session).result_references("north", ("result",), owner="owner")


@pytest.mark.parametrize("sources", [None, {}, "invalid", [None], [{"kind": "unknown", "asset_id": "asset"}]])
async def test_malformed_source_provenance_is_denied_before_content(remembered, sources):
    from sqlalchemy import update

    from koinon.assistants.entities import ToolResult

    async with remembered.begin() as session:
        await session.execute(
            update(ToolResult)
            .where(ToolResult.id == "result")
            .values(payload={"source_manifest": {"complete": True, "sources": sources}})
        )
    async with remembered() as session:
        with pytest.raises(SourceError, match="unavailable"):
            await SourceReadRepository(session=session).result_references("north", ("result",), owner="owner")


async def test_curated_read_snapshot_has_no_provider_io_and_revocation_blocks_release(reviews):
    from pyfly.data.transaction import current_unit_of_work

    from koinon.integrations.content_sources.read_capabilities import curated_identity
    from koinon.integrations.content_sources.read_dtos import LocalSourcePin, ReaderSelectionSnapshot
    from koinon.integrations.content_sources.read_service import SourceReader
    from koinon.security.authority import PRIMARY_POLICY_UNIT

    revoked, observations = False, []

    class Authority:
        async def _check(self, *args):
            unit = current_unit_of_work("primary")
            assert unit is None or unit.completed, "Provider I/O entered the read snapshot"
            observations.append("remote")
            if revoked:
                raise SourceError("access_denied")
            return "comparison"

        async def _compare(self, actor, tenant, comparison):
            unit = current_unit_of_work("primary")
            assert unit is not None and unit.read_only and unit.definition.name == PRIMARY_POLICY_UNIT
            observations.append(("local", id(unit)))

    class Selections:
        async def resolve(self, *args):
            return ReaderSelectionSnapshot((), 0)

        async def confirm(self, *args):
            assert current_unit_of_work("primary") is None

        async def confirm_local(self, *args):
            assert current_unit_of_work("primary").read_only

    class Records:
        async def curated_state(self, *args):
            return SimpleNamespace(
                native_workspace_id="native-space",
                native_item_id="native-item",
                workspace_id="canonical-space",
                serving_version=1,
                head_version=1,
            )

    class Native:
        async def curated_version(self, *args):
            assert current_unit_of_work("primary") is None
            return "version"

    reader = SourceReader(Authority(), Selections(), Records(), SimpleNamespace(get=lambda: Native()))

    async def sources(actor, tenant, references, *, operation):
        assert references[0].knowledge_version_id == "version"
        await operation.check((LocalSourcePin("asset", "canon", "space", "source", "version", "extraction"),))
        return operation

    reader.sources = sources
    with pytest.raises(SourceError, match="access_denied"):
        async with reader.curated_read("owner", "north", (("item", 1),)):
            unit = current_unit_of_work("primary")
            assert observations[-1] == ("local", id(unit))
            assert curated_identity("owner", "north", "item", 1).version_id == "version"
            revoked = True
    assert observations[-1] == "remote"
    assert curated_identity("owner", "north", "item", 1) is None
