# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Answer cards expose selected source facts, never stored model analysis or SQL constants."""

from koinon.answers.facts import recorded_facts
from koinon.answers.receipts import AnswerRelease
from koinon.assistants.entities import ToolResult


def released_result_data(row: ToolResult, release: AnswerRelease | None) -> dict:
    if release is None:
        data = row.payload.get("data", {})
        if row.kind == "schema":
            return {"tables": data.get("tables", [])}
        if row.kind == "query":
            return {
                **{
                    key: data[key]
                    for key in ("sql", "query_id", "execution_status", "preview", "row_count", "truncated")
                    if key in data
                },
                "answer_eligible": False,
            }
    facts = tuple(
        fact
        for fact in recorded_facts(row.payload.get("answer_facts"))
        if release is None or fact.id in release.fact_ids
    )
    if row.kind == "search":
        return {
            "hits": [
                {
                    "asset_id": source.asset_id,
                    "id": source.chunk_id or source.id,
                    "source_id": source.source_id,
                    "title": source.title,
                    "text": fact.text,
                }
                for fact in facts
                if fact.kind == "quote"
                for source in fact.source_refs
            ]
        }
    if row.kind == "query":
        preview = [
            {"field": fact.label, "value": fact.value} for fact in facts if fact.kind in {"cell", "derived"}
        ]
        return {"preview": preview, "row_count": len(preview), "execution_status": "OK", "truncated": False}
    if row.kind == "attachment":
        return {
            "attachments": [
                {key: value for key, value in attachment.items() if key != "text_units"}
                for attachment in row.payload.get("data", {}).get("attachments", [])
            ]
        }
    return {}
