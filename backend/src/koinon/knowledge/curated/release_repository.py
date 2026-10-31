# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One bounded primary snapshot over all selected authorization dependencies."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository, transactional
from pyfly.data.transaction import Propagation
from sqlalchemy import Text, cast, func, literal, or_, select, union_all
from sqlalchemy.orm import aliased
from sqlalchemy.sql.selectable import FromClause

from koinon.authorized_applications.entities import AuthorizedApplication
from koinon.catalog.entities import CatalogEntry
from koinon.knowledge.curated.entities import CuratedCatalogState, CuratedSourceRoot
from koinon.knowledge.curated.release_dtos import CuratedReleaseStamp
from koinon.knowledge.curated.release_mappers import MAX_ROWS, release_stamp
from koinon.knowledge.entities import DomainBinding
from koinon.mcp_applications.entities import McpOAuthClientRegistration
from koinon.tokens.entities import PersonalToken

_WIDTH = 20


def _row(tag: str, columns: Sequence[Any]):
    if len(columns) > _WIDTH:
        raise ValueError("Authority projection exceeds its declared width")
    return select(
        literal(tag),
        *(cast(value, Text) for value in columns),
        *(literal(None, Text) for _ in range(_WIDTH - len(columns))),
    )


@repository(name="knowledge.curated.release_material")
class CuratedReleaseRepository(Repository[CuratedCatalogState, str]):
    @transactional(datasource="primary", propagation=Propagation.REQUIRES_NEW, read_only=True)
    async def observe(
        self,
        subject: str,
        tenant_id: str,
        item_ids: tuple[str, ...],
        members: FromClause,
        token_id: str | None,
    ) -> CuratedReleaseStamp:
        session = self._require_session()
        entry, state, root = CatalogEntry, CuratedCatalogState, CuratedSourceRoot
        roots = (
            select(root)
            .join(state, state.item_id == root.item_id)
            .where(
                root.tenant_id == tenant_id,
                root.item_id.in_(item_ids),
                root.native_version_id == state.serving_version_id,
                state.tenant_id == tenant_id,
            )
            .cte("release_roots")
        )
        seed = union_all(
            select(entry.id).where(entry.id.in_(item_ids), entry.tenant_id == tenant_id),
            select(roots.c.source_asset_id),
        )
        ancestry = (
            select(entry.id, entry.parent_id, literal(0).label("depth"))
            .where(entry.id.in_(seed), entry.tenant_id == tenant_id)
            .cte("release_ancestry", recursive=True)
        )
        parent = aliased(entry)
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
        statements = [
            _row(
                "entry",
                [
                    entry.id,
                    entry.tenant_id,
                    entry.workspace_id,
                    entry.project_id,
                    entry.parent_id,
                    entry.kind,
                    entry.status,
                    entry.updated_at,
                ],
            ).where(entry.id.in_(ids), entry.tenant_id == tenant_id),
            _row("state", list(state.__table__.columns)).where(
                state.item_id.in_(item_ids), state.tenant_id == tenant_id
            ),
            _row("root", list(roots.c)),
            _row(
                "binding",
                [
                    DomainBinding.id,
                    DomainBinding.tenant_id,
                    DomainBinding.catalog_id,
                    DomainBinding.workspace_id,
                    DomainBinding.domain,
                    DomainBinding.entity_kind,
                    DomainBinding.native_id,
                    DomainBinding.native_workspace_id,
                ],
            ).where(DomainBinding.catalog_id.in_(ids), DomainBinding.tenant_id == tenant_id),
            _row("membership", list(members.c)).where(
                members.c.subject == subject, members.c.tenant_id == tenant_id
            ),
        ]
        if "expires_at" in members.c:
            statements[-1] = statements[-1].where(
                or_(members.c.expires_at.is_(None), members.c.expires_at > clock)
            )
        if token_id is not None:
            token = PersonalToken
            active_token = (
                select(token)
                .where(
                    token.id == token_id,
                    token.subject == subject,
                    token.tenant_id == tenant_id,
                    token.revoked_at.is_(None),
                    token.expires_at > clock,
                )
                .cte("release_token")
            )
            app = AuthorizedApplication
            active_app = (
                select(app)
                .join(active_token, active_token.c.authorized_application_id == app.id)
                .where(
                    app.tenant_id == tenant_id,
                    app.subject == subject,
                    app.revoked_at.is_(None),
                    app.expires_at > clock,
                )
                .cte("release_app")
            )
            registration = McpOAuthClientRegistration
            statements.extend(
                [
                    _row(
                        "token",
                        [
                            active_token.c.id,
                            active_token.c.subject,
                            active_token.c.tenant_id,
                            active_token.c.purpose,
                            active_token.c.authorized_application_id,
                            active_token.c.scopes,
                            active_token.c.workspace_ids,
                            active_token.c.asset_ids,
                            active_token.c.resource_ids,
                            active_token.c.expires_at,
                        ],
                    ),
                    _row(
                        "application",
                        [
                            active_app.c.id,
                            active_app.c.subject,
                            active_app.c.client_id,
                            active_app.c.tenant_id,
                            active_app.c.workspace_id,
                            active_app.c.scopes,
                            active_app.c.resource,
                            active_app.c.client_registration,
                            active_app.c.expires_at,
                        ],
                    ),
                    _row(
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
                    ).where(
                        # Client IDs are global in current OAuth authority,
                        # including static-client collisions.
                        registration.client_id.in_(select(active_app.c.client_id)),
                    ),
                ]
            )
        rows = (await session.execute(union_all(*statements).limit(MAX_ROWS + 1))).all()
        return release_stamp(subject, tenant_id, token_id, rows)
