# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import html
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from koinon.evidence.dtos import ConversationSnapshot


@dataclass(frozen=True)
class RenderedExport:
    content: bytes
    content_type: str
    filename: str
    headers: tuple[tuple[str, str], ...] = ()


def safe_filename(title: str, extension: str) -> str:
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", plain).strip("-").lower()[:80] or "conversation"
    return slug + "." + extension


def _markdown(text: str) -> str:
    text = html.escape(text, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+|>\-])", r"\\\1", text)


def render_transcript(
    snapshot: ConversationSnapshot,
    format: str,
    *,
    include_evidence: bool,
    exported_at: datetime | None = None,
) -> RenderedExport:
    if format not in {"json", "markdown"}:
        raise ValueError("Choose Markdown or JSON for a conversation export")
    omissions = []
    if not include_evidence:
        omissions.append("Source evidence was excluded from this export.")
    elif not snapshot.source_manifest_complete:
        omissions.append("The source manifest is incomplete; this is not a complete evidence archive.")
    if any(message.private_derived for message in snapshot.messages):
        omissions.append("Private attachment files and their metadata are excluded.")
    messages = [
        {
            "id": message.id,
            "role": message.role,
            "text": message.text,
            "status": message.status,
            "revision": message.revision,
            "source_ids": list(message.source_ids) if include_evidence else [],
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "presentation": message.presentation.model_dump() if message.presentation else None,
        }
        for message in snapshot.messages
    ]
    sources = [source.model_dump(mode="json") for source in snapshot.sources] if include_evidence else []
    data = {
        "schema_version": 1,
        "kind": "conversation",
        "title": snapshot.title,
        "revision": snapshot.revision,
        "completeness": "selected_messages",
        "exported_at": (exported_at or datetime.now(UTC)).isoformat(),
        "messages": messages,
        "sources": sources,
        "source_manifest_complete": snapshot.source_manifest_complete if include_evidence else False,
        "omissions": omissions,
    }
    if format == "json":
        return RenderedExport(
            json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2).encode(),
            "application/json",
            safe_filename(snapshot.title, "json"),
        )
    lines = [
        "# " + _markdown(" ".join(snapshot.title.splitlines())),
        "",
        "Selected messages",
        "",
        "Revision: " + snapshot.revision,
        "",
    ]
    for message in snapshot.messages:
        label = "You" if message.role == "user" else "koinon"
        lines.extend(["## " + label, "", _markdown(message.text), ""])
        if message.status != "completed":
            lines.extend(["Answer status: " + message.status, ""])
    if sources:
        lines.extend(["## Sources", ""])
        for index, source in enumerate(snapshot.sources, 1):
            location = f", page {source.page}" if source.page is not None else ""
            if source.section:
                location += ", " + source.section
            lines.extend(
                [f"{index}. " + _markdown(source.title + location), "   Reference: " + _markdown(source.id)]
            )
            if source.used_revision:
                lines.append("   Used revision: " + _markdown(source.used_revision))
            if source.quote:
                lines.append("   Quote: " + _markdown(source.quote))
            lines.append("")
    if omissions:
        lines.extend(["## Export notes", "", *(_markdown(note) for note in omissions), ""])
    return RenderedExport(
        "\n".join(lines).encode(), "text/markdown; charset=utf-8", safe_filename(snapshot.title, "md")
    )
