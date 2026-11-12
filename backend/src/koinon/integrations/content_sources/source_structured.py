# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Task-bound source authority around each native ingestion unit and lineage event."""

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager

from flyquery.core.services.ingestion.lineage import StructuredStagePhase, StructuredStageTarget
from flyquery.core.services.ingestion.readers.excel_reader import ExcelReader
from flyquery.core.services.ingestion.stages.embed import _build_embed_text
from flyquery.models.entities.schema import SchemaObject, SchemaSnapshot
from pyfly.data.transaction import current_unit_of_work, infrastructure_unit
from pyfly.data.transaction.context import current_state
from pyfly.kernel import ConflictException
from sqlalchemy import select

from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline
from koinon.knowledge.bulk.structured_repository import StructuredBulkUnit
from koinon.knowledge.lineage.entities import SnapshotLineageRow, TransformRunRow


def denied():
    return ConflictException("The source producer is no longer authorized", code="SOURCE_PUBLICATION_DENIED")


class StructuredSourceProducer:
    def __init__(self, writer, admission, execution, operation, publication, lineage, attempt_id):
        self.writer, self.admission, self.execution = writer, admission, execution
        self.operation, self.publication, self.lineage = operation, publication, lineage
        self.attempt_id = attempt_id
        self.task = asyncio.current_task()
        self.active = True
        self.registrations = []
        self.runs = {}
        self.member_sinks = {}
        self.sink = lineage.sink(
            actor=operation.actor,
            tenant_id=operation.tenant_id,
            workspace_id=operation.workspace_id,
            dataset_id=operation.dataset_id,
            operation="upload",
            authorize=self.authorize,
        )

    def check(self):
        if not self.active or self.task is not asyncio.current_task():
            raise denied()

    def close(self):
        self.active = False
        self.registrations.clear()
        self.runs.clear()
        self.member_sinks.clear()

    async def freeze(self, admission, members):
        self.check()
        if admission != self.admission:
            raise denied()
        return await self.writer.freeze_publication(admission, execution=self.execution, members=members)

    def held_admission(self):
        from koinon.integrations.content_sources.source_publication import _FENCES

        self.check()
        primary = current_unit_of_work("primary")
        if primary is None or primary.completed:
            raise denied()
        session = self.writer.intake._require_session()
        entries = list(session.info.get(_FENCES, {}).values())
        if len(entries) != 1:
            raise denied()
        entry = entries[0]
        if entry[0] is not self.writer or entry[1] != self.admission or entry[4] != self.execution:
            raise denied()
        self.writer.require_fence(entry[1])
        return entry[1]

    async def authorize(self):
        self.held_admission()
        native = current_unit_of_work("structured")
        if not self.registrations or native is None or native.completed:
            raise denied()
        session, transaction = self.registrations[-1]
        if (
            native.resource is not session
            or session.get_transaction() is not transaction
            or not transaction.is_active
        ):
            raise denied()

    @asynccontextmanager
    async def local(self):
        self.check()
        state = current_state()
        primary = [unit for unit in state.held_units("primary") if not unit.completed]
        native = [unit for unit in state.held_units("structured") if not unit.completed]
        if any(not unit.completed for unit in state.held_units("canon")):
            raise denied()
        if primary:
            self.held_admission()
            if len(primary) != 1 or len(native) > 1:
                raise denied()
            if native and native[0] is not current_unit_of_work("structured"):
                raise denied()
            async with self.native() as session:
                yield session
            return
        if native:
            raise denied()
        async with self.publication() as admission:
            if admission != self.admission:
                raise denied()
            self.held_admission()
            async with self.native() as session:
                yield session

    @asynccontextmanager
    async def native(self):
        async with infrastructure_unit(self.lineage.datasources.get("structured")) as session:
            transaction = session.get_transaction()
            if transaction is None or not transaction.is_active:
                raise denied()
            registration = (session, transaction)
            self.registrations.append(registration)
            try:
                yield session
                await self.authorize()
            finally:
                if self.registrations and self.registrations[-1] is registration:
                    self.registrations.pop()
                else:
                    self.close()

    async def plans(self, session):
        state = await StructuredBulkUnit(session).get(self.operation)
        if state is None or state.source_attempt_id != self.attempt_id:
            raise denied()
        baseline = await self.writer.intake._require_session().get(SourcePublicationBaseline, self.attempt_id)
        if baseline is None or state.source_publication_sha256 != baseline.descriptor_sha256:
            raise denied()
        if state.plan and not state.source_publication_sha256:
            raise denied()
        return state

    async def restore(self, session, state):
        predecessors = (
            {member.table_id: member.snapshot_id for member in state.baseline.members}
            if state.operation_kind == "replace" and state.baseline is not None
            else {}
        )
        for member in state.prepared:
            run = await session.get(TransformRunRow, member.lineage_run_id)
            binding = await session.get(SnapshotLineageRow, member.snapshot_id)
            if (
                run is None
                or binding is None
                or run.artifact_id != self.operation.file_id
                or (run.tenant_id, run.workspace_id, run.dataset_id, run.actor)
                != (
                    self.operation.tenant_id,
                    self.operation.workspace_id,
                    self.operation.dataset_id,
                    self.operation.actor,
                )
                or run.operation != ("replace" if member.table_id in predecessors else "upload")
                or run.predecessor_snapshot_id != predecessors.get(member.table_id)
                or binding.run_id != run.id
                or binding.table_id != member.table_id
                or (binding.tenant_id, binding.workspace_id, binding.dataset_id)
                != (run.tenant_id, run.workspace_id, run.dataset_id)
            ):
                raise denied()
            self.runs[str(run.id)] = member.table_id

    @staticmethod
    def matches_member(member, path):
        if member.member_key == "root":
            return path is None
        if not isinstance(path, str) or not member.member_key:
            return False
        try:
            kind, encoded = member.member_key.split(":", 1)
            values = json.loads(encoded)
            if kind == "json":
                return values == [path]
            if kind == "worksheet":
                sheet, header, start, _ = ExcelReader._parse_section_path(path)
                return values == [sheet] or values == [sheet, header, start]
        except (ValueError, TypeError):
            return False
        return False

    async def emit(self, event, **values):
        self.check()
        if event not in {
            "received",
            "validate_input",
            "begin_section",
            "step",
            "model_input",
            "model_output",
            "bind_snapshot",
            "publish",
            "published",
            "target_mismatch",
        }:
            raise denied()
        async with self.local() as session:
            if values.get("session", session) is not session:
                raise denied()
            for key, expected in (
                ("tenant_id", self.operation.tenant_id),
                ("workspace_id", self.operation.workspace_id),
                ("dataset_id", self.operation.dataset_id),
                ("actor", self.operation.actor),
            ):
                if key in values and str(values[key]) != str(expected):
                    raise denied()
            state = await self.plans(session)
            if state.prepared:
                await self.restore(session, state)
            member = None
            if event in {"received", "validate_input", "begin_section"}:
                if str(values.get("file_id")) != str(self.operation.file_id):
                    raise denied()
                if event == "received" and (values.get("sha256"), values.get("byte_size")) != (
                    self.operation.sha256,
                    self.operation.size_bytes,
                ):
                    raise denied()
                if event == "begin_section":
                    matching = [
                        plan
                        for plan in state.plan
                        if self.matches_member(plan, values.get("sheet_or_json_path"))
                    ]
                    if len(matching) != 1 or matching[0].table_id in self.runs.values():
                        raise denied()
                    member = matching[0]
            elif event in {"step", "model_input", "model_output"}:
                if str(values.get("run_id")) not in self.runs:
                    raise denied()
            elif event in {"bind_snapshot", "publish", "published"}:
                matching = [
                    plan
                    for plan in state.plan
                    if str(plan.table_id) == str(values.get("table_id"))
                    and str(plan.snapshot_id) == str(values.get("snapshot_id"))
                ]
                if len(matching) != 1:
                    raise denied()
                member = matching[0]
                if (
                    event == "bind_snapshot"
                    and self.runs.get(str((values.get("receipt") or {}).get("run_id"))) != member.table_id
                ):
                    raise denied()
                if event != "bind_snapshot" and member.table_id not in self.runs.values():
                    raise denied()
            sink = self.sink
            if event == "begin_section" and member is not None:
                prior = (
                    next(
                        (value for value in state.baseline.members if value.table_id == member.table_id), None
                    )
                    if state.baseline
                    else None
                )
                if prior is not None:
                    sink = self.lineage.sink(
                        actor=self.operation.actor,
                        tenant_id=self.operation.tenant_id,
                        workspace_id=self.operation.workspace_id,
                        dataset_id=self.operation.dataset_id,
                        operation="replace",
                        predecessor_snapshot_id=str(prior.snapshot_id),
                        authorize=self.authorize,
                    )
                    sink.inputs.update(self.sink.inputs)
                self.member_sinks[member.table_id] = sink
            elif member is not None:
                sink = self.member_sinks.get(member.table_id, self.sink)
            elif values.get("run_id") is not None:
                sink = self.member_sinks.get(self.runs.get(str(values["run_id"])), self.sink)
            result = await sink.emit(event, **{**values, "session": session})
            if event == "begin_section":
                if not result or member is None:
                    raise denied()
                self.runs[str(result)] = member.table_id
            return result

    async def target(self, session, phase, target):
        if type(target) is not StructuredStageTarget or target.tenant_id != self.operation.tenant_id:
            raise denied()
        state = await self.plans(session)
        previous = (
            {value.table_id: value.snapshot_id for value in state.baseline.members} if state.baseline else {}
        )
        if state.baseline is not None:
            await StructuredBulkUnit(session)._replacement_baseline(self.operation, state.baseline)
        matching = [
            plan
            for plan in state.plan
            if (
                target.snapshot_id is None
                or plan.snapshot_id == target.snapshot_id
                or phase == StructuredStagePhase.RECONCILE_READ
                and previous.get(plan.table_id) == target.snapshot_id
            )
            and (target.table_id is None or plan.table_id == target.table_id)
        ]
        if len(matching) != 1 or (
            target.snapshot_id is None
            and (phase != StructuredStagePhase.RECONCILE_READ or target.table_id is None)
        ):
            raise denied()
        plan = matching[0]
        if target.snapshot_id is not None:
            snapshot = await session.get(SchemaSnapshot, target.snapshot_id)
            if snapshot is None:
                if phase != StructuredStagePhase.RECONCILE_WRITE:
                    raise denied()
            elif (
                snapshot.tenant_id,
                snapshot.workspace_id,
                snapshot.dataset_id,
                snapshot.table_id,
                snapshot.status,
            ) != (
                self.operation.tenant_id,
                self.operation.workspace_id,
                self.operation.dataset_id,
                plan.table_id,
                "READY" if previous.get(plan.table_id) == target.snapshot_id else "PARTIAL",
            ):
                raise denied()
        if target.object_id is not None:
            row = await session.scalar(
                select(SchemaObject).where(
                    SchemaObject.id == target.object_id,
                    SchemaObject.snapshot_id == plan.snapshot_id,
                    SchemaObject.tenant_id == self.operation.tenant_id,
                    SchemaObject.workspace_id == self.operation.workspace_id,
                    SchemaObject.table_id == plan.table_id,
                    SchemaObject.is_active.is_(True),
                )
            )
            if row is None:
                raise denied()
            if target.input_sha256 is not None:
                body = _build_embed_text(
                    {
                        name: getattr(row, name)
                        for name in (
                            "qualified_name",
                            "data_type",
                            "description",
                            "synonyms_json",
                            "profile_json",
                            "sample_values_json",
                        )
                    }
                )
                if hashlib.sha256(body.encode()).hexdigest() != target.input_sha256:
                    raise denied()
        if phase == StructuredStagePhase.EMBED_WRITE and (
            target.object_id is None or target.input_sha256 is None
        ):
            raise denied()

    @asynccontextmanager
    async def unit(self, phase, target):
        self.check()
        if type(phase) is not StructuredStagePhase:
            raise denied()
        async with self.local() as session:
            await self.target(session, phase, target)
            yield

    async def before_model(self, targets):
        self.check()
        if any(
            not unit.completed
            for name in ("primary", "canon", "structured")
            for unit in current_state().held_units(name)
        ):
            raise denied()
        if not targets or len(targets) > 10001:
            raise denied()
        async with self.local() as session:
            if all(target.input_sha256 is None for target in targets):
                state = await self.plans(session)
                if len(targets) != 2 or state.baseline is None or targets[0].table_id != targets[1].table_id:
                    raise denied()
                table_id = targets[0].table_id
                old = next(
                    (value.snapshot_id for value in state.baseline.members if value.table_id == table_id),
                    None,
                )
                new = next((value.snapshot_id for value in state.plan if value.table_id == table_id), None)
                if old is None or new is None or {target.snapshot_id for target in targets} != {old, new}:
                    raise denied()
                for target in targets:
                    if target.object_id is not None:
                        raise denied()
                    await self.target(session, StructuredStagePhase.RECONCILE_READ, target)
                return
            for target in targets:
                if target.input_sha256 is None:
                    raise denied()
                await self.target(session, StructuredStagePhase.EMBED_READ, target)
