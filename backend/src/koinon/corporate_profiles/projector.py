# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fresh bounded tenant presentation, without changing global profiles."""

from typing import Any, NoReturn

from pyfly.container import service
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import ROLE_PERMISSIONS, CatalogService
from koinon.corporate_profiles.mappers import effective
from koinon.corporate_profiles.projection_repository import CorporatePresentationRepository
from koinon.corporate_profiles.read_models import PresentationRead, RevisionFact
from koinon.security.authority import primary_authority
from koinon.tokens.entities import PersonalToken


def denied() -> NoReturn:
    raise AccessDenied("Presentation is unavailable in this organization scope", code="ACCESS_DENIED")


@service(name="corporate_profiles.projector")
class CorporateProfileProjector:
    def __init__(self, catalog: CatalogService, repository: CorporatePresentationRepository):
        self.catalog, self.repository = catalog, repository

    @primary_authority(fresh=True)
    async def batch(
        self,
        actor,
        tenant_id,
        wanted,
        workspace_id=None,
        *,
        own=False,
        authors=False,
        author_permission="catalog:read",
        write=False,
        count_query=None,
        expected_total=None,
        people=(),
        units=(),
        unassigned=(),
        page_query=None,
        page_subjects=(),
    ):
        if len(wanted) > (200 if authors else 100) or own and actor not in wanted:
            denied()
        await self.catalog._validate_workspace(tenant_id, workspace_id)
        context = SecurityContextHolder.get_context()
        attributes: dict[str, Any] = context.attributes if context else {}
        token_data = attributes.get("koinon_token") if "koinon_token" in attributes else None
        token_id = ""
        if token_data is not None:
            if not isinstance(token_data, dict) or not token_data.get("id"):
                denied()
            token_id = token_data["id"]
        request = PresentationRead(
            actor,
            tenant_id,
            frozenset(wanted),
            workspace_id,
            own,
            authors,
            token_id,
            count_query,
            expected_total,
            tuple(RevisionFact(row.id, row.revision) for row in people if row is not None),
            tuple(RevisionFact(row.id, row.revision) for row in units),
            tuple(unassigned),
            page_query,
            tuple(page_subjects),
            tuple(role for role, permissions in ROLE_PERMISSIONS.items() if author_permission in permissions),
        )
        rows = await self.repository.read(request, self.catalog.effective_membership_rows())
        if not rows or (
            not authors
            and wanted
            and (
                own
                and actor not in {row.subject for row in rows}
                or not own
                and {row.subject for row in rows} != set(wanted)
            )
        ):
            denied()
        result = {}
        for row in rows:
            self._token(
                row.token,
                token_data,
                tenant_id,
                workspace_id,
                own=own,
                authors=authors,
                write=write,
                author_permission=author_permission,
            )
            if row.subject is not None:
                result[row.subject] = effective(
                    row.subject,
                    row.profile,
                    row.snapshot,
                    row.preference,
                    row.provider,
                    row.mapping,
                    conflict_enabled=row.active_policy,
                    conflict_name_required=row.name_required,
                    conflict_avatar_required=row.avatar_required,
                    conflict_overrides_allowed=row.overrides_allowed,
                    current_member=row.current_member,
                )
        return result

    @staticmethod
    def _token(
        row: PersonalToken | None,
        expected,
        tenant_id,
        workspace_id,
        *,
        own,
        authors,
        write=False,
        author_permission="catalog:read",
    ):
        if expected is None:
            return
        if row is None:
            denied()
        scopes = set(row.scopes) if isinstance(row.scopes, list) else set()
        allowed = (
            ({"profile:write"} if write else {"profile:read", "profile:write"})
            if own
            else {"members:write", "catalog:read"}
        )
        if authors:
            if (
                author_permission not in scopes
                or row.tenant_id != tenant_id
                or row.workspace_ids != expected.get("workspace_ids")
                or row.asset_ids != expected.get("asset_ids")
            ):
                denied()
            return
        if (
            not scopes.intersection(allowed)
            or row.tenant_id != tenant_id
            or row.asset_ids is not None
            or row.workspace_ids is not None
            and workspace_id not in row.workspace_ids
        ):
            if authors:
                denied()
            denied()
