# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private extracted text stays ephemeral; only its immutable unit binding is recorded."""

import json
from hashlib import sha256

from koinon.knowledge.answer_evidence import AnswerFact


def verified_private_facts(facts, rows, refs) -> tuple[AnswerFact, ...]:
    index = {row.id: row for row in rows if row.kind == "attachment"}
    current = {(ref.id, ref.sha256, ref.revision) for ref in refs}
    accepted = []
    for fact in facts:
        row = index.get(fact.result_id)
        matched = False
        for attachment in row.payload.get("data", {}).get("attachments", []) if row else ():
            if (attachment["id"], attachment["sha256"], attachment["revision"]) not in current:
                continue
            for unit in attachment.get("text_units", []):
                binding = json.dumps(
                    [
                        attachment["id"],
                        attachment["sha256"],
                        attachment["revision"],
                        unit["unit_id"],
                        unit["text_sha256"],
                        unit["page"],
                    ],
                    separators=(",", ":"),
                )
                lineage = sha256(binding.encode()).hexdigest()
                if (
                    fact.kind == "quote"
                    and fact.text
                    and not fact.source_refs
                    and fact.label == attachment["filename"]
                    and fact.id == unit["id"] == sha256(("private:" + lineage).encode()).hexdigest()
                    and fact.lineage_sha256 == unit["lineage_sha256"] == lineage
                    and sha256(fact.text.encode()).hexdigest() == unit["text_sha256"]
                ):
                    matched = True
        if not matched:
            raise ValueError("Private factual input has no current immutable extracted-unit binding")
        accepted.append(fact)
    return tuple(accepted)
