# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Deployment observations contain no private file identity, path or inferred worker readiness."""

from datetime import datetime, timedelta
from importlib.util import find_spec

from pyfly.container import component, service
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import text

from koinon.knowledge.attachments.authority import AttachmentAuthority
from koinon.knowledge.attachments.data import TABLES, AttachmentData
from koinon.knowledge.attachments.dtos import AttachmentCapabilities
from koinon.knowledge.attachments.entities import timestamp
from koinon.knowledge.attachments.settings import AttachmentSettings
from koinon.knowledge.attachments.storage import AttachmentStorage

FORMATS = (
    ("document", "text/plain", (".txt",), ()),
    ("document", "text/markdown", (".md", ".markdown"), ()),
    ("document", "text/csv", (".csv",), ()),
    ("document", "text/tab-separated-values", (".tsv",), ()),
    ("document", "application/json", (".json",), ()),
    ("document", "text/html", (".html", ".htm"), ("bs4",)),
    ("document", "application/xml", (".xml",), ("lxml",)),
    ("document", "application/pdf", (".pdf",), ("pymupdf", "pypdf")),
    (
        "document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        (".docx",),
        ("docx",),
    ),
    (
        "document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        (".xlsx",),
        ("openpyxl",),
    ),
    (
        "document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        (".pptx",),
        ("pptx",),
    ),
    ("image", "image/png", (".png",), ("PIL",)),
    ("image", "image/jpeg", (".jpg", ".jpeg"), ("PIL",)),
    ("image", "image/webp", (".webp",), ("PIL",)),
    ("image", "image/gif", (".gif",), ("PIL",)),
    ("bundle", "application/zip", (".zip",), ()),
)


@component(name="knowledge.attachments.processing_state")
class AttachmentProcessingState:
    def __init__(self):
        self.last_tick: datetime | None = None


@service(name="knowledge.attachments.capabilities")
class AttachmentCapabilityService:
    def __init__(
        self,
        authority: AttachmentAuthority,
        data: AttachmentData,
        storage: AttachmentStorage,
        settings: AttachmentSettings,
        processing: AttachmentProcessingState,
    ):
        self.authority, self.data, self.storage = authority, data, storage
        self.settings, self.processing = settings, processing

    async def for_thread(self, subject, tenant_id, thread_id):
        await self.authority.thread(subject, tenant_id, thread_id)
        return await self.deployment()

    async def deployment(self):
        settings = self.settings
        settings.validate()
        try:
            self.storage.configured()
            local = self.storage.profile.backend == "local"
            dependencies = {
                "s3": ("boto3",),
                "azure": ("azure.storage.blob", "azure.identity"),
                "gcs": ("google.cloud.storage",),
            }
            try:
                configured = local or all(
                    find_spec(name) is not None for name in dependencies[self.storage.profile.backend]
                )
            except ModuleNotFoundError:
                configured = False
            storage = {
                "configured": configured,
                "available": True if local else None if configured else False,
                "reason": "Private storage is configured and its directory permissions were checked"
                if local
                else "Private cloud storage is configured; provider access has not been verified"
                if configured
                else "Install the declared private cloud storage SDK dependency",
            }
        except (ServiceUnavailableException, OSError):
            storage = {
                "configured": False,
                "available": False,
                "reason": "Configure private storage and verify its declared backend requirements",
            }
        source = self.data.registry.primary
        database = {
            "available": False,
            "reason": "Private files require the applied PostgreSQL attachment migration",
        }
        if source.url.get_backend_name() == "postgresql":
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
            database = {
                "available": bool(ready),
                "reason": "Owner/thread RLS tables and the non-bypass role were checked"
                if ready
                else database["reason"],
            }
        installed = find_spec("koinon.knowledge.attachments.extraction") is not None
        live = self.processing.last_tick is not None and self.processing.last_tick > timestamp() - timedelta(
            seconds=15
        )
        extraction = {
            "available": True if installed and live else None if installed else False,
            "reason": "A native private-file worker heartbeat was observed in this process"
            if live and installed
            else "External worker availability has not been observed by this API process"
            if installed
            else "The resource-bounded private extraction module is not installed",
        }
        formats = []
        for kind, mime, extensions, dependencies in FORMATS:
            available = installed and all(find_spec(dependency) is not None for dependency in dependencies)
            formats.append(
                {
                    "kind": kind,
                    "media_type": mime,
                    "extensions": list(extensions),
                    "extraction": {
                        "available": available,
                        "reason": "Image verification is supported; model vision is checked separately"
                        if available and kind == "image"
                        else "Text extraction prerequisites are installed; visual/OCR features are separate"
                        if available
                        else "Install the declared private extractor and format dependencies",
                    },
                }
            )
        return AttachmentCapabilities.model_validate(
            {
                "storage": storage,
                "database": database,
                "extraction": extraction,
                "formats": formats,
                "promotion": {},
                "limits": {
                    **{
                        name: getattr(settings, name)
                        for name in (
                            "max_file_bytes",
                            "max_image_bytes",
                            "max_selected",
                            "max_thread_files",
                            "max_thread_bytes",
                            "extraction_timeout_seconds",
                            "ttl_seconds",
                        )
                    },
                    "max_model_text_chars": 24000,
                    "max_model_binary_bytes": 16 * 1024 * 1024,
                },
            }
        )
