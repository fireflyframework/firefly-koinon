# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owner-authorized mapping commands keep remote I/O outside local effects."""

import asyncio
import base64
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pyfly.container import service
from pyfly.kernel import InvalidRequestException
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from koinon.catalog.entities import CatalogEntry
from koinon.integrations.content_sources.browse import PersonalSourceBrowser
from koinon.integrations.content_sources.dtos import Account, RemoteItem, SourceScope
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.lifecycle import SourceConnectionService, _no_remote_unit
from koinon.integrations.content_sources.mapping_ancestry import FolderAncestry
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.mapping_repository import SourceMappingRepository
from koinon.integrations.content_sources.read_authority import source_authority
from koinon.integrations.content_sources.reader_access import _OperationToken
from koinon.integrations.content_sources.sync_controls import (
    SourceControlRepository,
    SyncAuthorityCapture,
    control_digest,
)
from koinon.integrations.content_sources.sync_dtos import (
    ControlAction,
    SourceControlInput,
    SourceControlOutput,
    SourceControlReceipt,
    SourceDestinationPresentation,
    SourceDestinationSegment,
    SourceMappingOutput,
    SourceMappingPresentation,
    SourcePolicyOperationOutput,
    SourcePolicyReceipt,
    SourceRunItem,
    SourceRunItemPage,
    SourceRunOutput,
)
from koinon.integrations.content_sources.sync_entities import (
    SourceControlOperation,
    SourceFolderPublication,
    SourceImportedVersion,
    SourceMappingPolicy,
    SourcePolicyOperation,
    SourceSyncObservation,
    SourceSyncRun,
    SourceSyncState,
    SourceSyncWork,
)
from koinon.jobs.errors import JobConflict
from koinon.knowledge.bulk.authority import BulkAuthority
from koinon.knowledge.bulk.dtos import BulkDestination
from koinon.knowledge.bulk.entities import BulkItem
from koinon.security.authority import primary_authority


