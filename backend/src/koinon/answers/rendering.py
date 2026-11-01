# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import re
from dataclasses import dataclass

from pydantic import JsonValue

from koinon.answers.dtos import EvidenceAnswerPlan
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.answer_evidence import AnswerFact


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
            raise ValueError("A factual identifier cannot refer to different evidence")
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
            raise ValueError("A selected quotation must occur exactly in its recorded source")
        if fact.id not in private_fact_ids and not any(
            source.used_revision and source.quote and fact.text in source.quote for source in fact.source_refs
        ):
            raise ValueError("A source quotation needs an immutable source reference")
        if fact.id in private_fact_ids and not re.fullmatch(r"[a-f0-9]{64}", fact.lineage_sha256):
            raise ValueError("A private quotation needs its verified immutable input binding")
        selected.append((fact, choice.quote))
    for choice in plan.values:
        fact = pool.get(choice.fact_id)
        if (
            fact is None
            or fact.kind not in {"cell", "derived"}
            or not fact.source_refs
            or not re.fullmatch(r"[a-f0-9]{64}", fact.lineage_sha256)
        ):
            raise ValueError("A selected value needs verified native result and source lineage")
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
        raise ValueError("The selected factual answer exceeds the publication bound")
    return RenderedAnswer(
        text, tuple(citations.values()), tuple(dict.fromkeys(identifiers)), tuple(sources.values())
    )
