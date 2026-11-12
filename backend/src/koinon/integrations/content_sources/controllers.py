# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Personal metadata and consent only; no synchronization activation endpoint."""

from dataclasses import asdict

from pyfly.container import rest_controller
from pyfly.kernel import (
    ConflictException,
    ForbiddenException,
    InvalidRequestException,
    ServiceUnavailableException,
)
from pyfly.session.session import HttpSession
from pyfly.web import Body, PathVar, QueryParam, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request

from koinon.integrations.content_sources.api_dtos import (
    SourceAuthorizationCompletion,
    SourceAuthorizationInput,
    SourceAuthorizationOutput,
    SourceCapabilitiesOutput,
    SourceConnectionOutput,
    SourceConnectionPage,
    SourceConnectionRevision,
    SourceFolderPage,
    SourceLocationPage,
)
from koinon.integrations.content_sources.browse import PersonalSourceBrowser
from koinon.integrations.content_sources.dtos import bounded
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import SourceConnectionService
from koinon.integrations.content_sources.parsing import path_id
from koinon.integrations.content_sources.presentation import SourcePresentation
from koinon.security.identity import identity_from_request


def _actor(request: Request) -> str:
    identity = identity_from_request(request)
    attributes = request.state.security_context.attributes
    if "koinon_token" in attributes or "koinon_token_id" in attributes:
        raise ForbiddenException(
            "Use your signed-in account to manage source connections.",
            code="SOURCE_INTERACTIVE_IDENTITY_REQUIRED",
        )
    return identity.subject


def _session(request: Request) -> str:
    session = getattr(request.state, "session", None)
    if not isinstance(session, HttpSession) or session.invalidated or session.stored_id is None:
        raise ForbiddenException(
            "Start source consent from your signed-in browser.", code="SOURCE_BROWSER_SESSION_REQUIRED"
        )
    return session.id


async def _safe(operation):
    try:
        return await operation
    except SourceError as error:
        code = "SOURCE_" + error.code.upper()
        if error.code == "access_denied":
            raise ForbiddenException("This source is not available to your account.", code=code) from None
        if error.code == "authority_changed":
            raise ConflictException(
                "Source permissions changed during this read. Read the source again.", code=code
            ) from None
        if error.code in {"reconnect_required", "invalid_identity", "scope_mismatch"}:
            raise ConflictException("Connect your source account again to continue.", code=code) from None
        if error.code in {"invalid_cursor", "unsupported"}:
            raise InvalidRequestException("This source browsing request is unavailable.", code=code) from None
        raise ServiceUnavailableException(
            "The source could not be checked. Try again later.", code=code
        ) from None


def _browse_parameter(value: str, *, limit: int = 1024, identifier: bool = False) -> str:
    try:
        bounded(value, limit=limit)
        if identifier:
            path_id(value)
    except (ValueError, SourceError):
        raise InvalidRequestException(
            "Invalid source browsing parameter.", code="SOURCE_INVALID_PARAMETER"
        ) from None
    return value


@rest_controller
@request_mapping("/api/v1/tenants/{tenant_id}/content-sources")
class SourceCapabilitiesController:
    def __init__(self, presentation: SourcePresentation):
        self.presentation = presentation

    @get_mapping("/capabilities")
    async def get(self, tenant_id: PathVar[str], request: Request) -> SourceCapabilitiesOutput:
        return await self.presentation.capabilities(_actor(request), tenant_id)


