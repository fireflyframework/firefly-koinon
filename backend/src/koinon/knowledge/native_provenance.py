# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product-only authority checks for borrowed native provenance observers."""

from contextlib import contextmanager
from functools import wraps
from importlib import import_module
from uuid import UUID

from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import select, text

from koinon.integrations.content_sources.read_dtos import LocalSourcePin
from koinon.knowledge.capture_dtos import NativeDatabaseContext
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt


def bind_structured_source(receipt, operation, asset_id, binding):
    """Bind exact dataset authority to this task's native identity observer."""
    admission = StructuredSourceAdmission(receipt, operation, asset_id, binding)
    receipt.structured_admission = admission.admit
    receipt.structured_source_operation = operation


class StructuredSourceAdmission:
    def __init__(self, receipt, operation, asset_id, binding):
        self.receipt, self.operation = receipt, operation
        self.asset_id, self.binding = asset_id, binding

    async def _read(self, sql, parameters):
        from koinon.knowledge.adapters import native_scope

        with native_scope(
            "structured", self.operation.tenant, self.binding.native_workspace_id, self.operation.actor
        ):
            async with infrastructure_unit("structured", read_only=True) as session:
                result = await session.execute(text(sql), parameters)
                return [dict(row) for row in result.mappings()]

    async def _snapshots(self, pins):
        from types import SimpleNamespace

        from koinon.integrations.content_sources.errors import SourceError

        if not pins:
            return
        if len(pins) > 500:
            raise SourceError("size_exceeded")
        existing = self.receipt.structured_source_manifest
        if len(existing.keys() | pins.keys()) > 500:
            raise SourceError("size_exceeded")
        if any(key in existing and existing[key] != value for key, value in pins.items()):
            raise SourceError("version_changed")
        rows = await self._read(
            """SELECT ss.table_id,ss.id AS snapshot_id FROM flyquery_schema_snapshots ss
            JOIN flyquery_tables t ON t.id=ss.table_id
            WHERE ss.id=ANY(:ids) AND ss.dataset_id=:ds AND t.dataset_id=:ds
              AND ss.tenant_id=:tenant AND ss.workspace_id=:ws AND ss.status='READY'""",
            {
                "ids": [UUID(str(snapshot)) for snapshot in pins.values()],
                "ds": UUID(self.binding.native_id),
                "tenant": self.operation.tenant,
                "ws": UUID(self.binding.native_workspace_id),
            },
        )
        actual = {str(row["table_id"]): str(row["snapshot_id"]) for row in rows}
        if actual != pins:
            raise SourceError("access_denied")
        references = tuple(
            SimpleNamespace(
                id=snapshot,
                asset_id=self.asset_id,
                kind="dataset",
                snapshot_id=snapshot,
                source_version_id=None,
                extraction_id=None,
                query_id=None,
                knowledge_version_id=None,
            )
            for snapshot in pins.values()
        )
        await self.operation.reader.sources(
            self.operation.actor,
            self.operation.tenant,
            references,
            operation=self.operation,
        )
        existing.update(pins)

    async def admit(self, kind, rows, scope):
        from koinon.integrations.content_sources.errors import SourceError

        self.receipt.scope(scope.tenant_id, scope.workspace_id, scope.actor)
        if (scope.tenant_id, scope.workspace_id, scope.dataset_id, scope.actor) != (
            self.operation.tenant,
            self.binding.native_workspace_id,
            self.binding.native_id,
            self.operation.actor,
        ):
            raise SourceError("access_denied")
        if kind in {"schema", "table"}:
            pins = {}
            for row in rows:
                table, snapshot = str(row["table_id"]), str(row["snapshot_id"])
                if table in pins and pins[table] != snapshot:
                    raise SourceError("version_changed")
                pins[table] = snapshot
            await self._snapshots(pins)
            return rows
        selected = []
        imported = any(
            isinstance(pin, LocalSourcePin) and pin.domain == "structured" for pin in self.operation.used
        )
        for row in rows:
            if row.get("unknown_lineage"):
                continue
            if kind in {"example", "turn"}:
                query_id = row.get("query_id")
                if query_id:
                    values = await self._read(
                        "SELECT table_id_snapshot_pins_json AS pins FROM flyquery_queries "
                        "WHERE id=:id AND dataset_id=:ds AND tenant_id=:tenant AND workspace_id=:ws",
                        {
                            "id": UUID(str(query_id)),
                            "ds": UUID(self.binding.native_id),
                            "tenant": scope.tenant_id,
                            "ws": UUID(scope.workspace_id),
                        },
                    )
                    if len(values) != 1 or not values[0]["pins"]:
                        continue
                    await self._snapshots(values[0]["pins"])
                elif kind == "turn":
                    pins = row.get("snapshot_pins")
                    if not isinstance(pins, dict) or not pins:
                        continue
                    # Legacy turns pin by table name. Resolve names in SQL and
                    # expose only table IDs, retaining the recorded snapshot.
                    import json

                    identities = await self._read(
                        "SELECT t.id AS table_id,p.value::uuid AS snapshot_id FROM "
                        "jsonb_each_text(CAST(:pins AS jsonb)) p JOIN flyquery_tables t ON t.name=p.key "
                        "WHERE t.dataset_id=:ds",
                        {"pins": json.dumps(pins), "ds": UUID(self.binding.native_id)},
                    )
                    if len(identities) != len(pins):
                        continue
                    await self._snapshots(
                        {str(item["table_id"]): str(item["snapshot_id"]) for item in identities}
                    )
                elif (
                    row.get("source") == "AGENT_LEARNED"
                    or imported
                    or row.get("dataset_id")
                    and str(row["dataset_id"]) != scope.dataset_id
                ):
                    continue
            elif kind == "relation":
                if imported:
                    continue
                endpoints = {row["from_table_id"], row["to_table_id"]}
                identities = await self._read(
                    "SELECT id AS table_id,current_snapshot_id AS snapshot_id FROM flyquery_tables "
                    "WHERE id=ANY(:ids) AND dataset_id=:ds AND is_active=true",
                    {"ids": list(endpoints), "ds": UUID(self.binding.native_id)},
                )
                if len(identities) != len(endpoints) or any(not item["snapshot_id"] for item in identities):
                    continue
                await self._snapshots(
                    {str(item["table_id"]): str(item["snapshot_id"]) for item in identities}
                )
            elif kind == "metric":
                manifest = row.get("source_manifest")
                if manifest is None and imported:
                    continue
                if manifest is not None:
                    if not isinstance(manifest, dict) or not manifest:
                        continue
                    await self._snapshots(manifest)
            elif kind == "glossary":
                # Nonempty references must be immutable IDs with complete
                # lineage. Legacy names are retained, but never broaden access.
                if imported and (row.get("columns") or row.get("metrics")):
                    continue
            else:
                raise SourceError("unavailable")
            selected.append(row)
        return tuple(selected)


