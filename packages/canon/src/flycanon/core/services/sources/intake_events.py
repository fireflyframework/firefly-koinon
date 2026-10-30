# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Source lifecycle publication with explicitly supplied managed dependencies."""

import logging

from pyfly.eda import EventPublisher

from flycanon.config import CanonSettings
from flycanon.models.entities.source import SourceRow

logger = logging.getLogger(__name__)


async def publish_success(
    publisher: EventPublisher | None,
    settings: CanonSettings,
    *,
    source: SourceRow,
    correlation_id: str | None,
) -> None:
    if publisher is None:
        return
    try:
        await publisher.publish(  # type: ignore[attr-defined]
            destination=settings.ingest_topic,
            event_type=settings.source_ingested_event,
            payload={
                "source_id": source.id,
                "tenant_id": source.tenant_id,
                "workspace_id": source.workspace_id,
                "kind": source.kind,
                "content_sha256": source.content_sha256,
                "n_chunks": source.n_chunks,
            },
            headers={"correlation-id": correlation_id} if correlation_id else None,
        )
    except Exception as exc:
        logger.warning("source.ingested publish failed source_id=%s: %s", source.id, exc)


async def publish_failure(
    publisher: EventPublisher | None,
    settings: CanonSettings,
    *,
    source: SourceRow,
    exc: BaseException,
    correlation_id: str | None,
) -> None:
    if publisher is None:
        return
    try:
        await publisher.publish(  # type: ignore[attr-defined]
            destination=settings.ingest_topic,
            event_type=settings.source_ingestion_failed_event,
            payload={
                "source_id": source.id,
                "tenant_id": source.tenant_id,
                "workspace_id": source.workspace_id,
                "kind": source.kind,
                "code": getattr(exc, "code", "ingestion_failed"),
                "message": str(exc),
            },
            headers={"correlation-id": correlation_id} if correlation_id else None,
        )
    except Exception as inner:
        logger.warning("source.failed publish failed source_id=%s: %s", source.id, inner)
