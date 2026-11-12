# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable, bounded preparation with fresh authority at every browser boundary."""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pyfly.container import service
from sqlalchemy import select

from koinon.integrations.content_sources.account_operation_dtos import (
    AccountOperationBusy,
    AccountOperationRequest,
)
from koinon.integrations.content_sources.account_operations import SourceAccountBusy, SourceAccountOperations
from koinon.integrations.content_sources.dtos import Account, Cursor, RemoteItem, SourceScope
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.mapping_ancestry import FolderAncestry
from koinon.integrations.content_sources.mapping_dtos import (
    VALIDATION_MAX_LIFETIME_SECONDS,
    MappingReviewInput,
)
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.mapping_preview import (
    SourceMappingPreview,
    available_extensions,
    import_choice,
    source_name_key,
)
from koinon.integrations.content_sources.mapping_review import SourceMappingReviews
from koinon.integrations.content_sources.mapping_validation_dtos import (
    SourceMappingValidationInput,
    SourceMappingValidationItem,
    SourceMappingValidationItemPage,
    SourceMappingValidationOutput,
)
from koinon.integrations.content_sources.mapping_validation_entities import (
    SourceMappingValidation as Validation,
)
from koinon.integrations.content_sources.mapping_validation_entities import (
    SourceMappingValidationEntry as Entry,
)
from koinon.integrations.content_sources.mapping_validation_repository import (
    SourceMappingValidationRepository,
)
from koinon.integrations.content_sources.read_authority import source_authority
from koinon.integrations.content_sources.reader_access import _OperationToken
from koinon.integrations.content_sources.sessions import SourceBrowserSessions
from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.sync_controls import _conflict
from koinon.integrations.content_sources.sync_walk import walk_page
from koinon.jobs.errors import JobConflict
from koinon.security.authority import primary_authority
from koinon.workers.admission import WorkAdmission

logger = logging.getLogger(__name__)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def effective_selection(creation: MappingReviewInput, root_kind: str | None) -> MappingReviewInput:
    if root_kind not in {"file", "folder"}:
        raise _conflict("SOURCE_INVALID_SELECTION")
    if root_kind == "file":
        if creation.excluded_ids:
            raise _conflict("SOURCE_INVALID_SELECTION")
        return creation.model_copy(update={"recursive": False}, deep=True)
    return creation.model_copy(deep=True)


def raw_budget(previous, observed, maximum):
    if type(observed) is not int or not 0 <= observed <= 100:
        raise SourceError("resync_required")
    count = previous + observed
    return count, count > maximum


def manifest_digest(header, entries):
    """Canonical JSON document, streamed in identity order, independent of page boundaries."""
    value = hashlib.sha256()
    value.update(b'{"entries":[')
    separator = b""
    for entry in entries:
        value.update(separator)
        value.update(canonical(entry).encode())
        separator = b","
    value.update(b'],"header":')
    value.update(canonical(header).encode())
    value.update(b"}")
    return value.hexdigest()


async def _all_or_cancel(awaitables):
    """A failed request owns its provider siblings until cancellation has finished."""
    tasks = [asyncio.create_task(awaitable) for awaitable in awaitables]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


class ValidationTokens:
    def __init__(self, vault):
        self.vault = vault

    def issue(self, row, purpose, *, position=None):
        value = {
            "session": row.session_hash,
            "request": row.request_sha256,
            "revision": row.revision,
            "expires": row.expires_at.timestamp(),
            "position": position,
        }
        return base64.urlsafe_b64encode(
            self.vault.encrypt(row.tenant_id, row.owner, str(row.id), "validation-" + purpose, value)
        ).decode()

    def read(self, row, value, purpose, now):
        try:
            if not isinstance(value, str) or not 1 <= len(value) <= 4096:
                raise ValueError
            body = self.vault.decrypt(
                row.tenant_id,
                row.owner,
                str(row.id),
                "validation-" + purpose,
                base64.b64decode(value, altchars=b"-_", validate=True),
            )
            if (
                body["session"] != row.session_hash
                or body["request"] != row.request_sha256
                or body["expires"] != row.expires_at.timestamp()
                or row.expires_at <= now
                or type(body["revision"]) is not int
            ):
                raise ValueError
            return body
        except Exception:
            raise SourceError("invalid_cursor") from None


@dataclass(frozen=True, slots=True)
class SealedValidation:
    validation_id: UUID
    revision: int
    manifest_sha256: str
    selection_json: str
    root_proof_json: str
    expires_at: datetime