def evidence_bound(domain):
    def decorate(operation):
        @wraps(operation)
        async def bound(self, *args, **kwargs):
            supplied = kwargs.get("_capture") is not None
            receipt = kwargs.get("_capture") or NativeEvidenceReceipt(kwargs["actor"], kwargs["tenant_id"])
            kwargs["_capture"] = receipt
            try:
                with evidence_scope(self, receipt, domain, kwargs):
                    return await operation(self, *args, **kwargs)
            finally:
                if not supplied:
                    receipt.closed = True

        return bound

    return decorate


@contextmanager
def evidence_scope(domains, receipt, domain, arguments):
    package = "flycanon" if domain == "canon" else "flyquery"
    observer = import_module(package + ".core.services.query.provenance")
    if domain == "structured":

        async def verify(scope, objects):
            return await verify_structured(domains, scope, objects)

        receipt.verify_structured = verify
    with observer.observe(
        receipt,
        tenant_id=arguments["tenant_id"],
        workspace_id=arguments["workspace_id"],
        dataset_id=arguments.get("dataset_id", ""),
        actor=arguments["actor"],
        **({"source_ids": arguments["source_ids"]} if domain == "canon" else {}),
    ):
        yield


async def verify_structured(domains, scope, objects):
    from flyquery.models.entities.schema import SchemaObject, SchemaSnapshot
    from flyquery.models.entities.table import Table

    from koinon.knowledge.adapters import native_scope

    try:
        source = domains._resolve(DataSourceRegistry).get("structured")
        ids = {UUID(value) for value in objects}
        dataset, workspace = UUID(scope.dataset_id), UUID(scope.workspace_id)
    except (KeyError, ValueError, TypeError) as error:
        raise ServiceUnavailableException(
            "Native schema provenance is unavailable", code="EVIDENCE_UNAVAILABLE"
        ) from error
    with native_scope("structured", scope.tenant_id, scope.workspace_id, scope.actor):
        async with infrastructure_unit(source, read_only=True) as session:
            rows = (
                await session.execute(
                    select(SchemaObject.id, SchemaObject.table_id, SchemaObject.snapshot_id)
                    .join(SchemaSnapshot, SchemaSnapshot.id == SchemaObject.snapshot_id)
                    .join(Table, Table.id == SchemaObject.table_id)
                    .where(
                        SchemaObject.id.in_(ids),
                        SchemaObject.tenant_id == scope.tenant_id,
                        SchemaObject.workspace_id == workspace,
                        Table.dataset_id == dataset,
                        Table.workspace_id == workspace,
                        Table.tenant_id == scope.tenant_id,
                        SchemaSnapshot.dataset_id == dataset,
                        SchemaSnapshot.workspace_id == workspace,
                        SchemaSnapshot.tenant_id == scope.tenant_id,
                        SchemaSnapshot.status == "READY",
                    )
                )
            ).all()
            engine = session.get_bind().dialect.name
            identity = (
                (
                    await session.execute(
                        text(
                            "SELECT current_database() AS database, current_catalog AS catalog, "
                            "current_schema() AS schema"
                        )
                    )
                )
                .mappings()
                .one()
                if engine == "postgresql"
                else {}
            )
    if {str(row.id): (str(row.table_id), str(row.snapshot_id)) for row in rows} != objects:
        return False
    return NativeDatabaseContext(
        engine, identity.get("database"), identity.get("catalog"), identity.get("schema")
    )
