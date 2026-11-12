# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable human reviews and accepted authority have independent revisions."""

import asyncio
import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import wraps
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pyfly.container import repository, service
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, select

from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.mapping_preview import SourceMappingPreview
from koinon.integrations.content_sources.mapping_review import SourceMappingReviews
from koinon.integrations.content_sources.mapping_validation import (
    SealedValidation,
    SourceMappingValidations,
    effective_selection,
)
from koinon.integrations.content_sources.mapping_validation_entities import SourceMappingValidationEntry
from koinon.integrations.content_sources.read_authority import source_authority
from koinon.integrations.content_sources.sessions import SourceBrowserSessions
from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.sync_controls import ACTIVE_RUNS, _conflict
from koinon.integrations.content_sources.sync_dtos import (
    SourceDestinationPresentation,
    SourceDestinationSegment,
    SourcePolicyApplyInput,
    SourcePolicyOperationOutput,
    SourcePolicyReviewInput,
    SourceReviewPage,
)
from koinon.integrations.content_sources.sync_entities import (
    SourceMappingPolicy,
    SourcePolicyOperation,
    SourceSyncRun,
    SourceSyncState,
)
from koinon.integrations.content_sources.sync_schedule import next_occurrence
from koinon.security.authority import primary_authority


def policy_digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def policy_deadline(method):
    """One deadline includes admission, provider work and the final transaction."""

    @wraps(method)
    async def bounded(*args, **kwargs):
        try:
            async with asyncio.timeout(120):
                return await method(*args, **kwargs)
        except TimeoutError:
            raise SourceError("timeout") from None

    return bounded


def review_payload(request):
    """An omitted optional validation preserves historical command receipt identity."""
    return request.model_dump(
        mode="json", exclude={"validation_id"} if request.validation_id is None else set()
    )


def validation_reference(sealed, mapping_id, expected_revision):
    if sealed is None:
        return None
    return {
        "id": str(sealed.validation_id),
        "revision": sealed.revision,
        "manifest_sha256": sealed.manifest_sha256,
        "mapping_id": mapping_id,
        "expected_revision": expected_revision,
    }


def sealed_root(sealed, root_id):
    proof = json.loads(sealed.root_proof_json)
    root = proof["root"]
    paths = dict(proof["ancestry"]["paths"])
    if root["item_id"] != root_id or root["kind"] not in {"file", "folder"}:
        raise _conflict("SOURCE_VALIDATION_CHANGED")
    if root["kind"] == "file":
        if len(root["parents"]) != 1:
            raise _conflict("SOURCE_VALIDATION_CHANGED")
        parent = root["parents"][0]
        return "file", (root_id, parent, *paths[parent])
    return "folder", (root_id, *paths[root_id])


@dataclass(frozen=True, slots=True)
class PolicyCapture:
    connection_revision: int
    authority: dict
    authority_sha256: str
    root_ancestry: tuple[str, ...]
    preview_sha256: str
    preview_complete: bool
    preview_collisions: int
    captured_at: datetime
    expires_at: datetime
    root_kind: str = "folder"
    validation: SealedValidation | None = None
    validation_mapping_revision: int | None = None