@service(name="content_sources.mapping_validation_service")
class SourceMappingValidations:
    def __init__(
        self,
        records: SourceMappingValidationRepository,
        reviews: SourceMappingReviews,
        preview: SourceMappingPreview,
        sessions: SourceBrowserSessions,
        settings: ContentSourceSettings,
        admission: WorkAdmission,
        accounts: SourceAccountOperations,
    ):
        self.records, self.reviews, self.preview = records, reviews, preview
        self.sessions, self.settings, self.admission = sessions, settings, admission
        self.accounts = accounts
        self.vault = reviews.connections.vault
        self.tokens = ValidationTokens(self.vault)

    @asynccontextmanager
    async def _account_slice(self, row):
        permit = await self.accounts.acquire(
            row.tenant_id,
            AccountOperationRequest(
                kind="validation",
                operation_id=str(row.id),
                revision=row.revision,
                connection_id=row.connection_id,
                connection_revision=row.connection_revision,
                owner=row.owner,
                process_instance_id=str(uuid4()),
            ),
        )
        if isinstance(permit, AccountOperationBusy):
            raise SourceAccountBusy(permit.retry_after_seconds)
        try:
            yield permit
        except BaseException:
            try:
                await self.accounts.abort(permit)
            except (Exception, asyncio.CancelledError) as error:
                logger.warning("source_account_cleanup_failed", extra={"error_type": type(error).__name__})
            raise

    async def _finish_account(self, permit):
        if not await self.accounts.finish(
            permit,
            self.records._require_session(),
            outcome="clean" if permit.completion.settled else "uncertain",
        ):
            raise _conflict("SOURCE_ACCOUNT_LEASE_LOST")

    @staticmethod
    def _now():
        return datetime.now(UTC)

    def _encrypt(self, row, purpose, value):
        try:
            return self.vault.encrypt(row.tenant_id, row.owner, str(row.id), "validation-" + purpose, value)
        except ValueError:
            raise SourceError("size_exceeded") from None

    @staticmethod
    def _parent_fits(row, updates):
        # Reserve conservative space for fixed identity/status JSON and its encoding overhead.
        fields = ("request_ciphertext", "root_proof_ciphertext", "walk_ciphertext", "checkpoint_ciphertext")
        return sum(len(updates.get(key, getattr(row, key)) or b"") for key in fields) + 16384 <= 8388608

    def _decrypt(self, row, purpose, value):
        if value is None:
            raise _conflict("SOURCE_VALIDATION_UNAVAILABLE")
        return self.vault.decrypt(row.tenant_id, row.owner, str(row.id), "validation-" + purpose, value)

    async def _session(self, actor, session):
        return await self.sessions.require_with_expiry(actor, session)

    def _bound(self, row, actor, tenant, session, *, live=True):
        if (
            row is None
            or row.owner != actor
            or row.tenant_id != tenant
            or not hmac.compare_digest(row.session_hash, digest(session))
        ):
            raise SourceError("access_denied")
        if live and row.expires_at <= self._now():
            raise _conflict("SOURCE_VALIDATION_EXPIRED")

    async def _load(self, actor, tenant, session, identifier, *, live=True, selection_authority=True):
        await self._session(actor, session)
        await self.reviews.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(read_only=False):
            row = await self.records.owned(tenant, actor, identifier)
            self._bound(row, actor, tenant, session, live=live)
            # Identity recovery still requires current tenant membership, even after payload removal.
            await self.reviews.authority.read_bounds(actor, tenant)
            if selection_authority and row.request_ciphertext is not None and row.expires_at > self._now():
                selected = self._selection(row)
                await self._local_authority(row, selected)
            return row

    async def _local_authority(self, row, selected):
        await self.reviews.authority.destination(row.owner, row.tenant_id, selected.destination, write=True)
        connection = await self.reviews.connections.connections.owned(
            row.tenant_id, row.owner, row.connection_id, lock=True
        )
        if (
            connection is None
            or connection.revision != row.connection_revision
            or source_authority(connection)[1] != row.authority_sha256
            or connection.status != "connected"
            or connection.secret_ciphertext is None
            or connection.refresh_operation is not None
            or self.reviews.connections.registrations.get(connection.provider).fingerprint
            != connection.config_fingerprint
        ):
            raise SourceError("authority_changed")
        if row.mapping_id is not None:
            mapping = await self.records._require_session().scalar(
                select(SourceMapping)
                .where(
                    SourceMapping.tenant_id == row.tenant_id,
                    SourceMapping.owner == row.owner,
                    SourceMapping.id == row.mapping_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if mapping is None or mapping.revision != row.expected_revision:
                raise SourceError("authority_changed")
        if row.scan_max_items != self.settings.sync_max_scan_items:
            raise SourceError("authority_changed")

    async def _root_proof(self, adapter, scope, selected):
        root = await adapter.get_item(selected.root_id)
        if root.scope != scope or root.item_id != selected.root_id:
            raise SourceError("scope_mismatch")
        if root.kind not in {"file", "folder"}:
            raise SourceError("unsupported")
        roots = (root.item_id,) if root.kind == "folder" else root.parents
        if root.kind == "file" and len(roots) != 1:
            raise SourceError("scope_mismatch")
        ancestry = await FolderAncestry(adapter, scope).capture(roots)
        return {"root": asdict(root), "ancestry": asdict(ancestry)}

    @asynccontextmanager
    async def _remote(self, row, selected, session):
        _no_remote_unit()
        await self._session(row.owner, session)
        connection = await self.reviews.connections.connected(row.owner, row.tenant_id, row.connection_id)
        account = connection.account
        if account is None:
            raise SourceError("reconnect_required")
        grant = await self.reviews.connections.read_grant(
            row.owner, row.tenant_id, row.connection_id, account
        )
        if grant.revision != row.connection_revision:
            raise SourceError("authority_changed")
        scope = SourceScope(account, selected.drive_id)
        async with self.reviews.browser._source(scope, _OperationToken(account, grant.token)) as adapter:
            proof = await self._root_proof(adapter, scope, selected)
            if digest(proof) != row.root_proof_sha256:
                raise SourceError("version_changed")
            yield adapter, scope
            if digest(await self._root_proof(adapter, scope, selected)) != row.root_proof_sha256:
                raise SourceError("version_changed")
        await self.reviews.connections.confirm_read_grant(row.owner, row.tenant_id, row.connection_id, grant)
        await self._session(row.owner, session)
        await self.reviews.authority.catalog._refresh_managed_memberships(row.owner)

    def _output(self, row):
        state = (
            row.state
            if row.expires_at > self._now() or row.state in {"cleaning", "abandoned", "expired"}
            else "expired"
        )
        return SourceMappingValidationOutput(
            validation_id=row.id,
            revision=row.revision,
            state=state,
            expires_at=row.expires_at,
            continuation_token=self.tokens.issue(row, "continue")
            if state in {"scanning", "verifying", "checking_changes"}
            else None,
            enumeration_complete=row.enumeration_complete,
            manifest_sha256=row.manifest_sha256 if state == "complete" else None,
            reason_code=row.reason_code,
        )

    async def begin_validation(self, actor, tenant, session, body: SourceMappingValidationInput):
        _no_remote_unit()
        async with asyncio.timeout(120), self.admission.hold("bulk", api=True):
            expiry = min(
                await self._session(actor, session),
                self._now() + timedelta(seconds=VALIDATION_MAX_LIFETIME_SECONDS),
            )
            selected, identifier = body.selection(), uuid4()
            await self.reviews.authority.catalog._refresh_managed_memberships(actor)
            async with primary_authority(read_only=False):
                await self.reviews.authority.destination(actor, tenant, selected.destination, write=True)
                previous = await self.records.operation(tenant, actor, body.operation_id)
                if previous is not None:
                    self._bound(previous, actor, tenant, session)
                    if (previous.request_sha256, previous.mapping_id, previous.expected_revision) != (
                        digest(selected.model_dump(mode="json")),
                        body.mapping_id,
                        body.expected_revision,
                    ):
                        raise _conflict("IDEMPOTENCY_CONFLICT")
                    return self._output(previous)
                connection = await self.reviews.connections.connections.owned(
                    tenant, actor, selected.connection_id, lock=True
                )
                if connection is None:
                    raise SourceError("access_denied")
                authority = source_authority(connection)[1]
                now, maximum = self._now(), self.settings.sync_max_scan_items
                row = Validation(
                    id=identifier,
                    tenant_id=tenant,
                    owner=actor,
                    operation_id=body.operation_id,
                    session_hash=digest(session),
                    request_sha256=digest(selected.model_dump(mode="json")),
                    connection_id=selected.connection_id,
                    connection_revision=connection.revision,
                    authority_sha256=authority,
                    mapping_id=body.mapping_id,
                    expected_revision=body.expected_revision,
                    root_captured=False,
                    root_kind=None,
                    root_proof_sha256=None,
                    root_proof_ciphertext=None,
                    walk_ciphertext=None,
                    checkpoint_ciphertext=None,
                    state="scanning",
                    revision=1,
                    enumeration_complete=False,
                    verification_position=0,
                    raw_observed_count=0,
                    eligible_count=0,
                    change_count=0,
                    scan_max_items=maximum,
                    reserved_bytes=maximum * 16384 + 8388608,
                    max_active_per_tenant=self.settings.sync_validation_max_active_per_tenant,
                    max_active_per_owner=self.settings.sync_validation_max_active_per_owner,
                    max_records_per_tenant=self.settings.sync_validation_max_records_per_tenant,
                    max_retained_bytes_per_tenant=self.settings.sync_validation_max_retained_bytes_per_tenant,
                    created_at=now,
                    updated_at=now,
                    expires_at=expiry,
                    cleanup_position=0,
                )
                row.request_ciphertext = self._encrypt(row, "request", selected.model_dump(mode="json"))
                await self._local_authority(row, selected)
                return self._output(await self.records.admit(row))

    def _selection(self, row):
        creation = MappingReviewInput.model_validate(self._decrypt(row, "request", row.request_ciphertext))
        return effective_selection(creation, row.root_kind) if row.root_captured else creation

    async def _capture_root(self, row, creation, session):
        """Read-only external work after durable admission, followed by a separate CAS commit."""
        _no_remote_unit()
        connection = await self.reviews.connections.connected(row.owner, row.tenant_id, row.connection_id)
        account = connection.account
        if account is None:
            raise SourceError("reconnect_required")
        grant = await self.reviews.connections.read_grant(
            row.owner, row.tenant_id, row.connection_id, account
        )
        if grant.revision != row.connection_revision:
            raise SourceError("authority_changed")
        scope = SourceScope(account, creation.drive_id)
        async with self.reviews.browser._source(scope, _OperationToken(account, grant.token)) as adapter:
            checkpoint = await adapter.start_cursor()
            if checkpoint.scope != scope:
                raise SourceError("scope_mismatch")
            proof = await self._root_proof(adapter, scope, creation)
            effective_selection(creation, proof["root"]["kind"])
            if await self._root_proof(adapter, scope, creation) != proof:
                raise SourceError("version_changed")
        await self.reviews.connections.confirm_read_grant(row.owner, row.tenant_id, row.connection_id, grant)
        await self._session(row.owner, session)
        await self.reviews.authority.catalog._refresh_managed_memberships(row.owner)
        return {
            "root_captured": True,
            "root_kind": proof["root"]["kind"],
            "root_proof_sha256": digest(proof),
            "root_proof_ciphertext": self._encrypt(row, "root", proof),
            "checkpoint_ciphertext": self._encrypt(row, "checkpoint", asdict(checkpoint)),
        }

    async def validation_status(self, actor, tenant, session, identifier):
        row = await self._load(actor, tenant, session, identifier, live=False)
        return self._output(row)

    async def creation_receipt(self, actor, tenant, session, operation):
        await self._session(actor, session)
        async with primary_authority(read_only=False):
            row = await self.records.operation(tenant, actor, operation)
            self._bound(row, actor, tenant, session)
            identifier = row.id
        return await self.validation_status(actor, tenant, session, identifier)

    async def abandon_validation(self, actor, tenant, session, identifier, expected_revision):
        await self._load(actor, tenant, session, identifier, live=False, selection_authority=False)
        async with primary_authority(read_only=False):
            row = await self.records.owned(tenant, actor, identifier, lock=True)
            self._bound(row, actor, tenant, session, live=False)
            if row.state not in {"cleaning", "abandoned", "expired"}:
                if row.revision != expected_revision:
                    raise _conflict("SOURCE_VALIDATION_CHANGED")
                self.records.start_cleanup(row, self._now())
                await self.records._require_session().flush()
            return self._output(row)

    async def _current(self, original, session, expected, *, consumed=None, invalidating=False):
        selected = self._selection(original)
        # Canonical tenant -> connection -> mapping -> validation is shared with final apply.
        if invalidating:
            await self.records.tenant_lock(original.tenant_id)
            await self.reviews.authority.read_bounds(original.owner, original.tenant_id)
        else:
            await self._local_authority(original, selected)
        row = await self.records.owned(original.tenant_id, original.owner, original.id, lock=True)
        self._bound(row, original.owner, original.tenant_id, session)
        if row.revision != expected and (
            consumed is None
            or row.last_continuation_sha256 != consumed
            or row.last_continuation_result_revision != row.revision
        ):
            raise _conflict("SOURCE_VALIDATION_CHANGED")
        return row, selected

    def _candidate(self, row, item, parent, selected):
        choice = import_choice(item, selected, available_extensions(selected.mode))
        return {
            "remote": asdict(item),
            "filename": choice.filename,
            "export_mime": choice.export_mime,
            "reason": choice.reason,
            "parent": parent,
        }

    async def _path(self, row, candidate, selected, cache):
        """Store parent links once; materialize a bounded path only for this request."""
        parts, ancestry = [candidate["filename"]], []
        parent = candidate["parent"]
        seen = set()
        while parent is not None:
            if parent in seen or len(seen) >= 256:
                raise SourceError("resync_required")
            seen.add(parent)
            ancestry.append(parent)
            if parent == selected.root_id:
                break
            if parent not in cache:
                entry = await self.records.entry(row, parent)
                if entry is None:
                    raise SourceError("resync_required")
                cache[parent] = self._decrypt(row, "entry", entry.candidate_ciphertext)
            previous = cache[parent]
            parts.append(previous["filename"])
            parent = previous["parent"]
        return list(reversed(parts)), list(reversed(ancestry))

    async def _presentation(self, row, entry, selected, cache):
        candidate = self._decrypt(row, "entry", entry.candidate_ciphertext)
        remote = candidate["remote"]
        fields = {key: value for key, value in remote.items() if key != "scope"}
        fields["parents"] = tuple(fields["parents"])
        scope = SourceScope(Account(**remote["scope"]["account"]), remote["scope"]["drive_id"])
        choice = import_choice(
            RemoteItem(scope=scope, **fields), selected, available_extensions(selected.mode)
        )
        if (choice.filename, choice.export_mime, choice.reason) != (
            candidate["filename"],
            candidate["export_mime"],
            candidate["reason"],
        ):
            raise _conflict("SOURCE_VALIDATION_CHANGED")
        path, ancestry = await self._path(row, candidate, selected, cache)
        return {
            "item_id": entry.item_id,
            "name": remote["name"],
            "kind": remote["kind"],
            "version": remote["version"],
            "filename": candidate["filename"],
            "export_mime": candidate["export_mime"],
            "reason": candidate["reason"],
            "relative_path": path,
            "ancestry": ancestry,
            "destination_relative_path": (
                [candidate["filename"]] if selected.hierarchy == "flatten" else path
            ),
            "size_bytes": remote["size_bytes"],
            "collision": "none",
            "action": "create",
        }

    async def _namespace(self, row, selected, entries):
        cache = {}
        values = [await self._presentation(row, entry, selected, cache) for entry in entries]
        await self.preview.local_conflicts(
            row.owner, row.tenant_id, selected, values, mapping_id=row.mapping_id
        )
        collisions = await self.records.collision_keys(
            row, [entry.destination_key_sha256 for entry in entries]
        )
        for entry, value in zip(entries, values, strict=True):
            if entry.destination_key_sha256 in collisions and value["collision"] == "none":
                value["collision"] = "source_name"
        origins = {}
        if row.mapping_id is not None:
            origins = {
                item.item_id: item
                for item in (
                    await self.records._require_session().scalars(
                        select(SourceObject).where(
                            SourceObject.tenant_id == row.tenant_id,
                            SourceObject.mapping_id == row.mapping_id,
                            SourceObject.item_id.in_([entry.item_id for entry in entries]),
                        )
                    )
                ).all()
            }
        for value in values:
            origin = origins.get(value["item_id"])
            value["action"] = (
                "skip"
                if value["reason"] or value["kind"] != "file"
                else "create"
                if origin is None or origin.published_native_version_id is None
                else "move"
                if origin.remote_name != value["name"] or origin.remote_ancestry_json != value["ancestry"]
                else "replace"
            )
        return values

    async def _scan(self, row, selected, adapter, scope):
        state = self._decrypt(row, "walk", row.walk_ciphertext) if row.walk_ciphertext else None
        chosen_root = await adapter.get_item(selected.root_id) if row.root_kind == "file" else None
        page = await walk_page(
            adapter,
            scope,
            selected.root_id,
            recursive=selected.recursive,
            excluded=tuple(selected.excluded_ids),
            state=state,
            chosen_root=chosen_root,
        )
        observations = [(entry.item, entry.ancestry[-1] if entry.ancestry else None) for entry in page.items]
        raw, complete, next_state = page.raw_observed_count, page.complete, page.next_state
        count, overflow = raw_budget(row.raw_observed_count, raw, row.scan_max_items)
        if overflow:
            return {
                "state": "blocked",
                "reason_code": "SOURCE_SCAN_LIMIT_EXCEEDED",
                "raw_observed_count": count,
            }, []
        candidates = [(item, self._candidate(row, item, parent, selected)) for item, parent in observations]
        cache = {item.item_id: candidate for item, candidate in candidates}
        entries = []
        async with primary_authority(read_only=False):
            for item, candidate in candidates:
                path, _ = await self._path(row, candidate, selected, cache)
                normalized = [
                    source_name_key(part)
                    for part in ([candidate["filename"]] if selected.hierarchy == "flatten" else path)
                ]
                key = digest(normalized if candidate["reason"] is None else {"skipped": item.item_id})
                ciphertext = self._encrypt(row, "entry", candidate)
                retained = (
                    sum(
                        len(value.encode())
                        for value in (
                            row.tenant_id,
                            item.item_id,
                            candidate["parent"] or "",
                            digest(asdict(item)),
                            key,
                        )
                    )
                    + len(ciphertext)
                    + 36
                )
                if retained > 16384:
                    return {"state": "blocked", "reason_code": "SOURCE_SCAN_LIMIT_EXCEEDED"}, []
                entries.append(
                    Entry(
                        tenant_id=row.tenant_id,
                        validation_id=row.id,
                        item_id=item.item_id,
                        parent_item_id=candidate["parent"],
                        fingerprint_sha256=digest(asdict(item)),
                        candidate_ciphertext=ciphertext,
                        destination_key_sha256=key,
                        verified=False,
                    )
                )
        return {
            "state": "verifying" if complete else "scanning",
            "raw_observed_count": count,
            "enumeration_complete": complete,
            "walk_ciphertext": self._encrypt(row, "walk", next_state) if next_state else None,
        }, entries

    async def _verify(self, row, adapter):
        async with primary_authority(read_only=False):
            entries = await self.records.entries(row, after=row.verification_position - 1)
        slots = asyncio.Semaphore(4)

        async def confirm(entry):
            async with slots:
                current = await adapter.check_access(entry.item_id)
                if digest(asdict(current)) != entry.fingerprint_sha256:
                    raise SourceError("version_changed")

        await _all_or_cancel(confirm(entry) for entry in entries)
        position = row.verification_position + len(entries)
        return {
            "verification_position": position,
            "state": "checking_changes" if position == row.eligible_count else "verifying",
        }, entries

    def _cursor(self, row, scope):
        value = self._decrypt(row, "checkpoint", row.checkpoint_ciphertext)
        if value["scope"] != json.loads(canonical(asdict(scope))):
            raise SourceError("invalid_cursor")
        return Cursor(scope, value["operation"], value["token"])

    async def _changes(self, row, selected, adapter, scope, *, freshness=False):
        before = self._cursor(row, scope)
        page = await adapter.changes(before)
        if len(page.changes) > 200 or page.next_cursor is None and page.checkpoint is None:
            raise SourceError("resync_required")
        after = page.next_cursor or page.checkpoint
        if after.scope != scope or after.operation != before.operation or page.next_cursor == before:
            raise SourceError("invalid_cursor")
        if freshness and page.next_cursor is not None:
            raise _conflict("SOURCE_VALIDATION_REFRESH_REQUIRED")
        count = row.change_count + len(page.changes)
        if count > row.scan_max_items:
            raise SourceError("resync_required")
        async with primary_authority(read_only=False):
            selected_change = await self.records._require_session().scalar(
                select(Entry.item_id)
                .where(
                    Entry.tenant_id == row.tenant_id,
                    Entry.validation_id == row.id,
                    Entry.item_id.in_([change.item_id for change in page.changes]),
                )
                .limit(1)
            )
        if selected_change is not None:
            # Current ancestry outside the root cannot erase membership observed during this scan.
            raise SourceError("version_changed")
        # A removal cannot prove former membership. Upserts may be ignored only with current ancestry.
        slots = asyncio.Semaphore(4)

        async def unrelated(change):
            if change.kind != "upsert" or change.item is None:
                raise SourceError("version_changed")
            async with slots:
                item = await adapter.get_item(change.item_id)
                if item.scope != scope or item != change.item or item.kind not in {"file", "folder"}:
                    raise SourceError("version_changed")
                roots = (item.item_id,) if item.kind == "folder" else item.parents
                if len(roots) != 1:
                    raise SourceError("version_changed")
                proof = await FolderAncestry(adapter, scope).capture(roots)
                if item.item_id == selected.root_id or selected.root_id in (
                    *roots,
                    *proof.ancestors(roots[0]),
                ):
                    raise SourceError("version_changed")
                original = self._decrypt(row, "root", row.root_proof_ciphertext)
                ancestors = {node["id"] for node in original["ancestry"]["nodes"]}
                if item.item_id in ancestors:
                    raise SourceError("version_changed")

        await _all_or_cancel(unrelated(change) for change in page.changes)
        return after, page.next_cursor is None, count

    async def _complete_digest(self, row, selected, checkpoint):
        """Stream all candidates under canonical locks; no provider calls in this fence."""
        if await self.records.source_collision(row):
            raise _conflict("SOURCE_NAME_COLLISION")
        header = {
            "selection": selected.model_dump(mode="json"),
            "root": self._decrypt(row, "root", row.root_proof_ciphertext),
            "authority": row.authority_sha256,
            "checkpoint": checkpoint,
            "scan_max_items": row.scan_max_items,
        }
        hashed = hashlib.sha256(b'{"entries":[')
        separator = b""
        statement = (
            select(Entry)
            .where(Entry.tenant_id == row.tenant_id, Entry.validation_id == row.id)
            .order_by(Entry.item_id.collate("C"))
        )
        stream = await self.records._require_session().stream_scalars(
            statement.execution_options(yield_per=100)
        )
        try:
            async for entries in stream.partitions(100):
                values = await self._namespace(row, selected, entries)
                for entry, value in zip(entries, values, strict=True):
                    if value["collision"] != "none":
                        raise _conflict(
                            "SOURCE_NAME_COLLISION"
                            if value["collision"] == "source_name"
                            else "SOURCE_LOCAL_EDIT"
                            if value["collision"] == "local_edit"
                            else "SOURCE_DESTINATION_COLLISION"
                        )
                    normalized = [source_name_key(part) for part in value["destination_relative_path"]]
                    hashed.update(separator)
                    hashed.update(
                        canonical(
                            (entry.item_id, entry.fingerprint_sha256, normalized, value["action"])
                        ).encode()
                    )
                    separator = b","
        finally:
            await stream.close()
        hashed.update(b'],"header":')
        hashed.update(canonical(header).encode())
        hashed.update(b"}")
        return hashed.hexdigest()

    async def continue_validation(self, actor, tenant, session, identifier, body):
        _no_remote_unit()
        async with asyncio.timeout(120), self.admission.hold("bulk", api=True):
            row = await self._load(actor, tenant, session, identifier)
            token = self.tokens.read(row, body.continuation_token, "continue", self._now())
            consumed = digest(body.continuation_token)
            if (
                consumed == row.last_continuation_sha256
                and row.last_continuation_result_revision == row.revision
            ):
                return self._output(row)
            if token["revision"] != row.revision or body.expected_revision != row.revision:
                raise _conflict("SOURCE_VALIDATION_CHANGED")
            if row.state not in {"scanning", "verifying", "checking_changes"}:
                raise _conflict("SOURCE_VALIDATION_CHANGED")
            async with self._account_slice(row) as permit:
                selected = self._selection(row)
                entries, updates, terminal = [], {}, False
                try:
                    async with self.accounts.remote(permit):
                        if not row.root_captured:
                            updates = await self._capture_root(row, selected, session)
                        else:
                            async with self._remote(row, selected, session) as (adapter, scope):
                                if row.state == "scanning":
                                    updates, entries = await self._scan(row, selected, adapter, scope)
                                elif row.state == "verifying":
                                    updates, entries = await self._verify(row, adapter)
                                else:
                                    checkpoint, terminal, count = await self._changes(
                                        row, selected, adapter, scope
                                    )
                                    updates = {
                                        "checkpoint_ciphertext": self._encrypt(
                                            row, "checkpoint", asdict(checkpoint)
                                        ),
                                        "change_count": count,
                                    }
                except JobConflict as error:
                    if error.code != "SOURCE_INVALID_SELECTION":
                        raise
                    updates = {"state": "blocked", "reason_code": "SOURCE_INVALID_SELECTION"}
                except SourceError as error:
                    if error.code not in {
                        "access_denied",
                        "authority_changed",
                        "version_changed",
                        "resync_required",
                        "invalid_cursor",
                        "size_exceeded",
                        "unsupported",
                        "scope_mismatch",
                        "reconnect_required",
                    }:
                        raise
                    updates = {
                        "state": "blocked" if error.code in {"size_exceeded", "unsupported"} else "stale",
                        "reason_code": "SOURCE_AUTHORITY_CHANGED"
                        if error.code in {"access_denied", "authority_changed"}
                        else "SOURCE_INVALID_SELECTION"
                        if error.code == "unsupported"
                        else "SOURCE_SCAN_LIMIT_EXCEEDED"
                        if error.code == "size_exceeded"
                        else "SOURCE_CHANGED",
                    }
                    entries, terminal = [], False
                if not self._parent_fits(row, updates):
                    updates = {"state": "blocked", "reason_code": "SOURCE_SCAN_LIMIT_EXCEEDED"}
                    entries, terminal = [], False
                async with primary_authority(read_only=False):
                    expected = row.revision
                    current, selected = await self._current(
                        row,
                        session,
                        expected,
                        consumed=consumed,
                        invalidating=updates.get("state") == "stale",
                    )
                    await self.accounts.assert_current(permit, self.records._require_session())
                    if current.revision != expected:
                        await self._finish_account(permit)
                        return self._output(current)
                    if row.state == "scanning" and entries:
                        # Detect changed duplicates before inserting anything, so a stale slice is atomic.
                        for entry in entries:
                            previous = await self.records.entry(current, entry.item_id)
                            if (
                                previous is not None
                                and previous.fingerprint_sha256 != entry.fingerprint_sha256
                            ):
                                updates, entries = {"state": "stale", "reason_code": "SOURCE_CHANGED"}, []
                                break
                        current.eligible_count += await self.records.append(current, entries)
                    elif row.state == "verifying" and entries:
                        await self.records.mark_verified(current, [entry.item_id for entry in entries])
                        try:
                            values = await self._namespace(current, selected, entries)
                        except JobConflict as error:
                            if error.code != "SOURCE_VALIDATION_CHANGED":
                                raise
                            updates.update(state="stale", reason_code="SOURCE_AUTHORITY_CHANGED")
                            values = []
                        collision = next(
                            (value["collision"] for value in values if value["collision"] != "none"), None
                        )
                        if collision:
                            updates["state"] = "blocked"
                            updates["reason_code"] = (
                                "SOURCE_NAME_COLLISION"
                                if collision == "source_name"
                                else "SOURCE_LOCAL_EDIT"
                                if collision == "local_edit"
                                else "SOURCE_DESTINATION_COLLISION"
                            )
                    for key, value in updates.items():
                        setattr(current, key, value)
                    if terminal:
                        # Queries below must not flush a half-transition before its revision/CAS receipt.
                        with self.records._require_session().no_autoflush:
                            try:
                                current.manifest_sha256 = await self._complete_digest(
                                    current,
                                    selected,
                                    self._decrypt(current, "checkpoint", current.checkpoint_ciphertext),
                                )
                                current.state = "complete"
                            except JobConflict as error:
                                if error.code not in {
                                    "SOURCE_NAME_COLLISION",
                                    "SOURCE_DESTINATION_COLLISION",
                                    "SOURCE_LOCAL_EDIT",
                                }:
                                    raise
                                current.state, current.reason_code = "blocked", error.code
                    current.revision += 1
                    current.updated_at = self._now()
                    current.last_continuation_sha256 = consumed
                    current.last_continuation_result_revision = current.revision
                    await self.records._require_session().flush()
                    await self._finish_account(permit)
                    return self._output(current)

    async def validation_items(self, actor, tenant, session, identifier, *, limit=25, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise SourceError("invalid_cursor")
        async with asyncio.timeout(120), self.admission.hold("bulk", api=True):
            row = await self._load(actor, tenant, session, identifier)
            selected = self._selection(row)
            if not row.root_captured:
                return SourceMappingValidationItemPage(
                    validation_id=row.id, revision=row.revision, items=[], visible_count=0, next_cursor=None
                )
            position = -1
            if cursor:
                value = self.tokens.read(row, cursor, "items", self._now())
                position = value["position"]
                if value["revision"] != row.revision or type(position) is not int or position < 0:
                    raise SourceError("invalid_cursor")
            async with primary_authority(read_only=False):
                entries = await self.records.entries(row, after=position, limit=limit)
            async with self._account_slice(row) as permit:
                authorized, denied = [], False
                denial = None
                try:
                    async with self.accounts.remote(permit):
                        async with self._remote(row, selected, session) as (adapter, _scope):
                            for entry in entries:
                                try:
                                    current = await adapter.check_access(entry.item_id)
                                    if digest(asdict(current)) != entry.fingerprint_sha256:
                                        raise SourceError("version_changed")
                                    # Hydrate retained names only after fresh item and all parent checks.
                                    parent, seen = entry.parent_item_id, set()
                                    while parent and parent != selected.root_id:
                                        if parent in seen or len(seen) >= 256:
                                            raise SourceError("resync_required")
                                        seen.add(parent)
                                        folder = await adapter.check_access(parent)
                                        if folder.kind != "folder" or len(folder.parents) != 1:
                                            raise SourceError("version_changed")
                                        async with primary_authority(read_only=False):
                                            pinned_parent = await self.records.entry(row, parent)
                                        if (
                                            pinned_parent is None
                                            or digest(asdict(folder)) != pinned_parent.fingerprint_sha256
                                        ):
                                            raise SourceError("version_changed")
                                        parent = pinned_parent.parent_item_id
                                    authorized.append(entry)
                                except SourceError as error:
                                    if error.code not in {"access_denied", "version_changed"}:
                                        raise
                                    denied = True
                                    denial = error
                        if denial is not None:
                            raise denial
                except SourceError as error:
                    if error is not denial:
                        raise
                async with primary_authority(read_only=False):
                    current, selected = await self._current(row, session, row.revision)
                    await self.accounts.assert_current(permit, self.records._require_session())
                    if denied and current.state not in {"stale", "blocked"}:
                        current.state, current.reason_code = "stale", "SOURCE_CHANGED"
                        current.revision += 1
                        current.updated_at = self._now()
                        await self.records._require_session().flush()
                    await self._finish_account(permit)
                    values = await self._namespace(current, selected, authorized)
                    next_cursor = (
                        self.tokens.issue(current, "items", position=entries[-1].sequence)
                        if (entries and entries[-1].sequence + 1 < current.eligible_count)
                        else None
                    )
                    return SourceMappingValidationItemPage(
                        validation_id=current.id,
                        revision=current.revision,
                        items=[
                            SourceMappingValidationItem.model_validate(
                                {key: value for key, value in item.items() if key != "ancestry"}
                            )
                            for item in values
                        ],
                        visible_count=len(values),
                        next_cursor=next_cursor,
                    )

    async def seal_for_review(
        self,
        actor,
        tenant,
        session,
        identifier,
        selection: MappingReviewInput,
        *,
        mapping_id=None,
        expected_revision=None,
    ):
        """Fresh provider evidence outside the caller's final primary/source fence."""
        async with asyncio.timeout(120), self.admission.hold("bulk", api=True):
            row = await self._load(actor, tenant, session, identifier)
            if (
                row.state != "complete"
                or row.manifest_sha256 is None
                or digest(self._selection(row).model_dump(mode="json"))
                != digest(selection.model_dump(mode="json"))
                or (row.mapping_id, row.expected_revision) != (mapping_id, expected_revision)
            ):
                raise _conflict("SOURCE_VALIDATION_CHANGED")
            async with self._account_slice(row) as permit:
                async with (
                    self.accounts.remote(permit),
                    self._remote(row, selection, session) as (adapter, scope),
                ):
                    await self._changes(row, selection, adapter, scope, freshness=True)
                async with primary_authority(read_only=False):
                    current, selected = await self._current(row, session, row.revision)
                    await self.accounts.assert_current(permit, self.records._require_session())
                    manifest = await self._complete_digest(
                        current, selected, self._decrypt(current, "checkpoint", current.checkpoint_ciphertext)
                    )
                    if manifest != row.manifest_sha256:
                        raise _conflict("SOURCE_VALIDATION_CHANGED")
                    await self._finish_account(permit)
                    return SealedValidation(
                        row.id,
                        row.revision,
                        manifest,
                        canonical(selected.model_dump(mode="json")),
                        canonical(self._decrypt(current, "root", current.root_proof_ciphertext)),
                        current.expires_at,
                    )

    async def locked_assert_eligible(self, actor, tenant, session, sealed: SealedValidation):
        """Caller already refreshed session/provider and holds canonical authority; no network here."""
        row = await self.records.owned(tenant, actor, sealed.validation_id)
        self._bound(row, actor, tenant, session)
        if (
            row.state != "complete"
            or row.revision != sealed.revision
            or row.manifest_sha256 != sealed.manifest_sha256
        ):
            raise _conflict("SOURCE_VALIDATION_CHANGED")
        selected = MappingReviewInput.model_validate_json(sealed.selection_json)
        if digest(self._selection(row).model_dump(mode="json")) != digest(selected.model_dump(mode="json")):
            raise _conflict("SOURCE_VALIDATION_CHANGED")
        await self._local_authority(row, selected)
        row = await self.records.owned(tenant, actor, sealed.validation_id, lock=True)
        if (
            row.state != "complete"
            or row.revision != sealed.revision
            or row.manifest_sha256 != sealed.manifest_sha256
        ):
            raise _conflict("SOURCE_VALIDATION_CHANGED")
        manifest = await self._complete_digest(
            row, selected, self._decrypt(row, "checkpoint", row.checkpoint_ciphertext)
        )
        if manifest != sealed.manifest_sha256:
            raise _conflict("SOURCE_VALIDATION_CHANGED")
        return row
