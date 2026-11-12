# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real reader composition with a source graph accepted by the migrated schema."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from pyfly.data.transaction import current_unit_of_work
from sqlalchemy import update

from koinon.catalog.service import CatalogService
from koinon.evidence.reviews import digest
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.read_authority import SourceReadAuthority, source_authority
from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput
from koinon.integrations.content_sources.read_repository import SourceReadRepository
from koinon.integrations.content_sources.read_service import SourceReader
from koinon.integrations.content_sources.reader_access import RemoteReadObservation
from koinon.integrations.content_sources.reader_selection_repository import SourceReaderSelectionRepository
from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections
from koinon.integrations.content_sources.sync_entities import (
    SourceImportedVersion,
    SourceMappingPolicy,
    SourcePolicyOperation,
    SourceSyncState,
)
from koinon.knowledge.entities import DomainBinding


async def assistant_source_reader(context, imported_graph):
    sessions = await imported_graph(context)
    async with sessions.begin() as session:
        await session.execute(
            update(PersonalSourceConnection).values(
                issuer="https://accounts.google.com",
                config_fingerprint="f" * 64,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
        )
        connection = await session.get(PersonalSourceConnection, "connection")
        authority, fingerprint = source_authority(connection)
        operation_id, receipt_id = str(uuid4()), str(uuid4())
        expires = datetime.now(UTC) + timedelta(hours=1)
        session.add(
            SourceMappingPolicy(
                id="policy",
                tenant_id="north",
                owner="owner",
                mapping_id="mapping",
                revision=1,
                mapping_revision=1,
                authority_sha256=fingerprint,
                policy_json={"authority": authority},
                policy_sha256=digest({"authority": authority}),
                root_ancestry_json=["root"],
                review_id="policy-review",
                review_digest="a" * 64,
                review_expires_at=expires,
                accepted_by="owner",
                accepted_session_hash="b" * 64,
                accepted_operation_id=operation_id,
                accepted_at=datetime.now(UTC),
            )
        )
        await session.flush()
        session.add(
            SourcePolicyOperation(
                id=receipt_id,
                tenant_id="north",
                owner="owner",
                operation_id=operation_id,
                action="apply",
                mapping_id="mapping",
                policy_id="policy",
                expected_policy_revision=1,
                result_policy_revision=1,
                payload_sha256="e" * 64,
                result_json={
                    "schema": "koinon.source-policy-operation.v1",
                    "receipt_id": receipt_id,
                    "operation_id": operation_id,
                    "action": "apply",
                    "mapping_id": "mapping",
                    "policy_id": "policy",
                    "expected_policy_revision": 1,
                    "result_policy_revision": 1,
                    "review_digest": "a" * 64,
                    "review_expires_at": expires.isoformat(),
                    "disposition": "accepted",
                },
            )
        )
        await session.flush()
        session.add(
            SourceSyncState(
                mapping_id="mapping",
                tenant_id="north",
                accepted_policy_id="policy",
                enabled=False,
            )
        )
        await session.execute(update(SourceMapping).values(config_fingerprint="f" * 64))
        await session.execute(update(SourceObject).values(state="imported"))
        await session.execute(
            update(SourceImportAttempt).values(
                receipt_json={
                    "domain": "canon",
                    "native_workspace_id": "native-space",
                    "native_source_id": "native-doc",
                    "native_asset_id": "native-doc",
                    "source_version_id": "v1",
                    "extraction_id": "extraction",
                },
                committed_at=datetime.now(UTC),
            )
        )
        session.add(
            DomainBinding(
                id="binding",
                tenant_id="north",
                catalog_id="asset",
                workspace_id="workspace",
                domain="canon",
                entity_kind="document",
                native_id="native-doc",
                native_workspace_id="native-space",
                created_by="owner",
            )
        )
        session.add(
            SourceImportedVersion(
                attempt_id="attempt",
                tenant_id="north",
                source_id="source",
                asset_id="asset",
                domain="canon",
                native_workspace_id="native-space",
                native_source_id="native-doc",
                native_asset_id="native-doc",
                native_version_id="v1",
                extraction_id="extraction",
            )
        )

    class Remote:
        def __init__(self):
            self.calls = []
            self.trace_enabled = False
            self.traces = []
            self.connections = SimpleNamespace(
                registrations=SimpleNamespace(get=lambda provider: SimpleNamespace(fingerprint="f" * 64))
            )

        async def check(self, actor, tenant, connection, targets):
            unit = current_unit_of_work("primary")
            assert unit is None or unit.completed
            self.calls.append((actor, tenant, connection))
            if self.trace_enabled:
                import sys

                frame, labels, pins = sys._getframe(), {}, ()
                while frame is not None:
                    path, name = frame.f_code.co_filename, frame.f_code.co_name
                    if path.endswith("/read_authority.py") and name == "_check":
                        pins = tuple(
                            tuple(
                                getattr(pin, key, None)
                                for key in (
                                    "asset_id",
                                    "domain",
                                    "native_workspace_id",
                                    "native_source_id",
                                    "version_id",
                                    "extraction_id",
                                    "part_id",
                                )
                            )
                            for pin in frame.f_locals["pins"]
                        )
                    elif path.endswith("/source_model.py"):
                        labels["model"] = name
                    elif path.endswith("/run_sources.py") and name == "run_source_unit":
                        labels["queue"] = frame.f_locals.get("purpose", "read")
                    elif path.endswith("/memory/service.py"):
                        labels["memory"] = name
                    elif path.endswith("/execution.py") and name == "captured_call":
                        labels["tool"] = frame.f_locals.get("kind", "unknown")
                    elif path.endswith("/source_reads.py"):
                        labels["history"] = name
                    frame = frame.f_back
                boundary = next(
                    (
                        f"{kind}:{labels[kind]}"
                        for kind in ("model", "tool", "queue", "memory", "history")
                        if kind in labels
                    ),
                    "generation",
                )
                self.traces.append((boundary, connection, tuple(targets), pins))
            return tuple(RemoteReadObservation(target, datetime.now(UTC), 1) for target in targets)

    catalog = context.get_bean(CatalogService)
    records = context.get_bean(SourceReadRepository)
    selections = SourceReaderSelections(context.get_bean(SourceReaderSelectionRepository), catalog)
    await selections.replace(
        "owner",
        "north",
        ReaderSelectionInput(
            expected_revision=0,
            operation_id=uuid4(),
            connections=[{"provider": "google_drive", "connection_id": "connection"}],
        ),
    )
    remote = Remote()
    reader = SourceReader(SourceReadAuthority(records, remote, catalog), selections, records)
    return reader, sessions, remote
