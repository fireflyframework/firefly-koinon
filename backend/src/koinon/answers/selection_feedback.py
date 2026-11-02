# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Finite repair instructions without source content or rejected model prose."""


def selection_feedback(code: str) -> str:
    problem = {
        "QUOTE_NOT_RECORDED": "QUOTE_NOT_RECORDED: a quote selected the wrong fact kind, ID or passage. ",
        "VALUE_LINEAGE_UNVERIFIED": "VALUE_LINEAGE_UNVERIFIED: a value selected a missing or quote fact. ",
    }.get(code, "The evidence selection is invalid. ")
    return (
        problem
        + 'Use only existing answer_facts IDs. For kind cell or derived, use values: [{"fact_id": "ID"}]. '
        "This includes strings, numbers, booleans, nulls and aggregates. Do not quote or copy their values. "
        'For kind quote, use quotes: [{"fact_id": "ID", "quote": "exact passage"}]. '
        "Select exact contiguous source quotations only. For separated sentences, use separate "
        "QuoteSelections, even with the same fact_id. Never paraphrase or join noncontiguous passages. "
        "Keep the requested language as en or es. Use insufficient_evidence with empty selections "
        "when no recorded facts answer the question. Never invent IDs, values or factual prose."
    )
