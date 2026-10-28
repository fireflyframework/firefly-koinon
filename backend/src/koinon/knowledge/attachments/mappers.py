# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from koinon.knowledge.attachments.dtos import AttachmentHistorySummary, AttachmentProgress, AttachmentView
from koinon.knowledge.attachments.entities import timestamp
from koinon.knowledge.attachments.ports import AttachmentRef


def status(row):
    return "expired" if row.status != "deleted" and row.expires_at <= timestamp() else row.status


def reference(row):
    return AttachmentRef(**{key: getattr(row, key) for key in AttachmentRef.__dataclass_fields__})


def snapshot(ref):
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in ((key, getattr(ref, key)) for key in AttachmentRef.__dataclass_fields__)
    }


def from_snapshot(value):
    fields = dict(value)
    fields["expires_at"] = datetime.fromisoformat(fields["expires_at"])
    return AttachmentRef(**fields)


def attachment_dto(row, job=None):
    current = status(row)
    progress = (
        row.status
        if row.status == "storing"
        else job.status
        if job
        else (
            "succeeded"
            if row.status == "ready"
            else "cancelled"
            if row.status in {"cancelled", "deleted"}
            else "queued"
        )
    )
    return AttachmentView.model_validate(
        {
            **{
                name: getattr(row, name)
                for name in (
                    "id",
                    "tenant_id",
                    "thread_id",
                    "filename",
                    "media_type",
                    "kind",
                    "size_bytes",
                    "sha256",
                    "revision",
                    "created_at",
                    "expires_at",
                    "page_count",
                    "chunk_count",
                    "error_code",
                    "error",
                    "warnings",
                )
            },
            "status": current,
            "progress": AttachmentProgress(
                status=progress,
                percent=job.progress if job else (100 if row.status == "ready" else 0),
                attempts=job.attempts if job else 0,
            ),
        }
    )


def history_summary(row):
    current = status(row)
    return AttachmentHistorySummary.model_validate(
        {
            **{
                name: getattr(row, name)
                for name in ("id", "media_type", "kind", "size_bytes", "sha256", "revision", "expires_at")
            },
            "filename": "Removed attachment" if current == "deleted" else row.filename,
            "status": current,
            "available": current == "ready",
        }
    )