@service(name="content_sources.mappings")
class SourceMappings:
    def __init__(
        self,
        authority: BulkAuthority,
        connections: SourceConnectionService,
        browser: PersonalSourceBrowser,
        mappings: SourceMappingRepository,
        controls: SourceControlRepository,
    ):
        self.authority, self.connections, self.browser = authority, connections, browser
        self.mappings, self.controls = mappings, controls

    @staticmethod
    def destination(mapping):
        return BulkDestination(
            workspace_id=mapping.workspace_id, project_id=mapping.project_id, parent_id=mapping.parent_id
        )

    def _page(self, actor, tenant, scope, cursor, limit):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise InvalidRequestException(
                "Use a page size from 1 through 100", code="SOURCE_INVALID_PARAMETER"
            )
        if cursor is None:
            return None
        try:
            if not isinstance(cursor, str) or len(cursor) > 4096:
                raise ValueError
            payload = self.connections.vault.decrypt(
                tenant,
                actor,
                scope,
                "source-status-page",
                base64.b64decode(cursor, altchars=b"-_", validate=True),
            )
            if datetime.fromisoformat(payload["expires"]) <= datetime.now(UTC) or not isinstance(
                payload["after"], str
            ):
                raise ValueError
            return payload["after"]
        except Exception:
            raise SourceError("invalid_cursor") from None

    def _next(self, actor, tenant, scope, after):
        return base64.urlsafe_b64encode(
            self.connections.vault.encrypt(
                tenant,
                actor,
                scope,
                "source-status-page",
                {"after": after, "expires": (datetime.now(UTC) + timedelta(minutes=15)).isoformat()},
            )
        ).decode()

    async def _read_scope(self, actor, tenant, identifier):
        mapping = await self.mappings.owned(tenant, actor, identifier)
        if mapping is None:
            raise SourceError("access_denied")
        await self.authority.destination(actor, tenant, self.destination(mapping), write=False)
        session = self.controls._require_session()
        state = await session.get(SourceSyncState, identifier)
        latest = await session.scalar(
            select(SourceMappingPolicy)
            .where(SourceMappingPolicy.tenant_id == tenant, SourceMappingPolicy.mapping_id == identifier)
            .order_by(SourceMappingPolicy.revision.desc())
            .limit(1)
        )
        policy = await session.get(SourceMappingPolicy, state.accepted_policy_id) if state else latest
        if latest is None or policy is None or policy.owner != actor:
            raise SourceError("unavailable")
        return mapping, state, policy, latest

    @asynccontextmanager
    async def authorized(self, actor, tenant, identifier):
        _no_remote_unit()
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(fresh=True):
            mapping, _, policy, _ = await self._read_scope(actor, tenant, identifier)
            original = (mapping.revision, policy.id, policy.policy_sha256)
        capture = await self.remote_capture(actor, tenant, mapping, policy)
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(fresh=True):
            mapping, state, policy, latest = await self._read_scope(actor, tenant, identifier)
            connection = await self.connections.connections.owned(tenant, actor, mapping.connection_id)
            if (
                connection is None
                or connection.revision != capture.connection_revision
                or connection.status != "connected"
                or connection.refresh_operation is not None
                or original != (mapping.revision, policy.id, policy.policy_sha256)
            ):
                raise SourceError("authority_changed")
            yield mapping, state, policy, latest

    async def get(self, actor, tenant, identifier):
        _no_remote_unit()
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(fresh=True):
            mapping, _, policy, latest = await self._read_scope(actor, tenant, identifier)
            connection = await self.connections.connections.owned(tenant, actor, mapping.connection_id)
            if connection is None:
                raise SourceError("access_denied")
            snapshot = (mapping.revision, mapping.status, policy.id, policy.policy_sha256, latest.revision)
            connection_revision = connection.revision
        presentation = SourceMappingPresentation()
        try:
            root, connection_revision = await self.connections.presentation.source_root(
                actor, tenant, mapping, policy, self.connections, self.browser
            )
            presentation = SourceMappingPresentation(source_root=root)
        except SourceError as error:
            presentation = SourceMappingPresentation(
                unavailable_reason=(
                    "access_denied"
                    if error.code == "access_denied"
                    else "reconnect_required"
                    if error.code == "reconnect_required"
                    else "unavailable"
                )
            )
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(fresh=True):
            mapping, state, policy, latest = await self._read_scope(actor, tenant, identifier)
            connection = await self.connections.connections.owned(tenant, actor, mapping.connection_id)
            if (
                snapshot
                != (mapping.revision, mapping.status, policy.id, policy.policy_sha256, latest.revision)
                or connection is None
                or connection.revision != connection_revision
            ):
                raise SourceError("authority_changed")
            if presentation.unavailable_reason is None:
                destination = await self.connections.presentation.destination(
                    actor, tenant, self.destination(mapping)
                )
                presentation = presentation.model_copy(update={"destination": destination})
            active = await self.controls._require_session().scalar(
                select(SourceSyncRun.id)
                .where(
                    SourceSyncRun.tenant_id == tenant,
                    SourceSyncRun.mapping_id == identifier,
                    SourceSyncRun.status.in_(("queued", "running", "reconciling")),
                )
                .limit(1)
            )
            return SourceMappingOutput(
                id=mapping.id,
                revision=mapping.revision,
                policy_revision=policy.revision if state else None,
                latest_review_revision=latest.revision,
                control_revision=state.revision if state else None,
                connection_id=mapping.connection_id,
                policy=MappingReviewInput.model_validate(policy.policy_json["request"]),
                presentation=presentation,
                status=mapping.status,
                next_run_at=state.next_run_at if state else None,
                can_pause=state is not None and mapping.status == "active",
                can_resume=state is not None and mapping.status == "paused",
                can_retire=state is not None and mapping.status != "retired",
                can_sync=state is not None
                and mapping.status == "active"
                and active is None
                and presentation.unavailable_reason is None,
            )

    async def list(self, actor, tenant, *, cursor=None, limit=25):
        _no_remote_unit()
        after = self._page(actor, tenant, "mappings", cursor, limit)
        await self.connections._authorize(actor, tenant)
        async with primary_authority(fresh=True):
            rows = await self._mapping_page_rows(actor, tenant, after=after, limit=limit + 1)
            snapshots = {}
            for mapping, state, latest, accepted, connection in rows[:limit]:
                await self.authority.destination(actor, tenant, self.destination(mapping), write=False)
                policy = accepted if state else latest
                if policy is None or connection is None or latest is None:
                    raise SourceError("unavailable")
                snapshots[mapping.id] = (
                    mapping.revision,
                    mapping.status,
                    policy.id,
                    policy.policy_sha256,
                    latest.revision,
                    connection.revision,
                )
            candidates = tuple(rows[:limit])
            continuation = (
                self._next(actor, tenant, "mappings", rows[limit - 1][0].id) if len(rows) > limit else None
            )
        presentations, revisions = {}, {}
        slots = asyncio.Semaphore(4)

        async def capture(row):
            mapping, state, latest, accepted, connection = row
            async with slots:
                try:
                    root, revision = await self.connections.presentation.source_root(
                        actor, tenant, mapping, accepted if state else latest, self.connections, self.browser
                    )
                    presentations[mapping.id] = SourceMappingPresentation(source_root=root)
                    revisions[mapping.id] = revision
                except SourceError as error:
                    presentations[mapping.id] = SourceMappingPresentation(
                        unavailable_reason=(
                            "access_denied"
                            if error.code == "access_denied"
                            else "reconnect_required"
                            if error.code == "reconnect_required"
                            else "unavailable"
                        )
                    )
                    revisions[mapping.id] = connection.revision

        try:
            async with asyncio.timeout(120):
                results = await asyncio.gather(*(capture(row) for row in candidates), return_exceptions=True)
                for result in results:
                    if isinstance(result, BaseException):
                        raise result
        except TimeoutError:
            raise SourceError("timeout") from None
        await self.connections._authorize(actor, tenant)
        async with primary_authority(fresh=True):
            current = await self._mapping_page_rows(actor, tenant, identifiers=tuple(snapshots), limit=limit)
            if len(current) != len(candidates):
                raise SourceError("authority_changed")
            items = []
            for mapping, state, latest, accepted, connection in current:
                policy = accepted if state else latest
                snapshot = snapshots[mapping.id]
                if (
                    policy is None
                    or connection is None
                    or latest is None
                    or snapshot[:5]
                    != (mapping.revision, mapping.status, policy.id, policy.policy_sha256, latest.revision)
                    or connection.revision != revisions[mapping.id]
                ):
                    raise SourceError("authority_changed")
                chain = await self.authority.destination(
                    actor, tenant, self.destination(mapping), write=False
                )
                presentation = presentations[mapping.id]
                if presentation.unavailable_reason is None:
                    presentation = presentation.model_copy(
                        update={
                            "destination": SourceDestinationPresentation(
                                segments=[
                                    SourceDestinationSegment(id=row.id, kind=row.kind, name=row.name)
                                    for row in reversed(chain)
                                ]
                            )
                        }
                    )
                items.append(
                    {
                        "id": mapping.id,
                        "status": mapping.status,
                        "connection_id": mapping.connection_id,
                        "policy_revision": mapping.revision if state else None,
                        "latest_review_revision": latest.revision,
                        "control_revision": state.revision if state else None,
                        "next_run_at": state.next_run_at.isoformat() if state and state.next_run_at else None,
                        "presentation": presentation.model_dump(mode="json"),
                    }
                )
            return {"items": items, "next_cursor": continuation}

    async def _mapping_page_rows(self, actor, tenant, *, after=None, identifiers=None, limit):
        latest, accepted = aliased(SourceMappingPolicy), aliased(SourceMappingPolicy)
        latest_revision = (
            select(func.max(SourceMappingPolicy.revision))
            .where(
                SourceMappingPolicy.tenant_id == tenant,
                SourceMappingPolicy.mapping_id == SourceMapping.id,
            )
            .correlate(SourceMapping)
            .scalar_subquery()
        )
        query = (
            select(SourceMapping, SourceSyncState, latest, accepted, PersonalSourceConnection)
            .outerjoin(
                SourceSyncState,
                (SourceSyncState.mapping_id == SourceMapping.id) & (SourceSyncState.tenant_id == tenant),
            )
            .outerjoin(
                latest,
                (latest.mapping_id == SourceMapping.id)
                & (latest.tenant_id == tenant)
                & (latest.revision == latest_revision),
            )
            .outerjoin(
                accepted, (accepted.id == SourceSyncState.accepted_policy_id) & (accepted.tenant_id == tenant)
            )
            .outerjoin(
                PersonalSourceConnection,
                (PersonalSourceConnection.id == SourceMapping.connection_id)
                & (PersonalSourceConnection.tenant_id == tenant)
                & (PersonalSourceConnection.owner == actor),
            )
            .where(SourceMapping.tenant_id == tenant, SourceMapping.owner == actor)
        )
        if after is not None:
            query = query.where(SourceMapping.id > after)
        if identifiers is not None:
            query = query.where(SourceMapping.id.in_(identifiers))
        return list(
            (
                await self.controls._require_session().execute(
                    query.order_by(SourceMapping.id).limit(limit).execution_options(populate_existing=True)
                )
            ).all()
        )

    async def run_mapping(self, actor, tenant, identifier):
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(fresh=True):
            row = await self.controls._require_session().scalar(
                select(SourceSyncRun)
                .join(SourceMapping, SourceMapping.id == SourceSyncRun.mapping_id)
                .where(
                    SourceSyncRun.id == identifier,
                    SourceSyncRun.tenant_id == tenant,
                    SourceMapping.tenant_id == tenant,
                    SourceMapping.owner == actor,
                )
            )
            if row is None:
                raise SourceError("access_denied")
            await self._read_scope(actor, tenant, row.mapping_id)
            return row.mapping_id

    async def initial_operation(self, actor, tenant, operation_id, action):
        if action != "review":
            raise SourceError("access_denied")
        try:
            if str(UUID(operation_id)) != operation_id:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise SourceError("access_denied") from None
        await self.connections._authorize(actor, tenant)
        async with primary_authority(fresh=True):
            mapping_id = await self.controls._require_session().scalar(
                select(SourcePolicyOperation.mapping_id).where(
                    SourcePolicyOperation.tenant_id == tenant,
                    SourcePolicyOperation.owner == actor,
                    SourcePolicyOperation.operation_id == operation_id,
                    SourcePolicyOperation.action == "review",
                )
            )
        if mapping_id is None:
            raise SourceError("access_denied")
        return await self.operation(actor, tenant, mapping_id, operation_id, action)

    async def operation(self, actor, tenant, mapping_id, operation_id, action):
        try:
            if str(UUID(operation_id)) != operation_id:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise SourceError("access_denied") from None
        if action not in {"review", "apply", "sync", "pause", "resume", "cancel", "retry", "retire"}:
            raise SourceError("access_denied")
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(fresh=True):
            await self._read_scope(actor, tenant, mapping_id)
            model = SourcePolicyOperation if action in {"review", "apply"} else SourceControlOperation
            row = await self.controls._require_session().scalar(
                select(model).where(
                    model.tenant_id == tenant,
                    model.owner == actor,
                    model.mapping_id == mapping_id,
                    model.operation_id == operation_id,
                    model.action == action,
                )
            )
            if row is None:
                raise SourceError("access_denied")
            if isinstance(row, SourcePolicyOperation):
                receipt = SourcePolicyOperationOutput.model_validate(row.result_json)
                if (receipt.mapping_id, receipt.policy_id, receipt.result_policy_revision) != (
                    row.mapping_id,
                    row.policy_id,
                    row.result_policy_revision,
                ):
                    raise SourceError("access_denied")
                result = SourcePolicyReceipt(receipt=receipt)
            else:
                receipt = SourceControlOutput.model_validate(row.result_json)
                if receipt.control_revision != row.result_revision:
                    raise SourceError("access_denied")
                result = SourceControlReceipt(receipt=receipt)
            if (receipt.receipt_id, receipt.operation_id, receipt.action) != (row.id, operation_id, action):
                raise SourceError("access_denied")
            return result

    @staticmethod
    def _run_output(run, state):
        return SourceRunOutput(
            id=run.id,
            mapping_id=run.mapping_id,
            policy_revision=run.mapping_revision,
            control_revision=state.revision,
            status=run.status,
            stopping=run.cancel_requested_at is not None,
            retry_of_run_id=run.retry_of_run_id,
            counters=run.counters_json,
            enumeration_complete=run.enumeration_complete,
            created_at=run.created_at,
            finished_at=run.finished_at,
            can_cancel=run.status in {"queued", "running", "reconciling"} and run.cancel_requested_at is None,
            can_retry=run.status in {"failed", "partial", "reconnect_required", "cancelled"},
        )

    async def run(self, actor, tenant, identifier):
        mapping_id = await self.run_mapping(actor, tenant, identifier)
        # Counts derive from source observations and require current source authorization.
        async with self.authorized(actor, tenant, mapping_id) as (_, state, _, _):
            row = await self.controls._require_session().get(SourceSyncRun, identifier)
            if row is None or state is None:
                raise SourceError("unavailable")
            return self._run_output(row, state)

    async def runs(self, actor, tenant, mapping_id, *, cursor=None, limit=25):
        after = self._page(actor, tenant, "runs:" + mapping_id, cursor, limit)
        async with self.authorized(actor, tenant, mapping_id) as (_, state, _, _):
            if state is None:
                return {"items": [], "next_cursor": None}
            query = select(SourceSyncRun).where(
                SourceSyncRun.tenant_id == tenant, SourceSyncRun.mapping_id == mapping_id
            )
            if after is not None:
                query = query.where(SourceSyncRun.id > after)
            rows = list(
                (
                    await self.controls._require_session().scalars(
                        query.order_by(SourceSyncRun.id).limit(limit + 1)
                    )
                ).all()
            )
            return {
                "items": [self._run_output(row, state).model_dump(mode="json") for row in rows[:limit]],
                "next_cursor": self._next(actor, tenant, "runs:" + mapping_id, rows[limit - 1].id)
                if len(rows) > limit
                else None,
            }

    async def run_items(self, actor, tenant, run_id, *, cursor=None, limit=25):
        """Scan bounded identities first; hydrate no history for denied provider items."""
        after = self._page(actor, tenant, "run-items:" + run_id, cursor, limit)
        mapping_id = await self.run_mapping(actor, tenant, run_id)
        async with self.authorized(actor, tenant, mapping_id) as (mapping, _, policy, _):
            snapshot = (mapping.revision, policy.id, policy.policy_sha256)
            account = Account(mapping.provider, mapping.external_subject, mapping.external_tenant)
            scope = SourceScope(account, mapping.drive_id)
            connection_id, root = mapping.connection_id, mapping.root_id
            query = (
                select(
                    SourceSyncWork.id,
                    SourceSyncWork.object_id,
                    SourceSyncWork.generation,
                    SourceSyncWork.remote_version,
                    SourceObject.item_id,
                )
                .join(SourceObject, SourceObject.id == SourceSyncWork.object_id)
                .where(
                    SourceSyncWork.tenant_id == tenant,
                    SourceSyncWork.mapping_id == mapping_id,
                    SourceObject.tenant_id == tenant,
                    select(SourceSyncObservation.id)
                    .where(
                        SourceSyncObservation.tenant_id == tenant,
                        SourceSyncObservation.run_id == run_id,
                        SourceSyncObservation.work_id == SourceSyncWork.id,
                    )
                    .exists(),
                )
            )
            if after is not None:
                query = query.where(SourceSyncWork.id > after)
            candidates = (
                await self.controls._require_session().execute(
                    query.order_by(SourceSyncWork.id).limit(limit + 1)
                )
            ).all()
        continuation = (
            self._next(actor, tenant, "run-items:" + run_id, candidates[limit - 1].id)
            if len(candidates) > limit
            else None
        )
        candidates = candidates[:limit]
        grant = await self.connections.read_grant(actor, tenant, connection_id, account)
        allowed, folders = {}, {}
        slots = asyncio.Semaphore(4)
        try:
            async with (
                asyncio.timeout(120),
                self.browser._source(scope, _OperationToken(account, grant.token)) as adapter,
            ):

                async def read(candidate):
                    try:
                        async with slots:
                            item = await adapter.get_item(candidate.item_id)
                            if item.kind == "file":
                                item = await adapter.check_access(candidate.item_id)
                            if item.scope != scope or item.item_id != candidate.item_id:
                                raise SourceError("scope_mismatch")
                            if item.version != candidate.remote_version:
                                raise SourceError("version_changed")
                            if len(item.parents) != 1:
                                raise SourceError("invalid_response")
                            allowed[candidate.id] = item
                    except SourceError as error:
                        if error.code != "access_denied" and not error.definitive_read_denial:
                            raise

                async def complete(calls):
                    results = await asyncio.gather(*calls, return_exceptions=True)
                    for result in results:
                        if isinstance(result, BaseException):
                            raise result

                await complete(read(candidate) for candidate in candidates)

                async def folder(identifier):
                    if identifier not in folders:
                        folders[identifier] = await adapter.get_item(identifier)
                    return folders[identifier]

                class AuthorizedFolders:
                    async def root(self) -> RemoteItem:
                        return await adapter.root()

                    async def get_item(self, item_id: str) -> RemoteItem:
                        return await folder(item_id)

                # Each path segment comes from an authorized current folder read.
                paths = {}
                for identifier, item in tuple(allowed.items()):
                    try:
                        proof = await FolderAncestry(AuthorizedFolders(), scope, max_depth=256).capture(
                            (item.parents[0],)
                        )
                        reverse = (item.parents[0], *proof.ancestors(item.parents[0]))
                        if root not in reverse:
                            allowed.pop(identifier)
                            continue
                        parents = tuple(reversed(reverse[: reverse.index(root)]))
                        paths[identifier] = [*(folders[parent].name for parent in parents), item.name]
                    except SourceError as error:
                        if error.code == "access_denied" or error.definitive_read_denial:
                            allowed.pop(identifier)
                        else:
                            raise

                # Changed metadata or a late denied ancestor cannot escape with a previous proof.
                async def confirm(item):
                    async with slots:
                        current = (
                            await adapter.check_access(item.item_id)
                            if item.kind == "file"
                            else await adapter.get_item(item.item_id)
                        )
                        if current != item:
                            raise SourceError("version_changed")

                await complete(confirm(item) for item in (*allowed.values(), *folders.values()))
        except TimeoutError:
            raise SourceError("timeout") from None
        await self.connections.confirm_read_grant(actor, tenant, connection_id, grant)
        async with self.authorized(actor, tenant, mapping_id) as (mapping, _, policy, _):
            if snapshot != (mapping.revision, policy.id, policy.policy_sha256):
                raise SourceError("authority_changed")
            connection = await self.connections.connections.owned(tenant, actor, connection_id)
            if connection is None or connection.revision != grant.revision:
                raise SourceError("authority_changed")
            rows = await self._run_item_states(tenant, mapping_id, tuple(allowed))
            published_folders = await self._published_folders(tenant, tuple(allowed))
            expected = {candidate.id: candidate for candidate in candidates}
            output = []
            for row in rows:
                (
                    work,
                    origin_generation,
                    origin_version,
                    origin_state,
                    published_version,
                    published_hash,
                    attempt_id,
                    source_id,
                    asset_id,
                    digest,
                    native_version,
                    bulk_status,
                    catalog_status,
                ) = row
                candidate, item = expected[work.id], allowed[work.id]
                if (work.object_id, work.generation, work.remote_version) != (
                    candidate.object_id,
                    candidate.generation,
                    candidate.remote_version,
                ) or (origin_generation, origin_version) != (candidate.generation, candidate.remote_version):
                    raise SourceError("authority_changed")
                status = self._item_status(
                    work,
                    item.kind,
                    native_version,
                    published_version,
                    digest,
                    published_hash,
                    bulk_status,
                    catalog_status,
                    origin_state,
                )
                if item.kind == "folder" and work.status == "imported":
                    status = "synchronized" if work.id in published_folders else "indeterminate"
                safe_codes = {
                    "SOURCE_FORMAT_UNSUPPORTED",
                    "SOURCE_FORMAT_UNSELECTED",
                    "SOURCE_PARSER_UNAVAILABLE",
                    "SOURCE_DOWNLOAD_DENIED",
                    "SOURCE_NAME_UNSUPPORTED",
                    "SOURCE_HIERARCHY_FLATTENED",
                    "SOURCE_LOCAL_CONFLICT",
                    "SOURCE_MEMBER_REVIEW_REQUIRED",
                    "SOURCE_METADATA_PENDING",
                    "SOURCE_PROCESSING_FAILED",
                    "SOURCE_NATIVE_OUTCOME_UNRESOLVED",
                }
                output.append(
                    SourceRunItem(
                        id=work.id,
                        object_id=work.object_id,
                        generation=work.generation,
                        remote_version=work.remote_version,
                        kind=item.kind if item.kind in {"file", "folder"} else "unknown",
                        name=item.name,
                        relative_path=paths[work.id],
                        status=status,
                        error_code=(
                            work.error_code if work.error_code in safe_codes else "SOURCE_ITEM_FAILED"
                        )
                        if work.error_code
                        else None,
                        source_id=source_id,
                        asset_id=asset_id,
                        attempt_id=attempt_id,
                        updated_at=work.updated_at,
                    )
                )
            if len(output) != len(allowed):
                raise SourceError("authority_changed")
            return SourceRunItemPage(items=output, next_cursor=continuation)

    async def _run_item_states(self, tenant, mapping_id, identifiers):
        return (
            await self.controls._require_session().execute(
                select(
                    SourceSyncWork,
                    SourceObject.generation,
                    SourceObject.remote_version,
                    SourceObject.state,
                    SourceObject.published_native_version_id,
                    SourceObject.published_sha256,
                    SourceImportAttempt.id,
                    SourceImportAttempt.source_id,
                    SourceImportAttempt.asset_id,
                    SourceImportAttempt.sha256,
                    SourceImportedVersion.native_version_id,
                    BulkItem.status,
                    CatalogEntry.status,
                )
                .join(SourceObject, SourceObject.id == SourceSyncWork.object_id)
                .outerjoin(SourceImportAttempt, SourceImportAttempt.id == SourceSyncWork.attempt_id)
                .outerjoin(SourceImportedVersion, SourceImportedVersion.attempt_id == SourceImportAttempt.id)
                .outerjoin(BulkItem, BulkItem.id == SourceImportAttempt.intake_item_id)
                .outerjoin(CatalogEntry, CatalogEntry.id == SourceImportAttempt.asset_id)
                .where(
                    SourceSyncWork.tenant_id == tenant,
                    SourceSyncWork.mapping_id == mapping_id,
                    SourceSyncWork.id.in_(identifiers),
                )
                .order_by(SourceSyncWork.id)
            )
        ).all()

    async def _published_folders(self, tenant, identifiers):
        return set(
            await self.controls._require_session().scalars(
                select(SourceFolderPublication.work_id)
                .join(CatalogEntry, CatalogEntry.id == SourceFolderPublication.local_folder_id)
                .join(SourceObject, SourceObject.id == SourceFolderPublication.object_id)
                .where(
                    SourceFolderPublication.tenant_id == tenant,
                    SourceFolderPublication.work_id.in_(identifiers),
                    CatalogEntry.status == "ready",
                    CatalogEntry.mutation_revision == SourceFolderPublication.canonical_revision,
                    SourceObject.published_sha256 == SourceFolderPublication.canonical_sha256,
                )
            )
        )

    @staticmethod
    def _item_status(
        work,
        kind,
        native_version,
        published_version,
        digest,
        published_hash,
        bulk_status,
        catalog_status,
        origin_state,
    ):
        if work.status in {"skipped", "conflict", "retired", "failed"}:
            return work.status
        if bulk_status == "reconciling":
            return "indeterminate"
        if (
            kind == "file"
            and work.status == "imported"
            and native_version
            and native_version == published_version
            and digest == published_hash
            and catalog_status == "ready"
            and origin_state == "imported"
        ):
            return "searchable"
        if work.status == "imported" or bulk_status == "succeeded":
            return "indeterminate"
        if bulk_status == "awaiting_upload":
            return "downloading"
        if bulk_status in {"staged", "queued", "running"}:
            return "processing"
        if bulk_status == "failed":
            return "failed"
        return "observed"

    async def _scope(self, actor, tenant, identifier, *, write=False):
        mapping = await self.mappings.owned(tenant, actor, identifier)
        if mapping is None:
            raise SourceError("access_denied")
        await self.authority.destination(actor, tenant, self.destination(mapping), write=write)
        state = await self.controls._require_session().get(SourceSyncState, identifier)
        if state is None or state.tenant_id != tenant:
            raise SourceError("unavailable")
        policy = await self.controls._require_session().get(SourceMappingPolicy, state.accepted_policy_id)
        if (
            policy is None
            or policy.tenant_id != tenant
            or policy.owner != actor
            or policy.accepted_at is None
        ):
            raise SourceError("access_denied")
        return mapping, state, policy

    async def _receipt(self, actor, tenant, operation):
        return await self.controls._require_session().scalar(
            select(SourceControlOperation).where(
                SourceControlOperation.tenant_id == tenant,
                SourceControlOperation.owner == actor,
                SourceControlOperation.operation_id == operation,
            )
        )

    async def remote_capture(self, actor, tenant, mapping, policy) -> SyncAuthorityCapture:
        _no_remote_unit()
        account = Account(mapping.provider, mapping.external_subject, mapping.external_tenant)
        grant = await self.connections.read_grant(actor, tenant, mapping.connection_id, account)
        scope = SourceScope(account, mapping.drive_id)
        async with self.browser._source(scope, _OperationToken(account, grant.token)) as adapter:
            proof = await FolderAncestry(adapter, scope).capture((mapping.root_id,))
        await self.connections.confirm_read_grant(actor, tenant, mapping.connection_id, grant)
        if (
            tuple(policy.root_ancestry_json) != (mapping.root_id, *proof.ancestors(mapping.root_id))
            or proof.root_kind(mapping.root_id) != policy.policy_json.get("root_kind", "folder")
        ):
            raise SourceError("authority_changed")
        async with primary_authority(fresh=True):
            current = await self.connections.connections.owned(tenant, actor, mapping.connection_id)
            if current is None or current.revision != grant.revision:
                raise SourceError("authority_changed")
            payload, digest = source_authority(current)
            if digest != policy.authority_sha256 or payload != policy.policy_json.get("authority"):
                raise SourceError("authority_changed")
        return SyncAuthorityCapture(grant.revision, digest, policy.id, policy.policy_sha256)

    async def execute(
        self,
        actor: str,
        tenant: str,
        mapping_id: str,
        action: ControlAction,
        request: SourceControlInput,
        *,
        target_run_id: str | None = None,
        _occurrence: datetime | None = None,
    ) -> SourceControlOutput:
        _no_remote_unit()
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(fresh=True):
            mapping, _, policy = await self._scope(actor, tenant, mapping_id)
            receipt = await self._receipt(actor, tenant, request.operation_id)
            if receipt is not None:
                if receipt.payload_sha256 != control_digest(
                    mapping_id, action, request, target_run_id, _occurrence
                ):
                    raise JobConflict(
                        "Operation UUID belongs to another source command", code="IDEMPOTENCY_CONFLICT"
                    )
                return SourceControlOutput.model_validate(receipt.result_json)
        capture = (
            await self.remote_capture(actor, tenant, mapping, policy)
            if action in {"sync", "resume", "retry"}
            else None
        )
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(read_only=False):
            await self._scope(actor, tenant, mapping_id, write=True)
            previous = await self._receipt(actor, tenant, request.operation_id)
            result = await self.controls.apply(
                tenant,
                actor,
                mapping_id,
                action,
                request,
                target_run_id=target_run_id,
                capture=capture,
                _occurrence=_occurrence,
            )
            if previous is None:
                await self.authority.catalog._audit(
                    actor,
                    tenant,
                    "source." + action,
                    mapping_id,
                    {
                        "operation_id": request.operation_id,
                        "receipt_id": result.receipt_id,
                        "control_revision": result.control_revision,
                        "outcome": result.disposition,
                    },
                )
            return result
