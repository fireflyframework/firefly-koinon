# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reauthenticate component operations without retaining the canonical request context."""

import asyncio
import contextvars
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from pyfly.context import ApplicationContext
from pyfly.kernel.exceptions import PyFlyException
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.curated.authority import CuratedAuthority
from koinon.knowledge.external_reviews.file_dtos import CHUNK_BYTES, MAX_FILE_BYTES
from koinon.knowledge.external_reviews.file_service import ExternalFileReviews
from koinon.knowledge.external_reviews.service import ExternalKnowledgeReviews
from koinon.mcp_auth.service import McpOAuthService
from koinon.organization_branding.service import OrganizationBrandingService


class ReviewScopeRequired(ToolError):
    """A scope-only denial observed by the actual canonical permission service."""


async def authenticated_operation(
    context: ApplicationContext, raw: str, work: Callable[[str], Awaitable[dict[str, Any]]]
):
    async def isolated():
        authenticated = await context.get_bean(McpOAuthService).authenticate(raw)
        attributes = authenticated.attributes
        issuer, subject = attributes.get("iss"), attributes.get("sub")
        if not isinstance(issuer, str) or not issuer or not isinstance(subject, str) or not subject:
            raise ToolError("Authentication required (401)")
        with SecurityContextHolder.using(authenticated):
            return await work(issuer + "|" + subject)

    try:
        return await asyncio.create_task(isolated(), context=contextvars.Context())
    except AccessDenied as error:
        if error.code == "TOKEN_INSUFFICIENT_SCOPE":
            raise ReviewScopeRequired("Additional knowledge authorization is required") from None
        raise ToolError("Knowledge operation is unavailable or no longer authorized (403)") from None
    except PyFlyException:
        raise ToolError("Private in-chat review is unavailable or no longer authorized") from None


async def presentation(context: ApplicationContext, principal: str, tenant_id: str):
    branding = await context.get_bean(OrganizationBrandingService).get(principal, tenant_id)
    values = branding.branding
    result = {
        "product_name": values.product_name,
        "assistant_name": values.assistant_name,
        "palette": values.palette.model_dump(mode="json"),
    }
    if values.symbol is not None and len(values.symbol) <= 65536:
        result["symbol"] = values.symbol
    return result


def private_review_reader(context: ApplicationContext, *, file=False):
    async def read(raw: str, tenant_id: str, review_id: str):
        async def work(principal):
            if file:
                challenge = await context.get_bean(ExternalFileReviews).challenge(
                    principal, tenant_id, review_id
                )
            else:
                challenge = await context.get_bean(ExternalKnowledgeReviews).challenge(
                    principal, tenant_id, review_id
                )
            return {
                **challenge.model_dump(mode="json"),
                "presentation": await presentation(context, principal, tenant_id),
            }

        return await authenticated_operation(context, raw, work)

    return read


def file_upload_preparer(context: ApplicationContext):
    async def prepare(raw: str, tenant_id: str, destination_id: str, mode: str):
        async def work(principal):
            destination = await context.get_bean(CuratedAuthority).destination(
                principal, tenant_id, destination_id
            )
            files = context.get_bean(ExternalFileReviews)
            _, storage_limit = files.storage.configured()
            maximum = min(
                MAX_FILE_BYTES,
                files.settings.max_file_bytes,
                files.facade().settings.max_upload_bytes,
                storage_limit,
            )
            return {
                "setup": {
                    "tenant_id": tenant_id,
                    "destination_id": destination.id,
                    "destination_name": destination.name,
                    "mode": mode,
                    "max_file_bytes": maximum,
                    "chunk_bytes": CHUNK_BYTES,
                },
                "presentation": await presentation(context, principal, tenant_id),
            }

        return await authenticated_operation(context, raw, work)

    return prepare
