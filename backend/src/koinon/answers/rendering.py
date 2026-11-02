# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import re
from dataclasses import dataclass

from pydantic import JsonValue

from koinon.answers.dtos import EvidenceAnswerPlan
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.answer_evidence import AnswerFact


class AnswerSelectionError(ValueError):
    """A safe selection code; source content never belongs in retry diagnostics."""

    def __init__(self, code: str, *, repairable: bool = False):
        self.code, self.repairable = code, repairable
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RenderedAnswer:
    text: str
    citations: tuple[dict[str, JsonValue], ...]
    fact_ids: tuple[str, ...]
    source_refs: tuple[SourceReference, ...] = ()


def render_answer(
    plan: EvidenceAnswerPlan,
    facts: tuple[AnswerFact, ...],
    language: str,
    *,
    private_fact_ids: frozenset[str] = frozenset(),
) -> RenderedAnswer:
    if plan.outcome == "product_help":
        raise AnswerSelectionError("PRODUCT_CONTEXT_REQUIRED")
    spanish = language.lower().startswith("es")
    if plan.outcome == "insufficient_evidence":
        text = (
            "No pude establecer una respuesta con evidencia verificable del conocimiento seleccionado. "
            "Precisa la pregunta o selecciona otra fuente."
            if spanish
            else "I could not establish an answer from verifiable evidence in the selected knowledge. "
            "Refine the question or select another source."
        )
        return RenderedAnswer(text, (), ())
    pool = {}
    for fact in facts:
        if fact.id in pool and pool[fact.id] != fact:
            raise AnswerSelectionError("CONFLICTING_FACT_ID")
        pool[fact.id] = fact
    selected = []
    for choice in plan.quotes:
        fact = pool.get(choice.fact_id)
        if (
            fact is None
            or fact.kind != "quote"
            or not fact.text
            or not choice.quote.strip()
            or choice.quote not in fact.text
        ):
            raise AnswerSelectionError("QUOTE_NOT_RECORDED", repairable=True)
        if fact.id not in private_fact_ids and not any(
            source.used_revision and source.quote and fact.text in source.quote for source in fact.source_refs
        ):
            raise AnswerSelectionError("QUOTE_REFERENCE_UNVERIFIED")
        if fact.id in private_fact_ids and not re.fullmatch(r"[a-f0-9]{64}", fact.lineage_sha256):
            raise AnswerSelectionError("PRIVATE_REFERENCE_UNVERIFIED")
        selected.append((fact, choice.quote))
    for choice in plan.values:
        fact = pool.get(choice.fact_id)
        if (
            fact is None
            or fact.kind not in {"cell", "derived"}
            or not fact.source_refs
            or not re.fullmatch(r"[a-f0-9]{64}", fact.lineage_sha256)
        ):
            raise AnswerSelectionError(
                "VALUE_LINEAGE_UNVERIFIED", repairable=fact is None or fact.kind == "quote"
            )
        value = (
            ("Sin valor registrado" if spanish else "No value recorded")
            if fact.value is None
            else ("Sí" if spanish else "Yes")
            if fact.value is True
            else ("No" if fact.value is False else str(fact.value))
        )
        selected.append((fact, value))
    paragraphs = [
        "El conocimiento seleccionado contiene esta información:"
        if spanish
        else "The selected knowledge contains this information:"
    ]
    citations, sources, identifiers = {}, {}, []
    for fact, text in selected:
        identifiers.append(fact.id)
        if fact.kind == "quote":
            paragraphs.append(("Fuente: " if spanish else "Source: ") + fact.label + "\n“" + text + "”")
        else:
            paragraphs.append(fact.label + ": " + text)
        for source in fact.source_refs:
            sources[source.id] = source
            citations[source.id] = {
                "asset_id": source.asset_id,
                "source_id": source.source_id,
                "title": source.title,
                "text": text,
            }
    text = "\n\n".join(paragraphs)
    if len(text) > 256000:
        raise AnswerSelectionError("ANSWER_TOO_LARGE")
    return RenderedAnswer(
        text, tuple(citations.values()), tuple(dict.fromkeys(identifiers)), tuple(sources.values())
    )
