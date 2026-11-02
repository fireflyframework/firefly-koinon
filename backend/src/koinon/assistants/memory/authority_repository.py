# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A fresh single-statement observation of fixed personal-memory authority material."""

import json
from collections.abc import Sequence
from typing import Any

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository, transactional
from pyfly.data.transaction import Isolation, Propagation
from sqlalchemy import Text, case, cast, exists, func, literal, or_, select, union_all
from sqlalchemy.orm import aliased
from sqlalchemy.sql.selectable import FromClause

from koinon.assistants.entities import ChatEvent, ChatMessage, ChatRun, ChatThread, ToolResult
from koinon.assistants.history.entities import ChatFolder
from koinon.assistants.memory.authority_mappers import partition_material
from koinon.assistants.memory.entities import ChatMemoryManifest
from koinon.assistants.memory.mappers import digest
from koinon.assistants.memory.repositories import authority_bytes, payload_bytes
from koinon.authorized_applications.entities import AuthorizedApplication
from koinon.catalog.entities import CatalogEntry
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.curated.entities import CuratedCatalogState, CuratedSourceRoot
from koinon.knowledge.entities import DomainBinding
from koinon.mcp_applications.entities import McpOAuthClientRegistration
from koinon.organization_chat.entities import OrganizationChatSetting
from koinon.tokens.entities import PersonalToken

MAX_PAGE_RESULT_BYTES = 32 * 1024 * 1024


def row(tag: str, columns: Sequence[Any]):
    if len(columns) > 20:
        raise ValueError("Personal memory authority projection exceeds its bounded width")
    return select(
        literal(tag),
        *(cast(value, Text) for value in columns),
        *(literal(None, Text) for _ in range(20 - len(columns))),
    )


