# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Render finite help topics exclusively from trusted current product configuration."""

from koinon.answers.help_dtos import HelpTopic, ProductHelpContext
from koinon.answers.rendering import RenderedAnswer


def render_product_help(topic: HelpTopic, context: ProductHelpContext, language: str) -> RenderedAnswer:
    if topic == "identity_and_capabilities":
        identity = render_product_help("identity", context, language)
        capabilities = render_product_help("capabilities", context, language)
        return RenderedAnswer(identity.text + "\n\n" + capabilities.text, (), ())
    spanish = language.lower().startswith("es")
    if topic == "identity":
        text = (
            f"Soy {context.assistant_name}, el asistente de {context.product_name}. "
            "Te ayudo a trabajar con el conocimiento al que tienes acceso."
            if spanish
            else f"I'm {context.assistant_name}, the assistant in {context.product_name}. "
            "I help you work with the knowledge you are allowed to access."
        )
    elif topic == "navigation":
        text = (
            "Abre la Biblioteca para explorar las fuentes que tienes autorizadas y vuelve al Chat "
            "para consultarlas. Seleccionar una fuente no amplía tus permisos."
            if spanish
            else "Open the Library to explore your authorized sources, "
            "then return to Chat to ask about them. "
            "Selecting a source does not expand your permissions."
        )
    elif topic == "capabilities":
        descriptions = {
            "search_knowledge": (
                "Search passages in your authorized knowledge.",
                "Buscar pasajes en el conocimiento autorizado.",
            ),
            "inspect_schema": (
                "Inspect the structure of authorized datasets.",
                "Consultar la estructura de los conjuntos de datos autorizados.",
            ),
            "query_dataset": (
                "Query authorized dataset values with recorded source lineage.",
                "Consultar valores de datos autorizados con su linaje registrado.",
            ),
            "propose_catalog_update": (
                "Prepare a name or description change proposal for your review; "
                "I do not apply it without approval.",
                "Preparar propuestas de nombre o descripción para tu revisión; no las aplico sin aprobación.",
            ),
            "search_private_attachments": (
                "Search recorded extracted text in your selected private files "
                "without publishing it to the organization.",
                "Buscar texto extraído registrado en tus archivos privados seleccionados, "
                "sin publicarlo en la organización.",
            ),
        }
        text = (
            ("En este contexto puedes pedirme:\n" if spanish else "In this context you can ask me to:\n")
            + "\n".join(descriptions[tool][int(spanish)] for tool in context.tools)
            if context.tools
            else (
                "No tengo herramientas de conocimiento disponibles en este contexto. Revisa la selección "
                "o pide a un administrador que revise permisos y configuración."
                if spanish
                else "No knowledge tools are available to me in this context. "
                "Review your selection or ask an "
                "administrator to review permissions and configuration."
            )
        )
    else:
        raise ValueError("Unknown product help topic")
    return RenderedAnswer(text, (), ())
