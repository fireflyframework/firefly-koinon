# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Scoped immutable file/section receipts; no inferred source or datum lineage."""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

from flyquery.core.services.ingestion.lineage import LineageError, observe
from flyquery.models.entities.file import File
from flyquery.models.entities.schema import SchemaSnapshot
from flyquery.models.entities.table import Table
from pyfly.container import service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException, InvalidRequestException
from sqlalchemy import func, select, update

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.lineage.dtos import LineagePage, SnapshotLineage, SourceArtifact, TransformStep
from koinon.knowledge.lineage.entities import (
    SnapshotLineageRow,
    SourceArtifactRow,
    TransformRunRow,
    TransformStepRow,
)
from koinon.knowledge.lineage.ports import StructuredSnapshotLineagePort
from koinon.knowledge.lineage.repositories import StructuredLineageRepository as Repo


def scope_of(values):
    return values["tenant_id"], UUID(str(values["workspace_id"])), UUID(str(values["dataset_id"]))


def denied():
    return AccessDenied("Snapshot lineage is unavailable in this scope", code="PROVENANCE_UNAVAILABLE")


@service(name="knowledge.structured_lineage")
class NativeStructuredLineage(StructuredSnapshotLineagePort):
    def __init__(self, datasources: DataSourceRegistry):
        self.datasources = datasources

    def sink(
        self,
        *,
        actor,
        tenant_id,
        workspace_id,
        operation,
        authorize,
        dataset_id=None,
        predecessor_snapshot_id=None,
    ):
        if operation not in {"upload", "replace", "reingest"}:
            raise LineageError("Unsupported lineage operation")
        return _Sink(
            self, actor, tenant_id, workspace_id, dataset_id, operation, predecessor_snapshot_id, authorize
        )

    @asynccontextmanager
    async def capture(self, **arguments):
        sink = self.sink(**arguments)
        await sink.authorize()
        with observe(sink):
            yield

    async def describe(self, session, snapshot_id, table_id, snapshot_status, values):
        scope = scope_of(values)
        row = await Repo.scope_row(session, SnapshotLineageRow, UUID(str(snapshot_id)), scope)
        common: dict[str, Any] = dict(
            tenant_id=scope[0],
            workspace_id=str(scope[1]),
            dataset_id=str(scope[2]),
            snapshot_id=str(snapshot_id),
            table_id=str(table_id),
            snapshot_status=snapshot_status,
        )
        if row is None:
            return SnapshotLineage(**common, status="not_recorded")
        if row.table_id != UUID(str(table_id)):
            raise denied()
        run = await Repo.scope_row(session, TransformRunRow, row.run_id, scope)
        artifact = await Repo.scope_row(session, SourceArtifactRow, run.artifact_id, scope) if run else None
        if run is None or artifact is None:
            raise denied()
        steps = await Repo.steps(session, run.id, scope)
        if len(steps) > 64:
            raise LineageError("Stored transform receipt exceeds its bounded pipeline invariant")
        return SnapshotLineage(
            **common,
            status="recorded",
            artifact=SourceArtifact(
                str(artifact.id),
                artifact.original_filename,
                artifact.sha256,
                artifact.byte_size,
                artifact.file_format,
                artifact.compression,
                artifact.actor,
                artifact.recorded_at,
            ),
            run_id=str(run.id),
            operation=run.operation,
            predecessor_snapshot_id=str(run.predecessor_snapshot_id) if run.predecessor_snapshot_id else None,
            sheet_or_json_path=run.sheet_or_json_path,
            table_label=run.table_label,
            parquet_sha256=row.parquet_sha256,
            parquet_byte_size=row.parquet_byte_size,
            schema_sha256=row.schema_sha256,
            reader_implementation=run.implementation,
            reader_sha256=run.implementation_sha256,
            parser_parameters=json.loads(json.dumps(run.parameters)),
            row_count=row.row_count,
            actor=row.actor,
            recorded_at=row.recorded_at,
            steps=tuple(
                TransformStep(
                    str(s.id),
                    s.ordinal,
                    s.kind,
                    s.implementation,
                    s.input_sha256,
                    s.output_sha256,
                    json.loads(json.dumps(s.parameters)),
                    s.actor,
                    s.recorded_at,
                    s.implementation_sha256,
                )
                for s in steps
            ),
        )

    async def read_snapshots(self, *, actor, tenant_id, workspace_id, dataset_id, snapshot_ids):
        from koinon.knowledge.adapters import native_scope

        if not 1 <= len(snapshot_ids) <= 500 or len(set(snapshot_ids)) != len(snapshot_ids):
            raise InvalidRequestException("Select 1–500 distinct snapshots", code="INVALID_PROVENANCE_SCOPE")
        values = dict(actor=actor, tenant_id=tenant_id, workspace_id=workspace_id, dataset_id=dataset_id)
        scope = scope_of(values)
        ids = [UUID(value) for value in snapshot_ids]
        with native_scope("structured", tenant_id, workspace_id, actor):
            async with infrastructure_unit(self.datasources.get("structured"), read_only=True) as session:
                rows = (
                    (
                        await session.execute(
                            select(SchemaSnapshot).where(
                                SchemaSnapshot.id.in_(ids),
                                SchemaSnapshot.tenant_id == tenant_id,
                                SchemaSnapshot.workspace_id == scope[1],
                                SchemaSnapshot.dataset_id == scope[2],
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                indexed = {row.id: row for row in rows}
                if set(indexed) != set(ids):
                    raise denied()
                return tuple(
                    [
                        await self.describe(session, i, indexed[i].table_id, indexed[i].status, values)
                        for i in ids
                    ]
                )

    async def read_table_history(
        self, *, actor, tenant_id, workspace_id, dataset_id, table_id, page=1, page_size=25
    ):
        from koinon.knowledge.adapters import native_scope

        if type(page) is not int or type(page_size) is not int or page < 1 or not 1 <= page_size <= 100:
            raise InvalidRequestException("Use a positive page and page_size up to100", code="INVALID_PAGE")
        values = dict(actor=actor, tenant_id=tenant_id, workspace_id=workspace_id, dataset_id=dataset_id)
        scope = scope_of(values)
        with native_scope("structured", tenant_id, workspace_id, actor):
            async with infrastructure_unit(self.datasources.get("structured"), read_only=True) as session:
                table = (
                    await session.execute(
                        select(Table).where(
                            Table.id == UUID(table_id),
                            Table.tenant_id == tenant_id,
                            Table.workspace_id == scope[1],
                            Table.dataset_id == scope[2],
                        )
                    )
                ).scalar_one_or_none()
                if table is None:
                    raise denied()
                if table.current_snapshot_id is not None:
                    current = (
                        await session.execute(
                            select(SchemaSnapshot.id).where(
                                SchemaSnapshot.id == table.current_snapshot_id,
                                SchemaSnapshot.table_id == table.id,
                                SchemaSnapshot.tenant_id == tenant_id,
                                SchemaSnapshot.workspace_id == scope[1],
                                SchemaSnapshot.dataset_id == scope[2],
                            )
                        )
                    ).scalar_one_or_none()
                    if current is None:
                        raise denied()
                filters = (
                    SchemaSnapshot.table_id == table.id,
                    SchemaSnapshot.tenant_id == tenant_id,
                    SchemaSnapshot.workspace_id == scope[1],
                    SchemaSnapshot.dataset_id == scope[2],
                )
                total = (
                    await session.execute(select(func.count()).select_from(SchemaSnapshot).where(*filters))
                ).scalar_one()
                rows = (
                    (
                        await session.execute(
                            select(SchemaSnapshot)
                            .where(*filters)
                            .order_by(SchemaSnapshot.taken_at.desc(), SchemaSnapshot.id.desc())
                            .offset((page - 1) * page_size)
                            .limit(page_size)
                        )
                    )
                    .scalars()
                    .all()
                )
                items = tuple(
                    [await self.describe(session, row.id, row.table_id, row.status, values) for row in rows]
                )
                return LineagePage(
                    items,
                    total,
                    page,
                    page_size,
                    (total + page_size - 1) // page_size,
                    page * page_size < total,
                    page > 1,
                    str(table.current_snapshot_id) if table.current_snapshot_id else None,
                )


class _Sink:
    def __init__(self, owner, actor, tenant, workspace, dataset, operation, predecessor, authorize):
        self.owner, self.actor = owner, actor
        self.tenant, self.workspace = tenant, UUID(str(workspace))
        self.dataset = UUID(str(dataset)) if dataset else None
        self.operation, self.predecessor, self.authorize = operation, predecessor, authorize
        self.locks = {}
        self.inputs = {}
        self.run_inputs = {}

    @property
    def scope(self):
        return self.tenant, self.workspace, self.dataset

    def values(self):
        return dict(
            tenant_id=self.tenant, workspace_id=self.workspace, dataset_id=self.dataset, actor=self.actor
        )

    def verify(self, values):
        if (
            values.get("tenant_id", self.tenant) != self.tenant
            or UUID(str(values.get("workspace_id", self.workspace))) != self.workspace
        ):
            raise denied()
        supplied = values.get("dataset_id")
        if self.dataset is None and supplied is not None:
            self.dataset = UUID(str(supplied))
        if self.dataset is None or supplied is not None and UUID(str(supplied)) != self.dataset:
            raise denied()
        if values.get("actor", self.actor) != self.actor:
            raise denied()

    async def emit(self, event, **values):
        self.verify(values)
        await self.authorize()
        if values.get("session") is not None:
            return await self.write(values["session"], event, values)
        run = str(values.get("run_id", ""))
        lock = self.locks.setdefault(run, asyncio.Lock())
        async with lock, infrastructure_unit(self.owner.datasources.get("structured")) as session:
            return await self.write(session, event, values)

    async def write(self, session, event, values):
        scoped = self.values()
        if event == "received":
            file = (
                await session.execute(
                    select(File).where(
                        File.id == values["file_id"],
                        File.tenant_id == self.tenant,
                        File.workspace_id == self.workspace,
                        File.dataset_id == self.dataset,
                    )
                )
            ).scalar_one_or_none()
            if file is None or (
                file.original_filename,
                file.content_hash_sha256,
                file.size_bytes,
                file.file_format,
                file.compression,
                file.uploaded_by,
            ) != (
                values["original_filename"],
                values["sha256"],
                values["byte_size"],
                values["file_format"],
                values["compression"],
                self.actor,
            ):
                raise denied()
            name = values["original_filename"]
            if not isinstance(name, str) or not 1 <= len(name) <= 512:
                raise LineageError("Original filename exceeds lineage limits")
            return await Repo.insert(
                session,
                SourceArtifactRow(
                    id=values["file_id"],
                    recorded_at=file.uploaded_at,
                    original_filename=name,
                    sha256=values["sha256"],
                    byte_size=values["byte_size"],
                    file_format=values["file_format"],
                    compression=values["compression"],
                    **scoped,
                ),
            )
        if event == "validate_input":
            artifact = await Repo.scope_row(session, SourceArtifactRow, values["file_id"], self.scope)
            if artifact is None:
                raise denied()
            if artifact.sha256 != values["input_sha256"] or artifact.compression != values["compression"]:
                raise LineageError("Parser input does not match the admitted original file")
            if values["compression"] == "none" and values["materialization_input_sha256"] != artifact.sha256:
                raise LineageError("Uncompressed parser input differs from the admitted original")
            self.inputs[str(artifact.id)] = (
                artifact.sha256,
                values["materialization_input_sha256"],
                artifact.compression,
            )
            return None
        if event == "target_mismatch":
            raise ConflictException(
                "The original table section is absent from the replacement file",
                code="CONTENT_SECTION_MISMATCH",
            )
        if event == "defer_table_file":
            if self.operation not in {"replace", "reingest"} or not self.predecessor:
                raise LineageError("Replacement requires the exact predecessor snapshot")
            artifact = await Repo.scope_row(session, SourceArtifactRow, values["file_id"], self.scope)
            if artifact is None:
                raise denied()
            return True
        if event == "begin_section":
            artifact = await Repo.scope_row(
                session, SourceArtifactRow, UUID(str(values["file_id"])), self.scope
            )
            if artifact is None:
                raise denied()
            if str(artifact.id) not in self.inputs:
                raise LineageError("Original parser input must be verified before section extraction")
            params = values["parameters"]
            if set(params) - {"workspace_locale", "type_infer_sample_rows", "max_title_rows", "compression"}:
                raise LineageError("Unregistered parser parameters")
            run = TransformRunRow(
                id=uuid4(),
                artifact_id=artifact.id,
                operation=self.operation,
                predecessor_snapshot_id=UUID(self.predecessor) if self.predecessor else None,
                sheet_or_json_path=values["sheet_or_json_path"],
                table_label=values["table_label"],
                implementation=values["implementation"],
                implementation_sha256=values.get("implementation_sha256"),
                parameters=params,
                **scoped,
            )
            await Repo.insert(session, run)
            self.run_inputs[str(run.id)] = self.inputs[str(artifact.id)]
            return str(run.id)
        if event in {"step", "model_input", "model_output"}:
            run = await Repo.scope_row(session, TransformRunRow, UUID(values["run_id"]), self.scope)
            if run is None:
                raise denied()
            steps = await Repo.steps(session, run.id, self.scope)
            if len(steps) + (2 if event == "model_input" or values.get("kind") == "stage_input" else 1) > 64:
                raise LineageError("The transform receipt reached its64-step bound")
            if values.get("kind") in {"decompress", "materialize"}:
                verified = self.run_inputs.get(str(run.id))
                if verified is None:
                    raise LineageError("Materialization input was not verified")
                raw, materialized, compression = verified
                if values.get("kind") == "decompress":
                    if (
                        compression == "none"
                        or values.get("input_sha256") != raw
                        or values.get("output_sha256") != materialized
                    ):
                        raise LineageError("Decompression receipt does not match the actual parser input")
                elif (
                    values.get("input_sha256") != materialized
                    or compression != "none"
                    and not any(
                        step.kind == "decompress" and step.output_sha256 == materialized for step in steps
                    )
                ):
                    raise LineageError(
                        "Materialization requires the admitted input and recorded decompression"
                    )
            parameters = values.get("parameters", {})
            if (
                set(parameters)
                - {
                    "columns",
                    "row_count",
                    "before_columns",
                    "after_columns",
                    "stage",
                    "role",
                    "model_reference",
                    "output_encoding",
                    "api",
                    "output_mode",
                    "binding_settings_sha256",
                    "transformation_identity_complete",
                    "constructor_identity_complete",
                    "binding_mode",
                    "assignment_id",
                    "assignment_revision",
                    "provider_id",
                    "provider_revision",
                    "selected_model_id",
                    "model_options_sha256",
                    "agent_id",
                    "agent_revision",
                    "model_class",
                    "instructions_sha256",
                    "applied_model_settings_sha256",
                }
                or len(json.dumps(parameters).encode()) > 65536
            ):
                raise LineageError("Transform parameters exceed their bounded schema")
            return await Repo.insert(
                session,
                TransformStepRow(
                    id=uuid4(),
                    run_id=run.id,
                    ordinal=len(steps) + 1,
                    kind=values.get("kind", event),
                    implementation_sha256=values.get("implementation_sha256"),
                    implementation=values["implementation"],
                    input_sha256=values.get("input_sha256"),
                    output_sha256=values.get("output_sha256"),
                    parameters=parameters,
                    **scoped,
                ),
            )
        if event == "bind_snapshot":
            actual = (
                await session.execute(
                    select(SchemaSnapshot.id).where(
                        SchemaSnapshot.id == values["snapshot_id"],
                        SchemaSnapshot.table_id == values["table_id"],
                        SchemaSnapshot.tenant_id == self.tenant,
                        SchemaSnapshot.workspace_id == self.workspace,
                        SchemaSnapshot.dataset_id == self.dataset,
                    )
                )
            ).scalar_one_or_none()
            if actual is None:
                raise denied()
            receipt = values.get("receipt") or {}
            if not receipt.get("run_id"):
                raise LineageError("Product snapshot requires a materialization receipt")
            run = await Repo.scope_row(session, TransformRunRow, UUID(receipt["run_id"]), self.scope)
            steps = await Repo.steps(session, run.id, self.scope) if run else ()
            if (
                not steps
                or steps[-1].kind != "finalize_parquet"
                or steps[-1].output_sha256 != receipt["parquet_sha256"]
            ):
                raise LineageError("Final Parquet receipt does not match the snapshot")
            binding = await Repo.insert(
                session,
                SnapshotLineageRow(
                    snapshot_id=values["snapshot_id"],
                    run_id=run.id,
                    table_id=values["table_id"],
                    parquet_sha256=receipt["parquet_sha256"],
                    parquet_byte_size=receipt["parquet_byte_size"],
                    row_count=values["row_count"],
                    schema_sha256=values["schema_sha256"],
                    **scoped,
                ),
            )
            coordinates = values.get("coordinates")
            if coordinates is not None:
                from koinon.knowledge.lineage.coordinate_service import persist_coordinates

                validated = self.run_inputs.get(str(run.id))
                if validated is None:
                    raise LineageError("Coordinate input must be validated in this materialization scope")
                await persist_coordinates(
                    session,
                    **scoped,
                    table_id=values["table_id"],
                    snapshot_id=values["snapshot_id"],
                    run_id=run.id,
                    artifact_id=run.artifact_id,
                    coordinates=coordinates,
                    row_count=values["row_count"],
                    column_count=values["column_count"],
                    input_sha256=validated[1],
                )
            return binding
        if event == "published":
            row = await Repo.scope_row(session, SnapshotLineageRow, values["snapshot_id"], self.scope)
            if row is None or row.table_id != values["table_id"]:
                raise denied()
            run = await Repo.scope_row(session, TransformRunRow, row.run_id, self.scope)
            await session.execute(
                update(Table)
                .where(
                    Table.id == row.table_id,
                    Table.tenant_id == self.tenant,
                    Table.workspace_id == self.workspace,
                    Table.dataset_id == self.dataset,
                )
                .values(source_file_id=run.artifact_id, sheet_or_json_path=run.sheet_or_json_path)
            )
            return await self.write(
                session,
                "step",
                {
                    "run_id": str(row.run_id),
                    "kind": "stage_completed",
                    "implementation": "structured.publish",
                    "parameters": {"stage": "publish"},
                },
            )
        if event == "publish":
            row = await Repo.scope_row(session, SnapshotLineageRow, values["snapshot_id"], self.scope)
            if row is None or row.table_id != values["table_id"]:
                raise LineageError("A snapshot cannot publish without committed immutable origin")
            run = await Repo.scope_row(session, TransformRunRow, row.run_id, self.scope)
            table = (
                await session.execute(
                    select(Table)
                    .where(
                        Table.id == row.table_id,
                        Table.tenant_id == self.tenant,
                        Table.workspace_id == self.workspace,
                        Table.dataset_id == self.dataset,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if table is None:
                raise denied()
            if (
                run.predecessor_snapshot_id is not None
                and table.current_snapshot_id != run.predecessor_snapshot_id
            ):
                raise ConflictException("Table changed during ingestion", code="CONTENT_VERSION_CONFLICT")
            return None
        raise LineageError("Unknown lineage operation")
