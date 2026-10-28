# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A borrowed primary unit restores private authority when joining run admission."""

from contextlib import asynccontextmanager

from pyfly.container import component
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import text

TABLES = (
    "koinon_chat_attachments",
    "koinon_chat_attachment_chunks",
    "koinon_chat_attachment_links",
    "koinon_chat_attachment_promotions",
)


@component(name="knowledge.attachments.data")
class AttachmentData:
    def __init__(self, registry: DataSourceRegistry):
        self.registry = registry

    @asynccontextmanager
    async def scope(self, subject: str, tenant_id: str, thread_id: str, *, purpose="read"):
        if (
            not subject
            or not tenant_id
            or not thread_id
            or purpose not in {"read", "extract", "purge", "pin"}
        ):
            raise ValueError("An explicit trusted private file scope is required")
        source = self.registry.primary
        if source.url.get_backend_name() != "postgresql":
            raise ServiceUnavailableException(
                "Private attachments require the migrated PostgreSQL data source",
                code="ATTACHMENT_DATABASE_REQUIRED",
            )
        async with infrastructure_unit(source) as session:
            ready = await session.scalar(
                text("""
                SELECT count(*)=4 AND bool_and(c.relrowsecurity AND c.relforcerowsecurity)
                  AND NOT (SELECT rolbypassrls OR rolsuper FROM pg_catalog.pg_roles
                           WHERE rolname=current_user)
                FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relname=ANY(CAST(:tables AS text[]))
            """),
                {"tables": list(TABLES)},
            )
            if not ready:
                raise ServiceUnavailableException(
                    "Apply the private attachment migration with an isolated non-bypass runtime role",
                    code="ATTACHMENT_SCHEMA_REQUIRED",
                )
            previous = (
                (
                    await session.execute(
                        text("""
                SELECT current_setting('app.attachment_subject',true) AS subject,
                       current_setting('app.attachment_tenant',true) AS tenant,
                       current_setting('app.attachment_thread',true) AS thread,
                       current_setting('app.attachment_purpose',true) AS purpose
            """)
                    )
                )
                .mappings()
                .one()
            )
            statement = text("""
                SELECT set_config('app.attachment_subject',:subject,true),
                       set_config('app.attachment_tenant',:tenant,true),
                       set_config('app.attachment_thread',:thread,true),
                       set_config('app.attachment_purpose',:purpose,true)
            """)
            await session.execute(
                statement, {"subject": subject, "tenant": tenant_id, "thread": thread_id, "purpose": purpose}
            )
            yield session
            await session.execute(statement, {key: previous[key] or "" for key in previous})
