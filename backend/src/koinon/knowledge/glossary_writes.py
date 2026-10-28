# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded original glossary writes keep the original native service and database transaction."""

import json
from uuid import UUID

from pydantic import ValidationError
from pyfly.container import component
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import PayloadTooLargeException
from sqlalchemy import text

from koinon.catalog.errors import AccessDenied, InvalidHierarchy
from koinon.knowledge.adapters import native_scope
from koinon.knowledge.legacy_read import LegacyReadAdmission
from koinon.web.capabilities import CapabilityRegistry
from koinon.web.legacy_security import LegacyOperationPolicies

GLOSSARY_WRITES = (
    ("POST", "/glossary"),
    ("PUT", "/glossary/{term_id}"),
    ("DELETE", "/glossary/{term_id}"),
    ("POST", "/agent/glossary"),
    ("PUT", "/agent/glossary/{term_id}"),
    ("DELETE", "/agent/glossary/{term_id}"),
)
ALIASES = {
    "synonyms": "synonyms_json",
    "tags": "tags_json",
    "related_columns": "related_columns_json",
    "related_metrics": "related_metrics_json",
}
ARRAYS = tuple(ALIASES.values())


@component(name="knowledge.legacy_glossary_write_admission")
class LegacyGlossaryWriteAdmission:
    def __init__(
        self, read: LegacyReadAdmission, policies: LegacyOperationPolicies, capabilities: CapabilityRegistry
    ):
        self.read, self.knowledge, self.datasources = read, read.knowledge, read.datasources
        if capabilities.domains.get("structured", {}).get("registered"):
            for method, path in GLOSSARY_WRITES:
                policies.register(
                    "structured",
                    method,
                    path,
                    self.verify,
                    "catalog:write",
                    agent_scopes=("flyquery.semantic:author",) if path.startswith("/agent/") else (),
                )

    async def _payload(self, request):
        from flyquery.core.services.glossary.errors import GlossaryPayloadInvalid
        from flyquery.interfaces.glossary import GlossaryTermCreate, GlossaryTermUpdate

        body = bytearray()
        async for block in request.stream():
            body.extend(block)
            if len(body) > 65536:
                raise PayloadTooLargeException(
                    "Glossary JSON exceeds 64 KiB", code="GLOSSARY_PAYLOAD_TOO_LARGE"
                )
        raw = bytes(body)
        request.scope["pyfly.request_body"] = raw
        try:
            value = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError as error:
            raise GlossaryPayloadInvalid("Supply UTF-8 glossary JSON") from error
        allowed = {"definition", *ALIASES, *ARRAYS} | ({"term"} if request.method == "POST" else set())
        if (
            not isinstance(value, dict)
            or set(value) - allowed
            or any(alias in value and field in value for alias, field in ALIASES.items())
        ):
            raise GlossaryPayloadInvalid("Use only glossary fields and one spelling per field")
        try:
            model = (GlossaryTermCreate if request.method == "POST" else GlossaryTermUpdate).model_validate(
                value, strict=True
            )
        except ValidationError as error:
            raise GlossaryPayloadInvalid("Supply valid glossary text and string arrays") from error
        fields = model.model_dump(exclude_unset=True)
        for name, maximum in (("term", 512), ("definition", 16000)):
            field = fields.get(name)
            if field is not None and (not field.strip() or len(field) > maximum):
                raise GlossaryPayloadInvalid("Glossary term/definition exceeds its text bounds")
        for name in ARRAYS:
            field = fields.get(name)
            if field is not None and (
                len(field) > 64 or any(not item.strip() or len(item) > 512 for item in field)
            ):
                raise GlossaryPayloadInvalid(
                    "Use up to 64 nonempty strings of 512 characters per glossary array",
                )
        return fields

    async def _term(self, tenant, workspace, actor, identifier):
        from flyquery.core.services.glossary.glossary_service import GlossaryService

        with native_scope("structured", tenant, workspace, actor):
            return await self.knowledge.domains._resolve(GlossaryService).get(UUID(identifier))

    async def _reference(self, tenant, workspace, kind, value):
        if kind == "column":
            statement = """
                SELECT so.id FROM flyquery_schema_objects so
                JOIN flyquery_tables t ON t.id=so.table_id AND t.current_snapshot_id=so.snapshot_id
                WHERE so.tenant_id=:tenant AND so.workspace_id=:workspace AND so.kind='COLUMN'
                  AND t.tenant_id=:tenant AND t.workspace_id=:workspace AND t.is_active=true
                  AND (CAST(so.id AS text)=:value OR so.qualified_name=:value
                       OR right(so.qualified_name,length(:value)+1)='.'||:value)
                ORDER BY so.id LIMIT 2
            """
        elif kind == "metric":
            statement = """
                SELECT m.id FROM flyquery_semantic_metrics m
                JOIN flyquery_datasets d ON d.id=m.dataset_id
                WHERE m.tenant_id=:tenant AND m.workspace_id=:workspace AND m.status!='RETIRED'
                  AND d.tenant_id=:tenant AND d.workspace_id=:workspace
                  AND (CAST(m.id AS text)=:value OR m.name=:value OR d.name||'.'||m.name=:value)
                ORDER BY m.id LIMIT 2
            """
        else:
            raise ValueError("Unreviewed glossary reference kind")
        async with infrastructure_unit(self.datasources.get("structured")) as session:
            rows = list(
                await session.scalars(
                    text(statement), {"tenant": tenant, "workspace": UUID(workspace), "value": value}
                )
            )
        if len(rows) != 1:
            raise AccessDenied(
                "A glossary reference must identify one admitted current resource",
                code="GLOSSARY_REFERENCE_UNAVAILABLE",
            )
        return str(rows[0])

    async def verify(self, request, identity, tenant, workspace, parameters):
        from flyquery.core.services.glossary.errors import GlossaryRevisionConflict, GlossaryRevisionRequired
        from flyquery.web.conventions.glossary_revisions import expected_glossary_revision

        chain = await self.knowledge._chain(identity.subject, tenant, workspace, "catalog:write")
        if chain[0].kind != "workspace":
            raise InvalidHierarchy("Select a canonical workspace", code="INVALID_WORKSPACE")
        restriction = self.knowledge.catalog.restriction
        grant = await restriction.grant(identity.subject) if restriction else None
        if grant is not None and grant.asset_ids is not None:
            raise AccessDenied(
                "Workspace glossary writes cannot project an exact-asset token", code="TOKEN_SCOPE_DENIED"
            )
        fields = await self._payload(request) if request.method != "DELETE" else {}
        try:
            binding = await self.knowledge.binding(tenant, workspace, "structured", entry=chain[0])
        except AccessDenied as error:
            if error.code != "BINDING_UNAVAILABLE" or request.method != "POST":
                raise
            binding = await self.knowledge._workspace(identity.subject, tenant, chain[0], "structured")
        await self.read.verify("structured", request, identity, tenant, workspace, parameters)
        native_workspace = binding.native_id
        request.state.verified_native_workspace_id = native_workspace
        existing = {}
        if parameters.get("term_id"):
            existing = await self._term(tenant, native_workspace, identity.subject, parameters["term_id"])
            if (
                not existing
                or existing["tenant_id"] != tenant
                or str(existing["workspace_id"]) != native_workspace
            ):
                raise AccessDenied("Glossary term is outside this workspace", code="LEGACY_SCOPE_DENIED")
            expected = expected_glossary_revision(request)
            if expected is None:
                raise GlossaryRevisionRequired()
            if expected != existing["updated_at"]:
                raise GlossaryRevisionConflict()
        if request.method == "DELETE":
            return
        with native_scope("structured", tenant, native_workspace, identity.subject):
            for name, kind, parameter in (
                ("related_columns_json", "column", "object_id"),
                ("related_metrics_json", "metric", "metric_id"),
            ):
                effective = fields.get(name)
                if effective is None:
                    effective = existing.get(name) or []
                if (
                    not isinstance(effective, list)
                    or len(effective) > 64
                    or any(
                        not isinstance(value, str) or not value.strip() or len(value) > 512
                        for value in effective
                    )
                ):
                    raise AccessDenied(
                        "Clear invalid historical glossary references before editing",
                        code="GLOSSARY_REFERENCE_UNAVAILABLE",
                    )
                for value in effective:
                    identifier = await self._reference(tenant, native_workspace, kind, value)
                    await self.read.verify(
                        "structured",
                        request,
                        identity,
                        tenant,
                        workspace,
                        {**parameters, parameter: identifier},
                    )