@repository(name="content_sources.policies")
class SourcePolicyRepository(Repository[SourceMappingPolicy, str]):
    """Caller retains canonical tenant/destination locks; remote proof precedes entry."""

    async def receipt(self, tenant, owner, operation, action, digest):
        row = await self._require_session().scalar(
            select(SourcePolicyOperation).where(
                SourcePolicyOperation.tenant_id == tenant,
                SourcePolicyOperation.owner == owner,
                SourcePolicyOperation.operation_id == operation,
            )
        )
        if row is None:
            return None
        if row.action != action or not hmac.compare_digest(row.payload_sha256, digest):
            raise _conflict("IDEMPOTENCY_CONFLICT")
        return SourcePolicyOperationOutput.model_validate(row.result_json)

    async def _connection(self, tenant, owner, identifier):
        row = await self._require_session().scalar(
            select(PersonalSourceConnection)
            .where(
                PersonalSourceConnection.id == identifier,
                PersonalSourceConnection.tenant_id == tenant,
                PersonalSourceConnection.owner == owner,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise _conflict("SOURCE_UNAVAILABLE")
        return row

    async def _mapping(self, tenant, owner, identifier):
        row = await self._require_session().scalar(
            select(SourceMapping)
            .where(
                SourceMapping.id == identifier,
                SourceMapping.tenant_id == tenant,
                SourceMapping.owner == owner,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise _conflict("SOURCE_UNAVAILABLE")
        return row

    @staticmethod
    def _fresh(connection, capture):
        if (
            connection.status != "connected"
            or connection.secret_ciphertext is None
            or connection.refresh_operation is not None
            or connection.revision != capture.connection_revision
            or source_authority(connection) != (capture.authority, capture.authority_sha256)
        ):
            raise _conflict("SOURCE_AUTHORITY_CHANGED")

    async def latest(self, tenant, mapping_id):
        return await self._require_session().scalar(
            select(func.max(SourceMappingPolicy.revision)).where(
                SourceMappingPolicy.tenant_id == tenant,
                SourceMappingPolicy.mapping_id == mapping_id,
            )
        )

    async def _baseline(self, tenant, mapping):
        state = await self._require_session().scalar(
            select(SourceSyncState)
            .where(
                SourceSyncState.tenant_id == tenant,
                SourceSyncState.mapping_id == mapping.id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if state is None:
            return {"policy_id": None, "revision": None}, None
        accepted = await self._require_session().get(SourceMappingPolicy, state.accepted_policy_id)
        if accepted is None or accepted.accepted_at is None or accepted.revision != mapping.revision:
            raise _conflict()
        return {"policy_id": accepted.id, "revision": accepted.revision}, state

    async def _record(self, tenant, owner, operation, action, policy, expected, digest):
        receipt_id = str(uuid4())
        result = SourcePolicyOperationOutput(
            receipt_id=receipt_id,
            operation_id=operation,
            action=action,
            mapping_id=policy.mapping_id,
            policy_id=policy.id,
            expected_policy_revision=expected,
            result_policy_revision=policy.revision,
            review_digest=policy.review_digest,
            review_expires_at=policy.review_expires_at,
            disposition="reviewed" if action == "review" else "accepted",
        )
        self._require_session().add(
            SourcePolicyOperation(
                id=receipt_id,
                tenant_id=tenant,
                owner=owner,
                operation_id=operation,
                action=action,
                mapping_id=policy.mapping_id,
                policy_id=policy.id,
                expected_policy_revision=expected,
                result_policy_revision=policy.revision,
                payload_sha256=digest,
                result_json=result.model_dump(mode="json", by_alias=True),
            )
        )
        await self._require_session().flush()
        return result

    async def review(
        self,
        tenant: str,
        owner: str,
        request: SourcePolicyReviewInput,
        session_hash: str,
        capture: PolicyCapture,
        *,
        mapping_id=None,
        expected_revision=None,
    ):
        session = self._require_session()
        connection = await self._connection(tenant, owner, request.connection_id)
        mapping = await self._mapping(tenant, owner, mapping_id) if mapping_id else None
        digest = policy_digest(["review", mapping_id, expected_revision, review_payload(request)])
        previous = await self.receipt(tenant, owner, request.operation_id, "review", digest)
        if previous is not None:
            return previous
        self._fresh(connection, capture)
        if capture.expires_at <= datetime.now(UTC) or len(session_hash) != 64:
            raise _conflict("SOURCE_REVIEW_EXPIRED")
        if request.validation_id is not None and (
            capture.validation is None
            or capture.validation.validation_id != request.validation_id
            or capture.validation.manifest_sha256 != capture.preview_sha256
            or not capture.preview_complete
            or capture.preview_collisions
        ):
            raise _conflict("SOURCE_VALIDATION_CHANGED")
        latest = await self.latest(tenant, mapping.id) if mapping else None
        if latest != expected_revision or (mapping and mapping.status == "retired"):
            raise _conflict("SOURCE_POLICY_CONFLICT")
        if mapping and (mapping.connection_id, mapping.drive_id, mapping.root_id) != (
            request.connection_id,
            request.drive_id,
            request.root_id,
        ):
            raise _conflict("SOURCE_POLICY_CONFLICT")
        policy_request = MappingReviewInput.model_validate(
            request.model_dump(exclude={"operation_id", "expected_revision", "validation_id"})
        )
        policy_request = effective_selection(policy_request, capture.root_kind)
        payload = policy_request.model_dump(mode="json")
        if mapping is None:
            identifier = str(uuid5(NAMESPACE_URL, json.dumps([tenant, owner, request.operation_id])))
            mapping = SourceMapping(
                id=identifier,
                tenant_id=tenant,
                owner=owner,
                connection_id=connection.id,
                provider=connection.provider,
                external_subject=connection.external_subject,
                external_tenant=connection.external_tenant,
                issuer=connection.issuer,
                config_fingerprint=connection.config_fingerprint,
                drive_id=request.drive_id,
                root_id=request.root_id,
                workspace_id=request.destination.workspace_id,
                project_id=request.destination.project_id,
                parent_id=request.destination.parent_id,
                request_json=payload,
                request_sha256=policy_digest(payload),
                status="reviewed",
                revision=1,
                reviewed_at=capture.captured_at,
                reviewed_expires_at=capture.expires_at,
            )
            session.add(mapping)
            await session.flush()
        baseline, _ = await self._baseline(tenant, mapping)
        revision = (latest or 0) + 1
        if revision > 2147483646:
            raise _conflict("SOURCE_POLICY_CONFLICT")
        immutable = {
            "request": payload,
            "authority": capture.authority,
            "accepted_baseline": baseline,
            "prepared_session_hash": session_hash,
            "preview_sha256": capture.preview_sha256,
            "preview_complete": capture.preview_complete,
            "preview_collisions": capture.preview_collisions,
            "root_kind": capture.root_kind,
            "validation": validation_reference(
                capture.validation, mapping_id, capture.validation_mapping_revision
            ),
        }
        identifier = str(uuid4())
        sha256 = policy_digest(immutable)
        policy = SourceMappingPolicy(
            id=identifier,
            tenant_id=tenant,
            owner=owner,
            mapping_id=mapping.id,
            revision=revision,
            mapping_revision=revision,
            authority_sha256=capture.authority_sha256,
            policy_json=immutable,
            policy_sha256=sha256,
            root_ancestry_json=list(capture.root_ancestry),
            review_id=identifier,
            review_digest=policy_digest([mapping.id, identifier, revision, sha256]),
            review_expires_at=capture.expires_at,
        )
        session.add(policy)
        await session.flush()
        return await self._record(tenant, owner, request.operation_id, "review", policy, latest, digest)

    async def apply(
        self,
        tenant: str,
        owner: str,
        mapping_id: str,
        request: SourcePolicyApplyInput,
        session_hash: str,
        capture: PolicyCapture,
        *,
        at=None,
    ):
        session = self._require_session()
        identity = await session.scalar(
            select(SourceMapping.connection_id).where(
                SourceMapping.id == mapping_id,
                SourceMapping.tenant_id == tenant,
                SourceMapping.owner == owner,
            )
        )
        if identity is None:
            raise _conflict("SOURCE_UNAVAILABLE")
        connection = await self._connection(tenant, owner, identity)
        mapping = await self._mapping(tenant, owner, mapping_id)
        digest = policy_digest(["apply", mapping_id, request.model_dump(mode="json")])
        previous = await self.receipt(tenant, owner, request.operation_id, "apply", digest)
        if previous is not None:
            return previous
        self._fresh(connection, capture)
        baseline, state = await self._baseline(tenant, mapping)
        policy = await session.scalar(
            select(SourceMappingPolicy).where(
                SourceMappingPolicy.id == request.review_id,
                SourceMappingPolicy.tenant_id == tenant,
                SourceMappingPolicy.owner == owner,
                SourceMappingPolicy.mapping_id == mapping_id,
            )
        )
        now = at or datetime.now(UTC)
        if (
            policy is None
            or mapping.status == "retired"
            or policy.accepted_at is not None
            or policy.revision != request.expected_revision
            or policy.revision != await self.latest(tenant, mapping_id)
            or policy.review_expires_at <= now
            or policy.review_digest != request.review_digest
            or policy.policy_json.get("prepared_session_hash") != session_hash
            or policy.policy_json.get("accepted_baseline") != baseline
            or policy.authority_sha256 != capture.authority_sha256
            or tuple(policy.root_ancestry_json) != capture.root_ancestry
            or policy.policy_json.get("preview_sha256") != capture.preview_sha256
            or policy.policy_json.get("root_kind", "folder") != capture.root_kind
            or policy.policy_json.get("validation")
            != validation_reference(
                capture.validation,
                (policy.policy_json.get("validation") or {}).get("mapping_id"),
                capture.validation_mapping_revision,
            )
            or policy.policy_sha256 != policy_digest(policy.policy_json)
        ):
            raise _conflict("SOURCE_POLICY_CONFLICT")
        active = await session.scalar(
            select(SourceSyncRun.id)
            .where(
                SourceSyncRun.tenant_id == tenant,
                SourceSyncRun.mapping_id == mapping_id,
                SourceSyncRun.status.in_(ACTIVE_RUNS),
            )
            .limit(1)
        )
        if active is not None:
            raise _conflict("SOURCE_RUN_ACTIVE")
        selected = MappingReviewInput.model_validate(policy.policy_json["request"])
        if capture.preview_collisions or not capture.preview_complete:
            raise _conflict("SOURCE_MAPPING_COLLISION")
        mapping.revision, mapping.status = policy.revision, "active"
        mapping.workspace_id, mapping.project_id, mapping.parent_id = (
            selected.destination.workspace_id,
            selected.destination.project_id,
            selected.destination.parent_id,
        )
        mapping.request_json, mapping.request_sha256 = (
            selected.model_dump(mode="json"),
            policy_digest(selected.model_dump(mode="json")),
        )
        mapping.config_fingerprint = connection.config_fingerprint
        mapping.updated_at = now
        policy.accepted_by, policy.accepted_session_hash = owner, session_hash
        policy.accepted_operation_id, policy.accepted_at = request.operation_id, now
        await session.flush()
        if state is None:
            state = SourceSyncState(
                mapping_id=mapping_id, tenant_id=tenant, accepted_policy_id=policy.id, revision=1
            )
            session.add(state)
        else:
            state.accepted_policy_id, state.revision = policy.id, state.revision + 1
        state.enabled, state.cursor_ciphertext = True, None
        state.next_run_at, state.updated_at = next_occurrence(selected.schedule, now), now
        await session.flush()
        return await self._record(
            tenant, owner, request.operation_id, "apply", policy, policy.revision, digest
        )


@service(name="content_sources.policy_service")
class SourcePolicies:
    def __init__(
        self,
        records: SourcePolicyRepository,
        reviews: SourceMappingReviews,
        preview: SourceMappingPreview,
        sessions: SourceBrowserSessions,
        settings: ContentSourceSettings,
        validations: SourceMappingValidations,
    ):
        self.records, self.reviews, self.preview, self.sessions = records, reviews, preview, sessions
        self.settings = settings
        self.validations = validations

    def _limits(self, selected):
        self.settings.synchronization_options()
        if (
            selected.schedule.kind == "interval"
            and not self.settings.sync_min_interval_seconds
            <= selected.schedule.seconds
            <= self.settings.sync_max_interval_seconds
        ):
            raise _conflict("SOURCE_POLICY_LIMIT")

    async def review_mapping(self, actor, tenant, review_id):
        await self.reviews.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(read_only=False):
            policy = await self.records._require_session().scalar(
                select(SourceMappingPolicy).where(
                    SourceMappingPolicy.id == review_id,
                    SourceMappingPolicy.tenant_id == tenant,
                    SourceMappingPolicy.owner == actor,
                )
            )
            if policy is None:
                raise SourceError("access_denied")
            selected = MappingReviewInput.model_validate(policy.policy_json["request"])
            await self._scope(actor, tenant, selected, policy.mapping_id)
            return policy.mapping_id

    @policy_deadline
    async def items(self, actor, tenant, review_id, *, limit=25, cursor=None, browser_session=None):
        _no_remote_unit()
        if type(limit) is not int or not 1 <= limit <= 100:
            raise SourceError("invalid_cursor")
        mapping_id = await self.review_mapping(actor, tenant, review_id)
        async with primary_authority(read_only=False):
            policy = await self.records._require_session().get(SourceMappingPolicy, review_id)
            selected = MappingReviewInput.model_validate(policy.policy_json["request"])
            await self._scope(actor, tenant, selected, mapping_id)
            if policy.review_expires_at <= datetime.now(UTC):
                raise _conflict("SOURCE_REVIEW_EXPIRED")
        if policy.policy_json.get("validation") is not None:
            return await self._sealed_items(
                actor,
                tenant,
                browser_session,
                policy,
                selected,
                limit=limit,
                cursor=cursor,
            )
        offset = 0
        vault = self.reviews.connections.vault
        if cursor is not None:
            try:
                if not isinstance(cursor, str) or len(cursor) > 4096:
                    raise ValueError
                data = vault.decrypt(
                    tenant,
                    actor,
                    review_id,
                    "review-page",
                    base64.b64decode(cursor, altchars=b"-_", validate=True),
                )
                offset = data["offset"]
                if data["digest"] != policy.review_digest or type(offset) is not int or not 0 < offset < 100:
                    raise ValueError
            except Exception:
                raise SourceError("invalid_cursor") from None
        preview = await self.preview.capture(actor, tenant, selected, mapping_id=mapping_id)
        if preview.sha256 != policy.policy_json.get("preview_sha256"):
            raise _conflict("SOURCE_REVIEW_CHANGED")
        await self.reviews.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(read_only=False):
            await self._scope(actor, tenant, selected, mapping_id)
            connection = await self.reviews.connections.connections.owned(
                tenant, actor, selected.connection_id, lock=True
            )
            if (
                connection is None
                or connection.revision != preview.connection_revision
                or source_authority(connection)[1] != policy.authority_sha256
            ):
                raise SourceError("authority_changed")
            current = await self.records._mapping(tenant, actor, mapping_id)
            baseline, _ = await self.records._baseline(tenant, current)
            rows = list(
                (
                    await self.records._require_session().scalars(
                        select(SourceObject).where(
                            SourceObject.tenant_id == tenant,
                            SourceObject.mapping_id == mapping_id,
                            SourceObject.item_id.in_([item["item_id"] for item in preview.items]),
                        )
                    )
                ).all()
            )
            objects = {row.item_id: row for row in rows}
            values = []
            for item in preview.items[offset : offset + limit]:
                origin = objects.get(item["item_id"])
                action = (
                    "skip"
                    if item["kind"] != "file" or item["reason"]
                    else (
                        "create"
                        if origin is None or origin.published_native_version_id is None
                        else "move"
                        if origin.remote_name != item["name"]
                        or origin.remote_ancestry_json != item["ancestry"]
                        else "replace"
                    )
                )
                values.append({**item, "action": action})
            next_offset = offset + len(values)
            next_cursor = (
                base64.urlsafe_b64encode(
                    vault.encrypt(
                        tenant,
                        actor,
                        review_id,
                        "review-page",
                        {"digest": policy.review_digest, "offset": next_offset},
                    )
                ).decode()
                if next_offset < len(preview.items)
                else None
            )
            return SourceReviewPage(
                review_id=review_id,
                normalized_policy=selected,
                next_occurrence_at=next_occurrence(selected.schedule, datetime.now(UTC)),
                policy_revision=policy.revision,
                review_digest=policy.review_digest,
                destination=SourceDestinationPresentation(
                    segments=[
                        SourceDestinationSegment(id=segment.id, kind=segment.kind, name=segment.name)
                        for segment in reversed(
                            await self.reviews.authority.destination(
                                actor,
                                tenant,
                                selected.destination,
                                write=True,
                            )
                        )
                    ]
                ),
                expires_at=policy.review_expires_at,
                items=values,
                next_cursor=next_cursor,
                enumeration_complete=preview.complete,
                total=len(preview.items) if preview.complete else None,
                observed_count=len(preview.items),
                known_bytes=sum(item["size_bytes"] or 0 for item in preview.items if item["kind"] == "file"),
                unknown_size_count=sum(
                    item["size_bytes"] is None for item in preview.items if item["kind"] == "file"
                ),
                root_kind=policy.policy_json.get("root_kind", "folder"),
                can_apply=policy.accepted_at is None
                and not preview.collisions
                and preview.complete
                and policy.revision == await self.records.latest(tenant, mapping_id)
                and baseline == policy.policy_json.get("accepted_baseline")
                and policy.review_expires_at > datetime.now(UTC),
            )

    async def _sealed_items(self, actor, tenant, browser_session, policy, selected, *, limit, cursor):
        if (
            not browser_session
            or policy.policy_json.get("prepared_session_hash")
            != hashlib.sha256(browser_session.encode()).hexdigest()
        ):
            raise SourceError("access_denied")
        reference = policy.policy_json["validation"]
        vault = self.reviews.connections.vault
        validation_cursor = None
        if cursor is not None:
            try:
                if not isinstance(cursor, str) or len(cursor) > 4096:
                    raise ValueError
                value = vault.decrypt(
                    tenant,
                    actor,
                    policy.id,
                    "sealed-review-page",
                    base64.b64decode(cursor, altchars=b"-_", validate=True),
                )
                if set(value) != {"digest", "cursor"} or value["digest"] != policy.review_digest:
                    raise ValueError
                validation_cursor = value["cursor"]
                if not isinstance(validation_cursor, str):
                    raise ValueError
            except Exception:
                raise SourceError("invalid_cursor") from None
        sealed, selected, validation_revision = await self._seal(
            actor,
            tenant,
            browser_session,
            UUID(reference["id"]),
            selected,
            mapping_id=reference["mapping_id"],
        )
        if reference != validation_reference(sealed, reference["mapping_id"], validation_revision):
            raise _conflict("SOURCE_REVIEW_CHANGED")
        page = await self.validations.validation_items(
            actor,
            tenant,
            browser_session,
            sealed.validation_id,
            limit=limit,
            cursor=validation_cursor,
        )
        await self.sessions.require(actor, browser_session)
        await self.reviews.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(read_only=False):
            await self._scope(actor, tenant, selected, policy.mapping_id)
            current = await self.records._require_session().scalar(
                select(SourceMappingPolicy)
                .where(
                    SourceMappingPolicy.id == policy.id,
                    SourceMappingPolicy.tenant_id == tenant,
                    SourceMappingPolicy.owner == actor,
                )
                .execution_options(populate_existing=True)
            )
            if (
                current is None
                or current.review_digest != policy.review_digest
                or current.policy_sha256 != policy_digest(current.policy_json)
                or current.review_expires_at <= datetime.now(UTC)
            ):
                raise _conflict("SOURCE_REVIEW_CHANGED")
            row = await self.validations.locked_assert_eligible(actor, tenant, browser_session, sealed)
            identities = [item.item_id for item in page.items]
            entries = {
                item.item_id: item
                for item in await self.records._require_session().scalars(
                    select(SourceMappingValidationEntry).where(
                        SourceMappingValidationEntry.tenant_id == tenant,
                        SourceMappingValidationEntry.validation_id == sealed.validation_id,
                        SourceMappingValidationEntry.item_id.in_(identities),
                    )
                )
            }
            if set(entries) != set(identities) or page.revision != sealed.revision:
                raise _conflict("SOURCE_REVIEW_CHANGED")
            values = await self.validations._namespace(row, selected, [entries[key] for key in identities])
            mapping = await self.records._mapping(tenant, actor, policy.mapping_id)
            baseline, _ = await self.records._baseline(tenant, mapping)
            destination = await self.reviews.authority.destination(
                actor, tenant, selected.destination, write=True
            )
            next_cursor = (
                base64.urlsafe_b64encode(
                    vault.encrypt(
                        tenant,
                        actor,
                        policy.id,
                        "sealed-review-page",
                        {"digest": policy.review_digest, "cursor": page.next_cursor},
                    )
                ).decode()
                if page.next_cursor is not None
                else None
            )
            return SourceReviewPage(
                review_id=current.id,
                normalized_policy=selected,
                next_occurrence_at=next_occurrence(selected.schedule, datetime.now(UTC)),
                policy_revision=current.revision,
                review_digest=current.review_digest,
                expires_at=current.review_expires_at,
                validation_id=sealed.validation_id,
                root_kind=row.root_kind,
                items=values,
                next_cursor=next_cursor,
                enumeration_complete=True,
                total=None,
                observed_count=None,
                known_bytes=None,
                unknown_size_count=None,
                can_apply=current.accepted_at is None
                and current.revision == await self.records.latest(tenant, mapping.id)
                and baseline == current.policy_json.get("accepted_baseline"),
                destination=SourceDestinationPresentation(
                    segments=[
                        SourceDestinationSegment(id=segment.id, kind=segment.kind, name=segment.name)
                        for segment in reversed(destination)
                    ]
                ),
            )

    async def _scope(self, actor, tenant, request, mapping_id):
        connection = await self.reviews.connections.connections.owned(tenant, actor, request.connection_id)
        if connection is None:
            raise SourceError("access_denied")
        await self.reviews.authority.destination(actor, tenant, request.destination, write=True)
        if mapping_id is not None:
            mapping = await self.reviews.records.owned(tenant, actor, mapping_id)
            if mapping is None:
                raise SourceError("access_denied")
            from koinon.integrations.content_sources.mapping_service import SourceMappings

            await self.reviews.authority.destination(
                actor, tenant, SourceMappings.destination(mapping), write=True
            )

    async def _audit(self, actor, tenant, result):
        await self.reviews.authority.catalog._audit(
            actor,
            tenant,
            "source.policy." + result.action,
            result.mapping_id,
            {
                "receipt_id": result.receipt_id,
                "operation_id": result.operation_id,
                "policy_id": result.policy_id,
                "revision": result.result_policy_revision,
            },
        )

    async def _seal(self, actor, tenant, session, identifier, selected, *, mapping_id=None):
        row = await self.validations._load(actor, tenant, session, identifier)
        if row.state != "complete" or not row.root_captured:
            raise _conflict("SOURCE_VALIDATION_CHANGED")
        selected = effective_selection(selected, row.root_kind)
        sealed = await self.validations.seal_for_review(
            actor,
            tenant,
            session,
            identifier,
            selected,
            mapping_id=mapping_id,
            expected_revision=row.expected_revision,
        )
        return sealed, selected, row.expected_revision

    async def _capture(
        self,
        actor,
        tenant,
        session,
        selected,
        row,
        proof,
        now,
        expires,
        preview,
        sealed,
        validation_revision=None,
    ):
        root_kind = proof.root_kind(selected.root_id)
        ancestry = (selected.root_id, *proof.ancestors(selected.root_id))
        authority, sha256 = source_authority(row)
        if sealed is not None:
            if sealed_root(sealed, selected.root_id) != (root_kind, ancestry):
                raise _conflict("SOURCE_VALIDATION_CHANGED")
            await self.validations.locked_assert_eligible(actor, tenant, session, sealed)
            return PolicyCapture(
                row.revision,
                authority,
                sha256,
                ancestry,
                sealed.manifest_sha256,
                True,
                0,
                now,
                min(expires, sealed.expires_at),
                root_kind,
                sealed,
                validation_revision,
            )
        if preview is None or row.revision != preview.connection_revision:
            raise SourceError("authority_changed")
        return PolicyCapture(
            row.revision,
            authority,
            sha256,
            ancestry,
            preview.sha256,
            preview.complete,
            preview.collisions,
            now,
            expires,
            root_kind,
        )

    @policy_deadline
    async def review(
        self,
        actor,
        tenant,
        browser_session,
        request: SourcePolicyReviewInput,
        *,
        mapping_id=None,
        expected_revision=None,
    ):
        _no_remote_unit()
        await self.sessions.require(actor, browser_session)
        digest = policy_digest(["review", mapping_id, expected_revision, review_payload(request)])
        await self.reviews.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(read_only=False):
            await self._scope(actor, tenant, request, mapping_id)
            previous = await self.records.receipt(tenant, actor, request.operation_id, "review", digest)
            if previous is not None:
                return previous
        self._limits(request)
        selected = MappingReviewInput.model_validate(
            request.model_dump(exclude={"operation_id", "expected_revision", "validation_id"})
        )
        sealed, preview, validation_revision = None, None, None
        if request.validation_id is not None:
            sealed, selected, validation_revision = await self._seal(
                actor,
                tenant,
                browser_session,
                request.validation_id,
                selected,
                mapping_id=mapping_id,
            )
        else:
            preview = await self.preview.capture(actor, tenant, selected, mapping_id=mapping_id)
        async with self.reviews.verified(
            actor,
            tenant,
            selected,
            existing_mapping_id=mapping_id,
            before_commit=lambda: self.sessions.require(actor, browser_session),
        ) as (row, proof, _, _, now, expires):
            await self._scope(actor, tenant, request, mapping_id)
            capture = await self._capture(
                actor,
                tenant,
                browser_session,
                selected,
                row,
                proof,
                now,
                expires,
                preview,
                sealed,
                validation_revision,
            )
            previous = await self.records.receipt(tenant, actor, request.operation_id, "review", digest)
            result = await self.records.review(
                tenant,
                actor,
                request,
                hashlib.sha256(browser_session.encode()).hexdigest(),
                capture,
                mapping_id=mapping_id,
                expected_revision=expected_revision,
            )
            if previous is None:
                await self._audit(actor, tenant, result)
            return result

    @policy_deadline
    async def apply(self, actor, tenant, browser_session, mapping_id, request: SourcePolicyApplyInput):
        _no_remote_unit()
        await self.sessions.require(actor, browser_session)
        digest = policy_digest(["apply", mapping_id, request.model_dump(mode="json")])
        await self.reviews.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(read_only=False):
            mapping = await self.reviews.records.owned(tenant, actor, mapping_id)
            if mapping is None:
                raise SourceError("access_denied")
            from koinon.integrations.content_sources.mapping_service import SourceMappings

            await self.reviews.authority.destination(
                actor, tenant, SourceMappings.destination(mapping), write=True
            )
            previous = await self.records.receipt(tenant, actor, request.operation_id, "apply", digest)
            if previous is not None:
                return previous
            policy = await self.records._require_session().scalar(
                select(SourceMappingPolicy).where(
                    SourceMappingPolicy.tenant_id == tenant,
                    SourceMappingPolicy.owner == actor,
                    SourceMappingPolicy.mapping_id == mapping_id,
                    SourceMappingPolicy.id == request.review_id,
                )
            )
            if policy is None:
                raise SourceError("access_denied")
            selected = MappingReviewInput.model_validate(policy.policy_json["request"])
            await self._scope(actor, tenant, selected, mapping_id)
        self._limits(selected)
        sealed, preview, validation_revision = None, None, None
        reference = policy.policy_json.get("validation")
        if reference is not None:
            sealed, selected, validation_revision = await self._seal(
                actor,
                tenant,
                browser_session,
                UUID(reference["id"]),
                selected,
                mapping_id=reference["mapping_id"],
            )
        else:
            preview = await self.preview.capture(actor, tenant, selected, mapping_id=mapping_id)
        async with self.reviews.verified(
            actor,
            tenant,
            selected,
            existing_mapping_id=mapping_id,
            before_commit=lambda: self.sessions.require(actor, browser_session),
        ) as (row, proof, _, _, now, expires):
            await self._scope(actor, tenant, selected, mapping_id)
            if preview is not None:
                current_items = [dict(item) for item in preview.items]
                await self.preview.local_conflicts(
                    actor, tenant, selected, current_items, mapping_id=mapping_id
                )
                if any(item["collision"] != "none" for item in current_items) or not preview.complete:
                    raise _conflict("SOURCE_MAPPING_COLLISION")
            capture = await self._capture(
                actor,
                tenant,
                browser_session,
                selected,
                row,
                proof,
                now,
                expires,
                preview,
                sealed,
                validation_revision,
            )
            previous = await self.records.receipt(tenant, actor, request.operation_id, "apply", digest)
            result = await self.records.apply(
                tenant,
                actor,
                mapping_id,
                request,
                hashlib.sha256(browser_session.encode()).hexdigest(),
                capture,
            )
            if previous is None:
                await self._audit(actor, tenant, result)
            return result