@repository(name="assistants.memory_authority")
class ChatMemoryAuthorityRepository(Repository[ChatMemoryManifest, str]):
    @transactional(
        datasource="primary",
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def observe_many(
        self,
        values,
        members: FromClause,
        token_id: str | None,
        deployment_sha256: str,
        current_evidence=(),
        captures=(),
        *,
        egress_pins=None,
        egress_manifests=None,
        reader_subject=None,
        additional_token_ids=(),
        release=None,
        additional_asset_ids=(),
    ):
        return await self.observe_bound(
            values,
            members,
            token_id,
            deployment_sha256,
            current_evidence,
            captures,
            egress_pins=egress_pins,
            egress_manifests=egress_manifests,
            reader_subject=reader_subject,
            additional_token_ids=additional_token_ids,
            release=release,
            additional_asset_ids=additional_asset_ids,
        )

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRED, read_only=True, read_from_primary=True
    )
    async def observe_bound(
        self,
        values,
        members: FromClause,
        token_id: str | None,
        deployment_sha256: str,
        current_evidence=(),
        captures=(),
        *,
        egress_pins=None,
        egress_manifests=None,
        reader_subject=None,
        additional_token_ids=(),
        release=None,
        additional_asset_ids=(),
    ):
        maximum = 200 if egress_pins is not None else 51
        if (not values and not current_evidence) or len(values) > maximum or len(current_evidence) > maximum:
            raise AccessDenied("Request a smaller conversation page", code="MEMORY_PAGE_TOO_WIDE")
        first = values[0] if values else current_evidence[0]
        subject, tenant_id = first.subject, first.tenant_id
        if any(
            (value.subject, value.tenant_id) != (subject, tenant_id) for value in (*values, *current_evidence)
        ):
            raise AccessDenied("Personal memory belongs to one account", code="MEMORY_UNAVAILABLE")
        run_ids = tuple(sorted({ref.run_id for value in values for ref in value.dependencies}))
        asset_ids = tuple(
            sorted(
                {key for value in (*values, *current_evidence) for key in value.asset_ids}
                | set(additional_asset_ids)
            )
        )
        thread_ids = tuple(sorted({value.thread_id for value in (*values, *current_evidence)}))
        current_run_ids = tuple(sorted({value.run_id for value in (*values, *current_evidence)}))
        current_result_ids = tuple(
            sorted({result.id for value in current_evidence for result in value.results})
        )
        if len(run_ids) > 512 or len(asset_ids) > 512:
            raise AccessDenied("Request a smaller conversation page", code="MEMORY_PAGE_TOO_WIDE")
        result_ids = tuple(
            sorted({pin.id for value in values for ref in value.dependencies for pin in ref.result_pins})
        )
        generation_ids = tuple(
            sorted({ref.generation_id for value in values for ref in value.dependencies if ref.generation_id})
        )
        if len(result_ids) > 1024:
            raise AccessDenied("Request a smaller conversation page", code="MEMORY_PAGE_TOO_WIDE")
        session = self._require_session()
        result_size = (
            select(func.coalesce(func.sum(payload_bytes(session.get_bind().dialect.name)), 0))
            .where(ToolResult.id.in_(result_ids))
            .scalar_subquery()
        )
        message_ids = tuple(
            sorted(
                {
                    key
                    for value in values
                    for ref in value.dependencies
                    for key in (ref.user_message_id, ref.answer_message_id)
                }
            )
        )
        message_size = (
            select(
                func.coalesce(func.sum(authority_bytes(session.get_bind().dialect.name, ChatMessage.text)), 0)
            )
            .where(ChatMessage.id.in_(message_ids))
            .scalar_subquery()
        )
        egress_size = (
            select(func.coalesce(func.sum(payload_bytes(session.get_bind().dialect.name)), 0))
            .where(ToolResult.id.in_(tuple(egress_pins or {})))
            .scalar_subquery()
        )
        result_fits = result_size + message_size + egress_size <= MAX_PAGE_RESULT_BYTES
        source_threads = select(ChatRun.thread_id).where(
            ChatRun.id.in_(run_ids), ChatRun.tenant_id == tenant_id
        )
        threads = select(ChatThread.id).where(
            ChatThread.tenant_id == tenant_id,
            or_(ChatThread.id.in_(thread_ids), ChatThread.id.in_(source_threads)),
        )
        folders = select(ChatThread.folder_id).where(ChatThread.id.in_(threads))
        roots = (
            select(CuratedSourceRoot)
            .where(CuratedSourceRoot.item_id.in_(asset_ids), CuratedSourceRoot.tenant_id == tenant_id)
            .cte("memory_roots")
        )
        seeds = union_all(
            select(CatalogEntry.id).where(
                CatalogEntry.id.in_(asset_ids), CatalogEntry.tenant_id == tenant_id
            ),
            select(roots.c.source_asset_id),
        )
        ancestry = (
            select(CatalogEntry.id, CatalogEntry.parent_id, literal(0).label("depth"))
            .where(CatalogEntry.id.in_(seeds), CatalogEntry.tenant_id == tenant_id)
            .cte("memory_ancestry", recursive=True)
        )
        parent = aliased(CatalogEntry)
        ancestry = ancestry.union_all(
            select(parent.id, parent.parent_id, ancestry.c.depth + 1)
            .join(ancestry, parent.id == ancestry.c.parent_id)
            .where(parent.tenant_id == tenant_id, ancestry.c.depth < 16)
        )
        ids = select(ancestry.c.id)
        clock = (
            func.statement_timestamp()
            if session.get_bind().dialect.name == "postgresql"
            else func.strftime("%Y-%m-%d %H:%M:%f", "now")
        )
        private_run = aliased(ChatRun)
        private_thread = exists(
            select(ToolResult.id)
            .join(private_run, private_run.id == ToolResult.run_id)
            .where(private_run.thread_id == ChatThread.id, ToolResult.kind == "attachment")
        ).correlate(ChatThread)
        statements = [
            row(
                "current_run",
                [ChatRun.id, ChatRun.thread_id, ChatRun.tenant_id, ChatRun.scope, ChatRun.access_token_id],
            ).where(ChatRun.id.in_(tuple(item.run_id for item in current_evidence))),
            row(
                "current_result",
                [
                    ToolResult.id,
                    ToolResult.run_id,
                    ToolResult.kind,
                    ToolResult.payload["asset_ids"],
                    ToolResult.payload["origin_token_id"].as_string(),
                    ToolResult.payload["generation_id"].as_string(),
                ],
            ).where(ToolResult.id.in_(current_result_ids)),
            row("thread_private", [ChatThread.id, private_thread]).where(ChatThread.id.in_(threads)),
            row("deployment", [literal(deployment_sha256)]),
            row("target_origin", [ChatRun.id, ChatRun.access_token_id, ChatRun.scope]).where(
                ChatRun.id.in_(current_run_ids), ChatRun.tenant_id == tenant_id
            ),
            row(
                "thread",
                [
                    ChatThread.id,
                    ChatThread.tenant_id,
                    ChatThread.subject,
                    ChatThread.folder_id,
                    ChatThread.scope,
                    ChatThread.archived_at,
                    ChatThread.deleted_at,
                ],
            ).where(ChatThread.id.in_(threads)),
            row("folder", list(ChatFolder.__table__.columns)).where(ChatFolder.id.in_(folders)),
            row("org_policy", list(OrganizationChatSetting.__table__.columns)).where(
                OrganizationChatSetting.tenant_id == tenant_id
            ),
            row(
                "run",
                [
                    ChatRun.id,
                    ChatRun.thread_id,
                    ChatRun.tenant_id,
                    ChatRun.user_message_id,
                    ChatRun.message_id,
                    ChatRun.status,
                    ChatRun.scope,
                    ChatRun.access_token_id,
                    ChatRun.sequence,
                ],
            ).where(ChatRun.id.in_(run_ids), ChatRun.tenant_id == tenant_id),
            row(
                "message",
                [
                    ChatMessage.id,
                    ChatMessage.thread_id,
                    ChatMessage.role,
                    case((result_fits, ChatMessage.text), else_=None),
                    ChatMessage.status,
                    ChatMessage.answer_policy,
                    ChatMessage.created_at,
                ],
            ).where(ChatMessage.id.in_(message_ids)),
            row("result_budget", [result_fits]),
            row(
                "result",
                [
                    ToolResult.id,
                    ToolResult.run_id,
                    ToolResult.kind,
                    case((result_fits, cast(ToolResult.payload, Text)), else_=None),
                    ToolResult.payload["origin_token_id"].as_string(),
                ],
            ).where(ToolResult.id.in_(result_ids)),
            row(
                "manifest",
                [
                    ChatMemoryManifest.generation_id,
                    ChatMemoryManifest.manifest_sha256,
                    ChatMemoryManifest.run_id,
                ],
            ).where(ChatMemoryManifest.generation_id.in_(generation_ids)),
            row(
                "entry",
                [
                    CatalogEntry.id,
                    CatalogEntry.tenant_id,
                    CatalogEntry.workspace_id,
                    CatalogEntry.project_id,
                    CatalogEntry.parent_id,
                    CatalogEntry.kind,
                    CatalogEntry.status,
                    CatalogEntry.updated_at,
                ],
            ).where(CatalogEntry.id.in_(ids), CatalogEntry.tenant_id == tenant_id),
            row("binding", list(DomainBinding.__table__.columns)).where(
                DomainBinding.catalog_id.in_(ids), DomainBinding.tenant_id == tenant_id
            ),
            row("curated_state", list(CuratedCatalogState.__table__.columns)).where(
                CuratedCatalogState.item_id.in_(asset_ids), CuratedCatalogState.tenant_id == tenant_id
            ),
            row("curated_root", list(roots.c)),
            row("membership", list(members.c)).where(
                members.c.subject == subject, members.c.tenant_id == tenant_id
            ),
        ]
        membership_index = len(statements) - 1
        if release is not None:
            from koinon.exports.entities import ExportRecord
            from koinon.knowledge.curated.entities import KnowledgeIntentRow
            from koinon.sharing.entities import ConversationShare

            kind, identifier = release
            if kind == "curated":
                statement = row(
                    "egress_release",
                    [
                        KnowledgeIntentRow.id,
                        KnowledgeIntentRow.authorization_digest,
                        KnowledgeIntentRow.status.in_(("committing", "unresolved"))
                        & KnowledgeIntentRow.confirmation_key.is_not(None)
                        & (KnowledgeIntentRow.expires_at > clock),
                    ],
                ).where(
                    KnowledgeIntentRow.id == identifier,
                    KnowledgeIntentRow.tenant_id == tenant_id,
                    KnowledgeIntentRow.subject == subject,
                )
            elif kind in {"export", "share"}:
                entity = ExportRecord if kind == "export" else ConversationShare
                revoked = ExportRecord.cancelled_at if kind == "export" else ConversationShare.revoked_at
                statement = row(
                    "egress_release",
                    [entity.id, entity.review_id, revoked.is_(None) & (entity.expires_at > clock)],
                ).where(
                    entity.id == identifier, entity.tenant_id == tenant_id, entity.owner_subject == subject
                )
            else:
                raise AccessDenied("This transfer is unavailable", code="MEMORY_UNAVAILABLE")
            statements.append(statement)
        statements.extend(row("egress_asset", [literal(identifier)]) for identifier in additional_asset_ids)
        if egress_pins is not None:
            if len(egress_pins) > 2000 or len(egress_manifests or {}) > 200:
                raise AccessDenied("Request a smaller conversation selection", code="MEMORY_PAGE_TOO_WIDE")
            statements.extend(
                [
                    row(
                        "egress_result",
                        [
                            ToolResult.id,
                            ToolResult.run_id,
                            ToolResult.kind,
                            case((result_fits, cast(ToolResult.payload, Text)), else_=None),
                        ],
                    ).where(ToolResult.id.in_(tuple(egress_pins))),
                    row(
                        "egress_manifest",
                        [ChatMemoryManifest.generation_id, ChatMemoryManifest.manifest_sha256],
                    ).where(ChatMemoryManifest.generation_id.in_(tuple(egress_manifests or {}))),
                ]
            )
        if "expires_at" in members.c:
            statements[membership_index] = statements[membership_index].where(
                or_(members.c.expires_at.is_(None), members.c.expires_at > clock)
            )
        if reader_subject is not None and reader_subject != subject:
            reader_members = row("reader/membership", list(members.c)).where(
                members.c.subject == reader_subject, members.c.tenant_id == tenant_id
            )
            if "expires_at" in members.c:
                reader_members = reader_members.where(
                    or_(members.c.expires_at.is_(None), members.c.expires_at > clock)
                )
            statements.append(reader_members)
        fixed_origins = {value.origin_token_id for value in values}
        if len(additional_token_ids) > 200:
            raise AccessDenied("Select fewer originating credentials", code="MEMORY_SCOPE_TOO_WIDE")
        fixed_origins.update(additional_token_ids)
        statements.extend(row("egress_origin", [literal(identifier)]) for identifier in additional_token_ids)
        fixed_origins.update(ref.origin_token_id for value in values for ref in value.dependencies)
        fixed_origins.update(value.origin_token_id for value in current_evidence)
        fixed_origins.update(
            result.payload.get("origin_token_id") for value in current_evidence for result in value.results
        )
        token_ids = union_all(
            select(PersonalToken.id).where(PersonalToken.id.in_(tuple(sorted(fixed_origins - {None})))),
            select(ChatRun.access_token_id).where(
                or_(ChatRun.id.in_(run_ids), ChatRun.id.in_(current_run_ids))
            ),
            select(ToolResult.payload["origin_token_id"].as_string()).where(
                ToolResult.id.in_((*result_ids, *current_result_ids))
            ),
        )
        token = PersonalToken
        active = (
            select(token)
            .where(
                token.id.in_(token_ids),
                token.subject == subject,
                token.tenant_id == tenant_id,
                token.revoked_at.is_(None),
                token.expires_at > clock,
            )
            .cte("memory_tokens")
        )
        app = AuthorizedApplication
        apps = (
            select(app)
            .where(
                app.id.in_(select(active.c.authorized_application_id)),
                app.subject == subject,
                app.tenant_id == tenant_id,
                app.revoked_at.is_(None),
                app.expires_at > clock,
            )
            .cte("memory_apps")
        )
        registration = McpOAuthClientRegistration
        statements.extend(
            [
                row(
                    "token",
                    [
                        active.c.id,
                        active.c.subject,
                        active.c.tenant_id,
                        active.c.purpose,
                        active.c.authorized_application_id,
                        active.c.scopes,
                        active.c.workspace_ids,
                        active.c.asset_ids,
                        active.c.resource_ids,
                        active.c.expires_at,
                    ],
                ),
                row(
                    "application",
                    [
                        apps.c.id,
                        apps.c.subject,
                        apps.c.client_id,
                        apps.c.tenant_id,
                        apps.c.workspace_id,
                        apps.c.scopes,
                        apps.c.resource,
                        apps.c.client_registration,
                        apps.c.expires_at,
                    ],
                ),
                row(
                    "registration",
                    [
                        registration.id,
                        registration.tenant_id,
                        registration.client_id,
                        registration.enabled,
                        registration.revision,
                        registration.name,
                        registration.redirect_uris,
                        registration.scopes,
                        registration.client_secret_hash,
                    ],
                ).where(registration.client_id.in_(select(apps.c.client_id))),
            ]
        )
        caller = (
            select(token)
            .where(
                token.id == token_id,
                token.subject == (reader_subject or subject),
                token.tenant_id == tenant_id,
                token.revoked_at.is_(None),
                token.expires_at > clock,
            )
            .cte("memory_caller")
        )
        caller_apps = (
            select(app)
            .join(caller, caller.c.authorized_application_id == app.id)
            .where(
                app.subject == (reader_subject or subject),
                app.tenant_id == tenant_id,
                app.revoked_at.is_(None),
                app.expires_at > clock,
            )
            .cte("memory_caller_apps")
        )
        statements.extend(
            [
                row(
                    "caller/token",
                    [
                        caller.c.id,
                        caller.c.subject,
                        caller.c.tenant_id,
                        caller.c.purpose,
                        caller.c.authorized_application_id,
                        caller.c.scopes,
                        caller.c.workspace_ids,
                        caller.c.asset_ids,
                        caller.c.resource_ids,
                        caller.c.expires_at,
                    ],
                ),
                row(
                    "caller/application",
                    [
                        caller_apps.c.id,
                        caller_apps.c.subject,
                        caller_apps.c.client_id,
                        caller_apps.c.tenant_id,
                        caller_apps.c.workspace_id,
                        caller_apps.c.scopes,
                        caller_apps.c.resource,
                        caller_apps.c.client_registration,
                        caller_apps.c.expires_at,
                    ],
                ),
                row(
                    "caller/registration",
                    [
                        registration.id,
                        registration.tenant_id,
                        registration.client_id,
                        registration.enabled,
                        registration.revision,
                        registration.name,
                        registration.redirect_uris,
                        registration.scopes,
                        registration.client_secret_hash,
                    ],
                ).where(registration.client_id.in_(select(caller_apps.c.client_id))),
            ]
        )
        if len(captures) > maximum or any(item.run_id not in current_run_ids for item in captures):
            raise AccessDenied("Request a smaller conversation page", code="MEMORY_PAGE_TOO_WIDE")
        for capture in captures:
            current_reset = (
                select(func.coalesce(func.max(ChatEvent.sequence), 0))
                .where(ChatEvent.run_id == capture.run_id, ChatEvent.type == "message_reset")
                .scalar_subquery()
            )
            if capture.kind == "sequence":
                unchanged = exists(
                    select(ChatRun.id).where(
                        ChatRun.id == capture.run_id,
                        ChatRun.tenant_id == tenant_id,
                        ChatRun.sequence >= capture.value,
                    )
                ) & (current_reset <= capture.value)
            elif capture.kind == "reset":
                unchanged = current_reset == capture.value
            else:
                raise AccessDenied("Conversation changed", code="MEMORY_UNAVAILABLE")
            statements.append(row("capture_check", [literal(capture.run_id), unchanged]))
        rows = (await session.execute(union_all(*statements).limit(32769))).all()
        if release is not None:
            active = [item for item in rows if item[0] == "egress_release"]
            if len(active) != 1 or active[0][3] not in {"true", "True", "1"}:
                raise AccessDenied("This transfer is no longer active", code="MEMORY_UNAVAILABLE")
        if (
            len(rows) > 32768
            or sum(sum(len(value.encode()) for value in item if isinstance(value, str)) for item in rows)
            > 32 * 1024 * 1024
        ):
            raise AccessDenied("Request a smaller conversation page", code="MEMORY_PAGE_TOO_WIDE")
        if egress_pins is not None:
            if any(item[0] == "egress_result" and item[4] is None for item in rows):
                raise AccessDenied("Select fewer evidence-bearing messages", code="MEMORY_PAGE_TOO_WIDE")
            actual = {
                item[1]: digest({"kind": item[3], "payload": json.loads(item[4])})
                for item in rows
                if item[0] == "egress_result"
            }
            manifests = {item[1]: item[2] for item in rows if item[0] == "egress_manifest"}
            if actual != egress_pins or manifests != (egress_manifests or {}):
                raise AccessDenied("Conversation evidence changed before delivery", code="MEMORY_UNAVAILABLE")
        return partition_material(rows, values, current_evidence)