@rest_controller
@request_mapping("/api/v1/tenants/{tenant_id}/content-sources")
class ContentConnectionsController:
    def __init__(self, connections: SourceConnectionService, browser: PersonalSourceBrowser):
        self.connections, self.browser = connections, browser

    @get_mapping("/connections")
    async def list(
        self,
        tenant_id: PathVar[str],
        request: Request,
        cursor: QueryParam[str | None] = None,
        limit: QueryParam[int] = 25,
    ) -> dict:
        actor = _actor(request)
        if not 1 <= limit <= 100 or (cursor is not None and not 1 <= len(cursor) <= 64):
            raise InvalidRequestException("Invalid connection page.", code="SOURCE_INVALID_PAGE")
        result = await _safe(self.connections.list(actor, tenant_id, cursor=cursor, limit=limit))
        return SourceConnectionPage.model_validate(asdict(result)).model_dump(mode="json")

    @post_mapping("/authorizations", status_code=201)
    async def begin(
        self, tenant_id: PathVar[str], body: Valid[Body[SourceAuthorizationInput]], request: Request
    ) -> dict:
        result = await _safe(
            self.connections.begin(_actor(request), tenant_id, _session(request), body.provider)
        )
        return SourceAuthorizationOutput.model_validate(asdict(result)).model_dump(mode="json")

    @post_mapping("/authorizations/complete")
    async def complete(
        self, tenant_id: PathVar[str], body: Valid[Body[SourceAuthorizationCompletion]], request: Request
    ) -> dict:
        result = await _safe(
            self.connections.complete(
                _actor(request),
                tenant_id,
                _session(request),
                body.challenge_id,
                state=body.state.get_secret_value(),
                code=body.code.get_secret_value(),
            )
        )
        return SourceConnectionOutput.model_validate(asdict(result)).model_dump(mode="json")

    @get_mapping("/connections/{connection_id}")
    async def get(self, tenant_id: PathVar[str], connection_id: PathVar[str], request: Request) -> dict:
        result = await _safe(self.connections.get(_actor(request), tenant_id, connection_id))
        return SourceConnectionOutput.model_validate(asdict(result)).model_dump(mode="json")

    @post_mapping("/connections/{connection_id}/disconnect")
    async def disconnect(
        self,
        tenant_id: PathVar[str],
        connection_id: PathVar[str],
        body: Valid[Body[SourceConnectionRevision]],
        request: Request,
    ) -> dict:
        actor = _actor(request)
        await _safe(self.connections.disconnect(actor, tenant_id, connection_id, body.expected_revision))
        result = await _safe(self.connections.get(actor, tenant_id, connection_id))
        return SourceConnectionOutput.model_validate(asdict(result)).model_dump(mode="json")

    @get_mapping("/connections/{connection_id}/sites")
    async def sites(
        self,
        tenant_id: PathVar[str],
        connection_id: PathVar[str],
        request: Request,
        q: QueryParam[str],
        cursor: QueryParam[str | None] = None,
    ) -> dict:
        actor = _actor(request)
        query = _browse_parameter(q, limit=256)
        result = await _safe(self.browser.sites(actor, tenant_id, connection_id, query, cursor=cursor))
        return SourceLocationPage.model_validate(asdict(result)).model_dump(mode="json")

    @get_mapping("/connections/{connection_id}/drives")
    async def drives(
        self,
        tenant_id: PathVar[str],
        connection_id: PathVar[str],
        request: Request,
        site_id: QueryParam[str | None] = None,
        cursor: QueryParam[str | None] = None,
    ) -> dict:
        actor = _actor(request)
        if site_id is not None:
            _browse_parameter(site_id, identifier=True)
        result = await _safe(
            self.browser.drives(actor, tenant_id, connection_id, site_id=site_id, cursor=cursor)
        )
        return SourceLocationPage.model_validate(asdict(result)).model_dump(mode="json")

    @get_mapping("/connections/{connection_id}/children")
    async def children(
        self,
        tenant_id: PathVar[str],
        connection_id: PathVar[str],
        request: Request,
        drive_id: QueryParam[str],
        folder_id: QueryParam[str | None] = None,
        cursor: QueryParam[str | None] = None,
    ) -> dict:
        actor = _actor(request)
        _browse_parameter(drive_id, identifier=True)
        if folder_id is not None:
            _browse_parameter(folder_id, identifier=True)
        result = await _safe(
            self.browser.children(
                actor, tenant_id, connection_id, drive_id, folder_id=folder_id, cursor=cursor
            )
        )
        return SourceFolderPage.model_validate(asdict(result)).model_dump(mode="json")
