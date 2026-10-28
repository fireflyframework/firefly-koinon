# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, literal_column, select

from koinon.knowledge.attachments.entities import (
    ChatAttachment,
    ChatAttachmentChunk,
    ChatAttachmentLink,
    ChatAttachmentPromotion,
    timestamp,
)


def owner(model, tenant_id, subject, thread_id):
    return model.tenant_id == tenant_id, model.subject == subject, model.thread_id == thread_id


@repository(name="knowledge.attachments.promotions")
class AttachmentPromotionRepository(Repository[ChatAttachmentPromotion, str]):
    pass


@repository(name="knowledge.attachments.records")
class AttachmentRepository(Repository[ChatAttachment, str]):
    async def selected(self, tenant_id, subject, thread_id, ids, *, lock=False):
        statement = (
            select(ChatAttachment)
            .where(*owner(ChatAttachment, tenant_id, subject, thread_id), ChatAttachment.id.in_(ids))
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update(read=True)
        return list(await self._require_session().scalars(statement))

    async def page(self, tenant_id, subject, thread_id, *, page, page_size, q="", status=None, kind=None):
        conditions = list(owner(ChatAttachment, tenant_id, subject, thread_id))
        now = timestamp()
        if status == "expired":
            conditions.extend((ChatAttachment.expires_at <= now, ChatAttachment.status != "deleted"))
        elif status is not None:
            conditions.append(ChatAttachment.status == status)
            if status != "deleted":
                conditions.append(ChatAttachment.expires_at > now)
        else:
            conditions.append(ChatAttachment.status != "deleted")
        if kind is not None:
            conditions.append(ChatAttachment.kind == kind)
        if q:
            conditions.append(
                ChatAttachment.filename.ilike(
                    "%" + q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
                )
            )
        session = self._require_session()
        total = await session.scalar(select(func.count()).select_from(ChatAttachment).where(*conditions))
        rows = await session.scalars(
            select(ChatAttachment)
            .where(*conditions)
            .order_by(ChatAttachment.created_at.desc(), ChatAttachment.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
            .execution_options(populate_existing=True)
        )
        return list(rows), total or 0

    async def quota(self, tenant_id, subject, thread_id):
        row = (
            await self._require_session().execute(
                select(func.count(), func.coalesce(func.sum(ChatAttachment.size_bytes), 0)).where(
                    *owner(ChatAttachment, tenant_id, subject, thread_id),
                    ChatAttachment.status != "deleted",
                    ChatAttachment.expires_at > timestamp(),
                )
            )
        ).one()
        return row[0], row[1]


@repository(name="knowledge.attachments.chunks")
class AttachmentChunkRepository(Repository[ChatAttachmentChunk, str]):
    async def page(self, tenant_id, subject, thread_id, ids, *, page=1, page_size=25, q=""):
        conditions = [
            *owner(ChatAttachmentChunk, tenant_id, subject, thread_id),
            ChatAttachmentChunk.attachment_id.in_(ids),
        ]
        config = literal_column("'simple'::regconfig")
        document = func.to_tsvector(config, ChatAttachmentChunk.text)
        query = func.websearch_to_tsquery(config, q)
        if q:
            conditions.append(document.op("@@")(query))
        session = self._require_session()
        total = await session.scalar(select(func.count()).select_from(ChatAttachmentChunk).where(*conditions))
        order = (
            (func.ts_rank_cd(document, query).desc(), ChatAttachmentChunk.id)
            if q
            else (ChatAttachmentChunk.attachment_id, ChatAttachmentChunk.ordinal)
        )
        rows = await session.scalars(
            select(ChatAttachmentChunk)
            .where(*conditions)
            .order_by(*order)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        return list(rows), total or 0


@repository(name="knowledge.attachments.links")
class AttachmentLinkRepository(Repository[ChatAttachmentLink, tuple[str, str]]):
    async def for_run(self, tenant_id, subject, thread_id, run_id):
        return list(
            await self._require_session().scalars(
                select(ChatAttachmentLink)
                .where(
                    *owner(ChatAttachmentLink, tenant_id, subject, thread_id),
                    ChatAttachmentLink.run_id == run_id,
                )
                .order_by(ChatAttachmentLink.ordinal)
            )
        )

    async def for_message(self, tenant_id, subject, thread_id, message_id):
        return list(
            await self._require_session().scalars(
                select(ChatAttachmentLink)
                .where(
                    *owner(ChatAttachmentLink, tenant_id, subject, thread_id),
                    ChatAttachmentLink.message_id == message_id,
                )
                .order_by(ChatAttachmentLink.ordinal)
            )
        )
