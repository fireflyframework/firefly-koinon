# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Migration-owned private tables; catalog boot never auto-creates unconfigured file storage."""

from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import UtcDateTime
from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, MetaData, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from koinon.assistants.entities import ChatMessage, ChatRun, ChatThread
from koinon.catalog.entities import CatalogEntry, Tenant


def timestamp():
    return datetime.now(UTC)


class AttachmentBase(DeclarativeBase):
    metadata = MetaData(schema="public")


class ChatAttachment(AttachmentBase):
    __tablename__ = "koinon_chat_attachments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "subject", "thread_id", "request_key", name="uq_chat_attachment_request"
        ),
        CheckConstraint("size_bytes > 0", name="ck_chat_attachment_size"),
        CheckConstraint("revision > 0", name="ck_chat_attachment_revision"),
        CheckConstraint("kind in ('document','image','bundle')", name="ck_chat_attachment_kind"),
        Index("ix_chat_attachment_owner", "tenant_id", "subject", "thread_id", "created_at", "id"),
        Index("ix_chat_attachment_expiry", "expires_at", "status"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.__table__.c.id))
    subject: Mapped[str] = mapped_column(String(512))
    thread_id: Mapped[str] = mapped_column(ForeignKey(ChatThread.__table__.c.id, ondelete="CASCADE"))
    request_key: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(255))
    declared_media_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    media_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    kind: Mapped[str] = mapped_column(String(16), default="document")
    size_bytes: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="storing")
    revision: Mapped[int] = mapped_column(default=1)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expiry_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    access_token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    chunk_count: Mapped[int] = mapped_column(default=0)
    text_char_count: Mapped[int] = mapped_column(default=0)
    normalized_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalized_media_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    normalized_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    image_width: Mapped[int | None] = mapped_column(nullable=True)
    image_height: Mapped[int | None] = mapped_column(nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=timestamp)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=timestamp)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())


class ChatAttachmentChunk(AttachmentBase):
    __tablename__ = "koinon_chat_attachment_chunks"
    __table_args__ = (
        UniqueConstraint("attachment_id", "ordinal", name="uq_chat_attachment_chunk_order"),
        CheckConstraint("char_start >= 0 AND char_end >= char_start", name="ck_chat_attachment_offsets"),
        Index("ix_chat_attachment_chunk_owner", "tenant_id", "subject", "thread_id", "attachment_id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attachment_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_attachments.id", ondelete="CASCADE"))
    tenant_id: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(512))
    thread_id: Mapped[str] = mapped_column(String(64))
    ordinal: Mapped[int] = mapped_column()
    text: Mapped[str] = mapped_column()
    page: Mapped[int | None] = mapped_column(nullable=True)
    section_path: Mapped[list] = mapped_column(JSON, default=list)
    char_start: Mapped[int] = mapped_column()
    char_end: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(String(64))


class ChatAttachmentLink(AttachmentBase):
    __tablename__ = "koinon_chat_attachment_links"
    __table_args__ = (
        UniqueConstraint("run_id", "ordinal", name="uq_chat_attachment_link_order"),
        Index("ix_chat_attachment_link_message", "tenant_id", "subject", "thread_id", "message_id"),
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey(ChatRun.__table__.c.id, ondelete="CASCADE"), primary_key=True
    )
    attachment_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_attachments.id"), primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey(ChatMessage.__table__.c.id, ondelete="CASCADE"))
    tenant_id: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(512))
    thread_id: Mapped[str] = mapped_column(String(64))
    ordinal: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column()
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=timestamp)


class ChatAttachmentPromotion(AttachmentBase):
    __tablename__ = "koinon_chat_attachment_promotions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "subject", "thread_id", "request_key", name="uq_chat_attachment_promotion"
        ),
        CheckConstraint(
            "action in ('add','replace_document','replace_table')", name="ck_chat_attachment_action"
        ),
        Index("ix_chat_attachment_promotion_owner", "tenant_id", "subject", "thread_id", "attachment_id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attachment_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_attachments.id"))
    tenant_id: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(512))
    thread_id: Mapped[str] = mapped_column(String(64))
    request_key: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="planned")
    revision: Mapped[int] = mapped_column(default=1)
    values_json: Mapped[dict] = mapped_column(JSON)
    source_catalog_id: Mapped[str | None] = mapped_column(
        ForeignKey(CatalogEntry.__table__.c.id), nullable=True
    )
    content_version_id: Mapped[str | None] = mapped_column(
        ForeignKey(CatalogEntry.__table__.c.id), nullable=True
    )
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=timestamp)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=timestamp)
