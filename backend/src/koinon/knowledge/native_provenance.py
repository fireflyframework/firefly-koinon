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

from koinon.knowledge.capture_dtos import NativeDatabaseContext
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt


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
