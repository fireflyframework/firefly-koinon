# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retained observations, work identities and encrypted cursors commit together."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select

from koinon.integrations.content_sources.dtos import bounded
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_entities import SourceObject
from koinon.integrations.content_sources.mapping_preview import available_extensions, import_choice
from koinon.integrations.content_sources.read_authority import source_authority
from koinon.integrations.content_sources.sync_entities import (
    SourceFolderPublication,
    SourceMappingPolicy,
    SourceSyncObservation,
    SourceSyncState,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_runs import SourceRunLease, SourceRunRepository, lost
from koinon.integrations.content_sources.sync_walk import WalkPage
from koinon.knowledge.bulk.ports import SourceIntakeItem


def event_hash(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@repository(name="content_sources.checkpoints")
class SourceCheckpoints(Repository[SourceSyncObservation, str]):
    async def append(
        self,
        lease: SourceRunLease,
        expected_page: int,
        page: WalkPage,
        *,
        cursor_ciphertext: bytes | None,
        at=None,
    ):
        """Caller holds canonical destination authority and owns the transaction.

        Remote reads and cursor encryption finish before entering this boundary.
        Completion here proves enumeration only; it never retires unseen imports.
        """
        if (
            type(expected_page) is not int
            or not 0 <= expected_page < 2147483646
            or len(page.items) > 100
            or type(page.raw_observed_count) is not int
            or not len(page.items) <= page.raw_observed_count <= 100
            or page.complete != (page.next_state is None)
            or page.complete != (cursor_ciphertext is None)
            or cursor_ciphertext is not None
            and (not isinstance(cursor_ciphertext, bytes) or not 1 <= len(cursor_ciphertext) <= 1024 * 1024)
        ):
            raise lost()
        session = self._require_session()
        runs = SourceRunRepository(session=session)
        connection, mapping, run = await runs.identity(lease.tenant_id, lease.owner, lease.run_id)
        current = await session.scalar(
            select(SourceSyncState)
            .where(SourceSyncState.mapping_id == mapping.id, SourceSyncState.tenant_id == lease.tenant_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        policy = await session.get(SourceMappingPolicy, run.policy_id)
        if (
            current is None
            or current.accepted_policy_id != run.policy_id
            or policy is None
            or policy.accepted_at is None
            or policy.authority_sha256 != source_authority(connection)[1]
            or current.scan_generation != run.scan_generation
            or current.scan_max_items is None
        ):
            raise lost()
        request = MappingReviewInput.model_validate(policy.policy_json["request"])
        available = available_extensions(request.mode)
        events = []
        for entry in page.items:
            item, ancestry = entry.item, entry.ancestry
            bounded(item.item_id)
            bounded(item.name)
            if item.version is not None:
                bounded(item.version, limit=2048)
            selected_file = (
                item.item_id == mapping.root_id
                and item.kind == "file"
                and not ancestry
                and not request.recursive
                and len(item.parents) == 1
                and item.parents[0] != item.item_id
                and len(page.items) == page.raw_observed_count == 1
                and page.complete
            )
            folder_child = (
                item.item_id != mapping.root_id
                and bool(ancestry)
                and ancestry[0] == mapping.root_id
                and len(ancestry) <= 256
                and len(set(ancestry)) == len(ancestry)
                and item.parents == (ancestry[-1],)
                and (request.recursive or len(ancestry) == 1)
            )
            if (
                item.scope.account.provider != mapping.provider
                or item.scope.account.subject != mapping.external_subject
                or item.scope.account.tenant_id != mapping.external_tenant
                or item.scope.drive_id != mapping.drive_id
                or not (selected_file or folder_child)
                or any(identifier in request.excluded_ids for identifier in (*ancestry, item.item_id))
            ):
                raise lost()
            for identifier in (*item.parents, *ancestry):
                bounded(identifier)
            payload = {"item": asdict(item), "ancestry": list(ancestry)}
            events.append((entry, payload, event_hash(payload)))
        if len({entry.item.item_id for entry in page.items}) != len(page.items):
            raise lost()
        existing = list(
            (
                await session.scalars(
                    select(SourceObject)
                    .where(
                        SourceObject.tenant_id == lease.tenant_id,
                        SourceObject.mapping_id == mapping.id,
                        SourceObject.item_id.in_([entry.item.item_id for entry in page.items]),
                    )
                    .order_by(SourceObject.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        # Jobs are locked after source objects, including on receipt-only replay.
        await runs.fenced(lease, at=at, publication=True)
        checkpoint = event_hash(
            {
                "page": expected_page,
                "events": [event[2] for event in events],
                "raw_observed_count": page.raw_observed_count,
                "complete": page.complete,
                "cursor_sha256": hashlib.sha256(cursor_ciphertext).hexdigest() if cursor_ciphertext else None,
            }
        )
        if run.counters_json.get("error_code") == "SOURCE_SCAN_LIMIT_EXCEEDED":
            if run.counters_json.get("checkpoint_sha256") != checkpoint:
                raise lost()
            return ()
        if run.page_sequence == expected_page + 1:
            rows = list(
                (
                    await session.scalars(
                        select(SourceSyncObservation)
                        .where(
                            SourceSyncObservation.run_id == run.id,
                            SourceSyncObservation.page_sequence == run.page_sequence,
                        )
                        .order_by(SourceSyncObservation.item_sequence)
                    )
                ).all()
            )
            if (
                run.cursor_ciphertext != cursor_ciphertext
                or run.counters_json.get("checkpoint_sha256") != checkpoint
                or run.enumeration_complete != page.complete
                or len(rows) != len(events)
                or any(row.event_sha256 != event[2] for row, event in zip(rows, events, strict=True))
            ):
                raise lost()
            return tuple(self.pin(row) for row in rows if row.remote_version is not None)
        if run.page_sequence != expected_page or run.enumeration_complete:
            raise lost()
        now = at or datetime.now(UTC)
        if page.raw_observed_count:
            current.scan_observed_count += page.raw_observed_count
            current.revision += 1
            current.updated_at = now
        if current.scan_observed_count > current.scan_max_items:
            # Preserve the previous safe checkpoint. The over-limit response is
            # accounted once, but cannot admit objects or establish absence.
            run.counters_json = {
                **run.counters_json,
                "error_code": "SOURCE_SCAN_LIMIT_EXCEEDED",
                "checkpoint_sha256": checkpoint,
            }
            run.status, run.updated_at = "reconciling", now
            await session.flush()
            return ()
        objects = {item.item_id: item for item in existing}
        published_folders = set(
            (
                await session.scalars(
                    select(SourceFolderPublication.object_id)
                    .where(
                        SourceFolderPublication.tenant_id == lease.tenant_id,
                        SourceFolderPublication.mapping_id == mapping.id,
                        SourceFolderPublication.object_id.in_([item.id for item in existing]),
                    )
                    .distinct()
                )
            ).all()
        )
        results = []
        for position, (entry, payload, digest) in enumerate(events):
            item, ancestry = entry.item, entry.ancestry
            origin = objects.get(item.item_id)
            structural = (item.parents[0], item.name, item.kind, list(ancestry))
            unchanged_committed = (
                origin is not None
                and origin.state == "imported"
                and (
                    origin.published_native_version_id is not None
                    or origin.remote_kind == "folder"
                    and origin.id in published_folders
                    and origin.published_local_revision is not None
                )
                and origin.published_sha256 is not None
                and origin.remote_version == item.version
                and origin.remote_kind == item.kind
                and origin.mapping_revision == mapping.revision
            )
            same_pending_generation = (
                origin is not None
                and origin.state in {"pending", "failed"}
                and origin.remote_version == item.version
                and origin.remote_kind == item.kind
                and origin.mapping_revision == mapping.revision
            )
            metadata_pending = (
                unchanged_committed
                and origin is not None
                and (
                    origin.remote_parent_id,
                    origin.remote_name,
                    origin.remote_kind,
                    origin.remote_ancestry_json,
                )
                != structural
            )
            if origin is None:
                origin = SourceObject(
                    id=str(uuid4()),
                    tenant_id=lease.tenant_id,
                    mapping_id=mapping.id,
                    item_id=item.item_id,
                    generation=1,
                    mapping_revision=mapping.revision,
                    remote_version=item.version,
                    state="pending",
                )
                session.add(origin)
            elif not unchanged_committed and not same_pending_generation:
                if origin.generation >= 2147483647:
                    raise lost()
                origin.generation += 1
                origin.mapping_revision, origin.remote_version, origin.state = (
                    mapping.revision,
                    item.version,
                    "pending",
                )
            elif same_pending_generation:
                # A fresh observation cannot discard an exact retained attempt or
                # known native receipt. Publication still needs this observation.
                origin.state = "pending"
            if not metadata_pending:
                (
                    origin.remote_parent_id,
                    origin.remote_name,
                    origin.remote_kind,
                    origin.remote_ancestry_json,
                ) = structural
            origin.updated_at = now
            await session.flush()
            work = await session.scalar(
                select(SourceSyncWork).where(
                    SourceSyncWork.tenant_id == lease.tenant_id,
                    SourceSyncWork.object_id == origin.id,
                    SourceSyncWork.generation == origin.generation,
                )
            )
            if work is None:
                work = SourceSyncWork(
                    id=str(uuid4()),
                    tenant_id=lease.tenant_id,
                    mapping_id=mapping.id,
                    object_id=origin.id,
                    generation=origin.generation,
                    remote_version=item.version,
                    event_sha256=digest,
                    status="admitted",
                    error_code=None,
                    attempt_id=None,
                    expected_local_revision=origin.published_local_revision,
                    expected_sha256=origin.published_sha256,
                )
                session.add(work)
                await session.flush()
            choice = import_choice(item, request, available)
            if choice.reason is not None:
                work.status, work.error_code = "skipped", choice.reason
            elif metadata_pending:
                work.status, work.error_code = "admitted", "SOURCE_METADATA_PENDING"
            elif unchanged_committed:
                work.status, work.error_code = "imported", None
            observation = SourceSyncObservation(
                id=str(uuid4()),
                tenant_id=lease.tenant_id,
                mapping_id=mapping.id,
                run_id=run.id,
                page_sequence=expected_page + 1,
                item_sequence=position,
                object_id=origin.id,
                generation=origin.generation,
                remote_version=item.version,
                event_json=payload,
                event_sha256=digest,
                work_id=work.id,
                observed_at=now,
            )
            session.add(observation)
            await session.flush()
            if item.version is not None:
                results.append(self.pin(observation))
        run.page_sequence += 1
        run.cursor_ciphertext, run.enumeration_complete, run.updated_at = (
            cursor_ciphertext,
            page.complete,
            now,
        )
        run.counters_json = {
            **run.counters_json,
            "observed": run.counters_json.get("observed", 0) + len(events),
            "checkpoint_sha256": checkpoint,
        }
        await session.flush()
        return tuple(results)

    @staticmethod
    def pin(row):
        return SourceIntakeItem(
            row.object_id,
            row.generation,
            row.remote_version,
            row.id,
            row.work_id,
            row.page_sequence,
            row.item_sequence,
            row.event_sha256,
        )
