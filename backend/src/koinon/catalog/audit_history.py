# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retained typed provenance admits audit identities before payload projection."""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import BigInteger, String, case, cast, func, literal, select, text, union, union_all
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import DBAPIError

from koinon.catalog.entities import AuditEvent, Membership
from koinon.catalog.history_entities import CatalogHistoryEdge, CatalogHistoryIdentity
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.sync_entities import (
    SourceControlOperation,
    SourceFolderPublication,
    SourceImportedAsset,
    SourcePolicyOperation,
)

CONTENT_ACTIONS = (
    "catalog.created",
    "catalog.updated",
    "catalog.moved",
    "catalog.deleted",
    "catalog.archived",
    "catalog.restored",
)


@dataclass(frozen=True, slots=True)
class AuditHistoryEvent:
    id: str
    tenant_id: str
    subject: str
    action: str
    resource_id: str | None
    details: dict
    created_at: datetime


@asynccontextmanager
async def bounded_audit_query(session):
    previous = await session.scalar(text("SELECT current_setting('statement_timeout')"))
    await session.execute(text("SET LOCAL statement_timeout = '2s'"))
    try:
        yield
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "57014":
            raise ServiceUnavailableException(
                "Audit history is temporarily unavailable", code="AUDIT_UNAVAILABLE"
            ) from None
        raise
    else:
        await session.execute(
            text("SELECT set_config('statement_timeout', :value, true)"), {"value": previous}
        )


def history_eligibility(tenant_id):
    """Keep recursion identity-only: historical paths may be deep, cyclic or shared."""
    identity, edge = CatalogHistoryIdentity, CatalogHistoryEdge
    roots = union(
        select(SourceImportedAsset.tenant_id, SourceImportedAsset.asset_id.label("resource_id")).where(
            SourceImportedAsset.tenant_id == tenant_id
        ),
        select(SourceImportedAsset.tenant_id, SourceImportedAsset.source_id.label("resource_id")).where(
            SourceImportedAsset.tenant_id == tenant_id
        ),
        select(
            SourceFolderPublication.tenant_id, SourceFolderPublication.local_folder_id.label("resource_id")
        ).where(SourceFolderPublication.tenant_id == tenant_id),
    ).subquery()
    protected = select(roots.c.tenant_id, roots.c.resource_id).cte("audit_protected", recursive=True)
    protected = protected.union(
        select(edge.tenant_id, edge.dependent_id)
        .join(
            protected, (edge.tenant_id == protected.c.tenant_id) & (edge.origin_id == protected.c.resource_id)
        )
        .where(edge.tenant_id == tenant_id)
    )
    # An old parent's incomplete *history* does not taint a new local child.
    # An explicit derivation from incomplete content does, including its descendants.
    unknown = (
        select(edge.tenant_id, edge.dependent_id.label("resource_id"))
        .join(identity, (identity.tenant_id == edge.tenant_id) & (identity.resource_id == edge.origin_id))
        .where(edge.tenant_id == tenant_id, edge.kind == "curated_source", identity.coverage != "complete")
        .cte("audit_unknown_derivations", recursive=True)
    )
    unknown = unknown.union(
        select(edge.tenant_id, edge.dependent_id)
        .join(unknown, (edge.tenant_id == unknown.c.tenant_id) & (edge.origin_id == unknown.c.resource_id))
        .where(edge.tenant_id == tenant_id)
    )
    return select(identity.resource_id).where(
        identity.tenant_id == tenant_id,
        identity.coverage == "complete",
        identity.resource_id.not_in(select(protected.c.resource_id)),
        identity.resource_id.not_in(select(unknown.c.resource_id)),
    )


def eligible_events(tenant_id):
    event = AuditEvent
    details = cast(event.details, JSONB)

    def projection(payload, catalog_resource=None):
        return select(
            event.id,
            event.tenant_id,
            event.subject,
            event.action,
            event.resource_id,
            payload.label("details"),
            event.created_at,
            (catalog_resource if catalog_resource is not None else literal(None, String)).label(
                "catalog_resource_id"
            ),
        ).where(event.tenant_id == tenant_id)

    local = projection(details, event.resource_id).where(
        event.action.in_(CONTENT_ACTIONS),
        event.resource_id.in_(history_eligibility(tenant_id)),
    )
    policy = SourcePolicyOperation
    policy_events = (
        projection(
            func.jsonb_build_object(
                "receipt_id",
                policy.id,
                "operation_id",
                policy.operation_id,
                "policy_id",
                policy.policy_id,
                "revision",
                policy.result_policy_revision,
            )
        )
        .join(
            policy,
            (policy.tenant_id == event.tenant_id)
            & (policy.owner == event.subject)
            & (policy.mapping_id == event.resource_id)
            & (policy.id == details["receipt_id"].astext)
            & (policy.operation_id == details["operation_id"].astext),
        )
        .where(
            policy.action.in_(("review", "apply")), event.action == literal("source.policy.") + policy.action
        )
    )
    control = SourceControlOperation
    outcome = cast(control.result_json, JSONB)["disposition"].astext
    controls = (
        projection(
            func.jsonb_build_object(
                "receipt_id",
                control.id,
                "operation_id",
                control.operation_id,
                "control_revision",
                control.result_revision,
                "outcome",
                outcome,
            )
        )
        .join(
            control,
            (control.tenant_id == event.tenant_id)
            & (control.owner == event.subject)
            & (control.mapping_id == event.resource_id)
            & (control.id == details["receipt_id"].astext)
            & (control.operation_id == details["operation_id"].astext),
        )
        .where(
            control.action.in_(("sync", "pause", "resume", "cancel", "retry", "retire")),
            event.action == literal("source.") + control.action,
            outcome.in_(("queued", "paused", "active", "stopping", "reconciling", "retired")),
        )
    )
    role = case(
        (
            details["role"].astext.in_(("viewer", "analyst", "editor", "operator", "admin")),
            details["role"].astext,
        )
    )
    active = case((func.jsonb_typeof(details["active"]) == "boolean", details["active"]))
    memberships = projection(
        func.jsonb_strip_nulls(
            func.jsonb_build_object(
                "role",
                role,
                "active",
                active,
                "subject",
                case((event.action == "membership.created", Membership.subject)),
            )
        )
    ).join(Membership, (Membership.tenant_id == event.tenant_id) & (Membership.id == event.resource_id))
    memberships = memberships.where(event.action.in_(("membership.created", "membership.updated")))
    connection = PersonalSourceConnection
    revision = case(
        (details["revision"].astext.op("~")("^[0-9]{1,18}$"), cast(details["revision"].astext, BigInteger))
    )
    accounts = (
        projection(
            func.jsonb_build_object(
                "provider",
                connection.provider,
                "revision",
                revision,
                "outcome",
                literal("success"),
            )
        )
        .join(
            connection,
            (connection.tenant_id == event.tenant_id)
            & (connection.owner == event.subject)
            & (connection.id == event.resource_id),
        )
        .where(
            event.action.in_(
                (
                    "source.authorization_requested",
                    "source.connected",
                    "source.disconnected",
                    "source.refresh_completed",
                )
            ),
            connection.provider.in_(("google_drive", "onedrive", "sharepoint")),
            func.jsonb_typeof(details["revision"]) == "number",
            revision.is_not(None),
            details["outcome"].astext == "success",
        )
    )
    return union_all(local, policy_events, controls, memberships, accounts).cte("eligible_audit")
