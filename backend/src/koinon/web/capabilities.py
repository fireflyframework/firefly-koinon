# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Report observed prerequisites separately from unverified provider configuration."""

from pyfly.container import Provider, rest_controller
from pyfly.core import Config
from pyfly.data.relational.sqlalchemy import SessionProvider
from pyfly.kernel import ServiceUnavailableException
from pyfly.web import get_mapping, request_mapping
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from koinon.knowledge.attachments.capabilities import AttachmentCapabilityService


class CapabilityRegistry:
    def __init__(self):
        self.domains: dict[str, dict] = {}


async def database_ready(sessions: SessionProvider) -> bool:
    try:
        async with sessions.unit(read_only=True) as session:
            await session.execute(text("SELECT id FROM lattice_tenants LIMIT 1"))
        return True
    except Exception:
        return False


@rest_controller
@request_mapping("")
class HealthController:
    def __init__(self, sessions: SessionProvider):
        self.sessions = sessions

    @get_mapping("/health")
    async def health(self) -> dict:
        return {"status": "up", "service": "firefly koinon"}

    @get_mapping("/ready")
    async def ready(self) -> JSONResponse:
        ready = await database_ready(self.sessions)
        return JSONResponse(
            {"status": "ready" if ready else "unavailable"}, status_code=200 if ready else 503
        )


@rest_controller
@request_mapping("/api/v1")
class CapabilitiesController:
    def __init__(
        self,
        config: Config,
        sessions: SessionProvider,
        registry: CapabilityRegistry,
        attachments: Provider[AttachmentCapabilityService | None],
    ):
        self.config, self.sessions, self.registry = config, sessions, registry
        self.attachments = attachments

    @get_mapping("/capabilities")
    async def capabilities(self) -> dict:
        database = await database_ready(self.sessions)
        model = str(self.config.get("pyfly.agentic.default-model", "") or "")
        provider = model.split(":", 1)[0] if model else "model-provider"
        features = [
            {
                "id": "catalog",
                "name": "Shared catalog and memberships",
                "available": database,
                "reason": None if database else "Catalog database is unavailable",
            }
        ]
        for domain in ("canon", "structured"):
            state = self.registry.domains.get(domain, {})
            features.append(
                {
                    "id": domain,
                    "name": "Document knowledge" if domain == "canon" else "Structured data",
                    "available": bool(state.get("qualified")) and database,
                    "reason": state.get("reason")
                    or (None if database else "Catalog database is unavailable"),
                }
            )
        features.append(
            {
                "id": "model-reasoning",
                "name": "Model reasoning",
                "available": False,
                "reason": "A configured model provider must pass connection qualification",
            }
        )
        attachments = None
        attachment_service = self.attachments.get()
        if attachment_service is not None:
            try:
                attachments = await attachment_service.deployment()
            except (ServiceUnavailableException, SQLAlchemyError, OSError, TimeoutError, ValueError):
                attachments = None
        attachment_ready = (
            attachments is not None
            and (attachments.storage.configured or attachments.storage.available is True)
            and all(value.available is True for value in (attachments.database, attachments.extraction))
        )
        features.append(
            {
                "id": "attachments",
                "name": "Private conversation attachments",
                "available": attachment_ready,
                "reason": "Private storage, database isolation and worker heartbeat were observed"
                if attachment_ready and attachments is not None and attachments.storage.available is True
                else "Storage configured; provider health is unknown; database and worker observed"
                if attachment_ready
                else "Private attachment prerequisites have not all been observed or enabled",
            }
        )
        providers = [
            {
                "id": provider,
                "name": model or "Model provider",
                "kind": "model",
                "configured": bool(model),
                "available": False,
                "reason": "Provider connection has not been verified"
                if model
                else "Select a provider and model",
                "capabilities": [],
            }
        ]
        result = {
            "providers": providers,
            "features": features,
            "catalog": {"ready": database},
            "agentic": {"configured": bool(model), "verified": False},
            "domains": self.registry.domains,
        }
        if attachments is not None:
            result["attachments"] = attachments.model_dump(mode="json")
        return result
