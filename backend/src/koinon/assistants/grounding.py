# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bound the model's view while retaining the exact authorized evidence for the UI."""

import json

from koinon.assistants.context_budget import ConservativeTokenEstimator


def evidence_view(kind: str, data: dict, evidence_id: str, budget: int) -> dict:
    key = {"search": "hits", "query": "preview", "schema": "tables"}[kind]
    view: dict = {"evidence_id": evidence_id, key: [], "truncated": False}
    if kind == "query":
        view.update(
            {name: data[name] for name in ("query_id", "execution_status", "row_count") if name in data}
        )
    estimator = ConservativeTokenEstimator()

    def fits(value):
        return (
            estimator.estimate(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")))
            <= budget
        )

    records = data.get(key) or []
    if kind == "search" and data.get("no_answer") is True:
        view["no_answer"] = True
        records = []
    final_answer = data.get("answer") if kind == "search" else None
    analysis_pending = isinstance(final_answer, str) and bool(final_answer.strip())
    for record in records:
        candidate = {**view, key: [*view[key], record]}
        if not fits(candidate):
            view["truncated"] = True
            break
        view = candidate
        if analysis_pending:
            analysis = {
                "text": final_answer,
                "citations": data.get("citations") or [],
                "result_id": evidence_id,
            }
            while analysis["text"] and not fits({**view, "derived_analysis": analysis}):
                analysis["text"] = analysis["text"][: len(analysis["text"]) // 2]
                analysis["truncated"] = True
                view["truncated"] = True
            if analysis["text"] and fits({**view, "derived_analysis": analysis}):
                view["derived_analysis"] = analysis
            else:
                view["truncated"] = True
            analysis_pending = False
    if not fits(view):
        return {"evidence_id": evidence_id, "truncated": True}
    return view


def has_evidence(kind: str, view: dict) -> bool:
    if kind == "query":
        return view.get("execution_status") in {"OK", "REFINED_OK"} and bool(view.get("preview"))
    if kind == "search":
        return view.get("no_answer") is not True and any(
            isinstance(hit, dict) and isinstance(hit.get("text"), str) and hit["text"].strip()
            for hit in view.get("hits", [])
        )
    return False


def refusal_message(language: str, code: str = "KNOWLEDGE_ONLY") -> str:
    messages = {
        "RLM_DOCUMENT_VIEWS_REQUIRED": (
            "The selected documents do not have the recorded views required for RLM. "
            "Ask an administrator to review the source prerequisites.",
            "Los documentos seleccionados no tienen las vistas registradas que requiere RLM. "
            "Pide a un administrador que revise los requisitos de las fuentes.",
        ),
        "KNOWLEDGE_RLM_UNQUALIFIED": (
            "RLM is not qualified for curated knowledge. Choose a supported source or "
            "ask an organization administrator to review the answer mode.",
            "RLM aún no está validado para el conocimiento curado. Elige una fuente compatible "
            "o pide a un administrador que revise el modo de respuesta.",
        ),
        "KNOWLEDGE_SETTINGS_SNAPSHOT_REQUIRED": (
            "This answer has no recorded knowledge settings. Start a new answer.",
            "Esta respuesta no tiene una configuración de conocimiento registrada. "
            "Inicia una nueva respuesta.",
        ),
        "KNOWLEDGE_SETTINGS_SNAPSHOT_INVALID": (
            "The recorded knowledge settings for this answer could not be verified. Start a new answer.",
            "No se pudo verificar la configuración de conocimiento registrada para esta respuesta. "
            "Inicia una nueva respuesta.",
        ),
        "EVIDENCE_BUDGET_EXCEEDED": (
            "This question exceeded the source audit budget. Narrow the question or select fewer sources.",
            "Esta pregunta superó el límite de auditoría de fuentes. "
            "Precisa la pregunta o elige menos fuentes.",
        ),
        "EVIDENCE_UNAVAILABLE": (
            "Access to a source used by this answer changed. "
            "Reopen the conversation after access is restored.",
            "Cambió el acceso a una fuente de esta respuesta. "
            "Vuelve a abrir el chat cuando se restablezca el acceso.",
        ),
        "EVIDENCE_PROVENANCE_REQUIRED": (
            "I couldn't verify the exact sources and revisions for this answer. Select another "
            "source or retry after indexing finishes.",
            "No pude verificar las fuentes y revisiones exactas de esta respuesta. Selecciona "
            "otra fuente o vuelve a intentar cuando termine la indexación.",
        ),
        "FACTUAL_EVIDENCE_REQUIRED": (
            "Schema definitions alone do not support a factual answer. Query the data or select "
            "document passages.",
            "El esquema por sí solo no sustenta una respuesta factual. Consulta los datos o "
            "selecciona pasajes de documentos.",
        ),
        "NO_MATCHING_EVIDENCE": (
            "The verified search or query returned no usable passages or rows. Refine the "
            "question or select another source.",
            "La búsqueda o consulta verificada no devolvió pasajes ni filas utilizables. Precisa "
            "la pregunta o selecciona otra fuente.",
        ),
        "REVIEW_REQUIRED": (
            "A change proposal is ready for your review. Nothing has been applied.",
            "Hay una propuesta de cambio lista para tu revisión. No se ha aplicado ningún cambio.",
        ),
    }
    if code in messages:
        return messages[code][1 if language.lower().startswith("es") else 0]
    if language.lower().startswith("es"):
        return (
            "Solo puedo ayudar con el conocimiento de tu organización. "
            "No pude fundamentar una respuesta en los documentos o datos seleccionados."
        )
    return (
        "I can help with your organization's knowledge. "
        "I could not ground an answer in the selected documents or datasets."
    )
