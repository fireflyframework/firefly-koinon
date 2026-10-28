# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Report deployment model roles independently from tenant conversation connections."""

from importlib import import_module

from pyfly.container import Container, component
from pyfly.data.relational.datasource_registry import DataSourceRegistry

ROLES = {
    "documents": (
        "flycanon.config",
        "CanonSettings",
        {
            "documents.embedding": "embedding_model",
            "documents.answer": "answer_model",
            "documents.rlm_root": "rlm_root_model",
            "documents.rlm_sub": "rlm_sub_model",
        },
    ),
    "structured": (
        "flyquery.config",
        "FlyquerySettings",
        {
            "structured.grounding": "grounding_model",
            "structured.generation": "generation_model",
            "structured.critic": "critic_model",
            "structured.explainer": "explainer_model",
        },
    ),
}
TOOLS = {
    "search_knowledge": ["documents.embedding"],
    "inspect_schema": ["structured.datasource"],
    "query_dataset": [
        "structured.datasource",
        "structured.grounding",
        "structured.generation",
        "structured.critic",
        "structured.explainer",
    ],
}


@component(name="assistants.dependencies")
class ConnectionDependencies:
    def __init__(self, container: Container, datasource_registry: DataSourceRegistry):
        self.container, self.sources = container, datasource_registry

    def describe(self) -> list[dict]:
        result = []
        for domain, (module, name, roles) in ROLES.items():
            settings = None
            try:
                cls = getattr(import_module(module), name)
                if self.container.contains_type(cls):
                    settings = self.container.resolve(cls)
            except ImportError:
                pass
            for role, field in roles.items():
                value = getattr(settings, field, "") if settings is not None else ""
                provider, _, model = value.partition(":")
                result.append(
                    {
                        "id": role,
                        "ownership": "deployment",
                        "read_only": True,
                        "provider": provider or None,
                        "model_id": model or None,
                        "configured": bool(value),
                        "available": None,
                        "status": "unverified" if value else "needs_setup",
                        "reason": "Deployment model setting; credentials and serving capability "
                        "remain unverified. "
                        "Tenant conversation settings do not replace this role."
                        if value
                        else "Bind the knowledge module and configure its deployment model.",
                    }
                )
            result.append(
                {
                    "id": domain + ".datasource",
                    "ownership": "deployment",
                    "read_only": True,
                    "configured": settings is not None
                    and ("canon" if domain == "documents" else "structured") in self.sources.names(),
                    "available": None,
                    "status": "unverified",
                    "reason": "Database connection is observed separately in deployment diagnostics.",
                }
            )
        return result

    def for_tools(self, tools: list[str]) -> list[dict]:
        roles = self.describe()
        return [
            {**next(row for row in roles if row["id"] == role), "tool": tool}
            for tool in tools
            for role in TOOLS.get(tool, [])
        ]
