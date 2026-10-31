# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Report scoped knowledge connections separately from native deployment defaults."""

from importlib import import_module

from pyfly.container import Container, component
from pyfly.data.relational.datasource_registry import DataSourceRegistry

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.connections.service import KnowledgeConnectionService

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
    def __init__(
        self,
        container: Container,
        datasource_registry: DataSourceRegistry,
        knowledge_connections: KnowledgeConnectionService | None = None,
    ):
        self.container, self.sources = container, datasource_registry
        self.knowledge_connections = knowledge_connections

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
                        "reason": "Deployment default only; workspace knowledge assignments "
                        "are selected separately. "
                        "Credentials and serving capability remain unverified."
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

    async def for_scope(self, subject, tenant_id, tools, scope, *, current_agent=None):
        wanted = [(tool, role) for tool in tools for role in TOOLS.get(tool, [])]
        models = list(dict.fromkeys(role for _, role in wanted if not role.endswith(".datasource")))
        workspace = scope.get("workspace_id")
        reason = "Select an authorized workspace to inspect its effective knowledge connection."
        selected = {}
        if models and workspace is not None and self.knowledge_connections is not None:
            try:
                selected = await self.knowledge_connections.dependency_configurations(
                    subject, tenant_id, workspace, models
                )
                reason = "Configure this knowledge role for the selected workspace."
            except AccessDenied:
                reason = "Knowledge connection details are unavailable in this scope."
        elif workspace is not None:
            reason = "Knowledge connection configuration is unavailable."
        sources = None
        result = []
        for tool, role in wanted:
            if role.endswith(".datasource"):
                if sources is None:
                    sources = self.describe()
                result.append({**next(row for row in sources if row["id"] == role), "tool": tool})
                continue
            value = {
                "id": role,
                "tool": tool,
                "ownership": "deployment",
                "read_only": True,
                "provider": None,
                "model_id": None,
                "configured": False,
                "available": None,
                "status": "unverified",
                "reason": reason,
            }
            assignment = selected.get(role)
            if assignment is not None:
                label = assignment["scope"].capitalize() + " knowledge assignment"
                value.update(
                    provider=assignment["provider"],
                    model_id=assignment["model_id"],
                    configured=assignment["configured"],
                )
                if not assignment["enabled"]:
                    value.update(status="needs_setup", reason=label + " is disabled.")
                elif assignment["mode"] == "current_agent":
                    if current_agent is not None:
                        value.update(current_agent)
                    value["reason"] = label + " uses this current-agent connection; invocation is unverified."
                else:
                    value.update(
                        status="unverified" if assignment["configured"] else "needs_setup",
                        reason=label
                        + (
                            "; credentials, index compatibility and serving capability remain unverified."
                            if assignment["configured"]
                            else " needs an enabled admitted provider and model."
                        ),
                    )
            elif role in selected:
                value.update(status="needs_setup")
            result.append(value)
        return result
