# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product operation receipts on the existing native Structured datasource."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from uuid import UUID

from flyquery.config import FlyquerySettings
from flyquery.models.entities.dataset import Dataset
from flyquery.models.entities.file import File
from flyquery.models.entities.schema import SchemaSnapshot
from flyquery.models.entities.table import Table
from pydantic import ValidationError
from pyfly.container import Provider, repository
from pyfly.data.relational.datasource_registry import DataSource
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException, ServiceUnavailableException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from koinon.knowledge.bulk.entities import now
from koinon.knowledge.bulk.ports import (
    NativeCommit,
    NativeObservation,
    NativeTableCommit,
    SourcePublicationBinding,
)
from koinon.knowledge.bulk.structured_dtos import (
    DatasetReplacementBaseline,
    PreparedStructuredTable,
    ReplacementMemberPlan,
    StructuredCommitReceipt,
    StructuredOperationIdentity,
    StructuredOperationState,
    StructuredTablePlan,
)
from koinon.knowledge.bulk.structured_entities import StructuredBulkOperation
from koinon.knowledge.lineage.entities import SnapshotLineageRow, SourceArtifactRow, TransformRunRow


def native_conflict() -> ConflictException:
    return ConflictException(
        "Native bulk operation differs from its immutable reservation", code="BULK_NATIVE_RECEIPT_CONFLICT"
    )


@dataclass(frozen=True, slots=True)
class SourceStructuredReceiptIdentity:
    """Exact retained source producer coordinates, without protected display metadata."""

    operation_id: UUID
    tenant_id: str
    workspace_id: UUID
    dataset_id: UUID
    file_id: UUID
    actor: str
    catalog_source_id: str
    catalog_dataset_id: str
    catalog_file_version_id: str
    sha256: str
    size_bytes: int
    source_attempt_id: str
    source_publication_sha256: str

    def __post_init__(self):
        if (
            any(type(value) is not UUID for value in (
                self.operation_id, self.workspace_id, self.dataset_id, self.file_id
            ))
            or any(not isinstance(value, str) or not 1 <= len(value) <= maximum for value, maximum in (
                (self.tenant_id, 512), (self.actor, 512), (self.catalog_source_id, 64),
                (self.catalog_dataset_id, 64), (self.catalog_file_version_id, 64),
                (self.source_attempt_id, 64),
            ))
            or any(not isinstance(value, str) or len(value) != 64
                   or any(character not in "0123456789abcdef" for character in value)
                   for value in (self.sha256, self.source_publication_sha256))
            or type(self.size_bytes) is not int or not 1 <= self.size_bytes <= 134217728
        ):
            raise native_conflict()


@dataclass(frozen=True, slots=True)
class StructuredReplacementAbsence:
    """Immediate native observation; never a reusable producer permission."""

    identity: StructuredOperationIdentity
    source_attempt_id: str
    source_publication_sha256: str
    baseline_sha256: str
    members: tuple[ReplacementMemberPlan, ...]
    object_key: str


def operation_identity(row: StructuredBulkOperation) -> StructuredOperationIdentity:
    values = {
        field: getattr(row, field)
        for field in StructuredOperationIdentity.model_fields
        if field != "operation_id"
    }
    try:
        return StructuredOperationIdentity(operation_id=row.id, **values)
    except ValidationError:
        raise native_conflict() from None


def state(row: StructuredBulkOperation) -> StructuredOperationState:
    try:
        replacement_plan = (
            tuple(ReplacementMemberPlan.model_validate(item) for item in row.plan_json or [])
            if row.operation_kind == "replace"
            else ()
        )
        plan = (
            [
                {field: getattr(member, field) for field in StructuredTablePlan.model_fields}
                for member in replacement_plan
                if member.action != "remove"
            ]
            if row.operation_kind == "replace"
            else row.plan_json or []
        )
        return StructuredOperationState.model_validate(
            {
                "identity": operation_identity(row),
                "status": row.status,
                "operation_kind": row.operation_kind,
                "baseline": row.baseline_json,
                "baseline_sha256": row.baseline_sha256,
                "plan": plan,
                "replacement_plan": replacement_plan,
                "prepared": row.prepared_json or [],
                "receipt": row.receipt_json,
                "source_attempt_id": row.source_attempt_id,
                "source_publication_sha256": row.source_publication_sha256,
            }
        )
    except ValidationError:
        raise native_conflict() from None


class StructuredBulkUnit:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def _row(
        self, identity: StructuredOperationIdentity, *, lock: bool = False
    ) -> StructuredBulkOperation | None:
        statement = select(StructuredBulkOperation).where(
            StructuredBulkOperation.id == identity.operation_id,
            StructuredBulkOperation.tenant_id == identity.tenant_id,
            StructuredBulkOperation.workspace_id == identity.workspace_id,
            StructuredBulkOperation.dataset_id == identity.dataset_id,
            StructuredBulkOperation.file_id == identity.file_id,
            StructuredBulkOperation.actor == identity.actor,
        )
        if lock:
            statement = statement.with_for_update()
        row = await self._session.scalar(statement.execution_options(populate_existing=True))
        if row is not None and operation_identity(row) != identity:
            raise native_conflict()
        return row

    async def get(self, identity: StructuredOperationIdentity) -> StructuredOperationState | None:
        row = await self._row(identity)
        return state(row) if row is not None else None

    async def replacement_absence(
        self,
        expected: StructuredOperationState,
        object_key: str,
    ) -> StructuredReplacementAbsence | None:
        """Inspect only an exact retained admission with no downstream native effects."""
        identity = expected.identity
        row = await self._row(identity, lock=True)
        if row is None or state(row) != expected:
            raise native_conflict()
        if (
            expected.operation_kind != "replace"
            or expected.status != "admitted"
            or expected.baseline is None
            or not expected.baseline_sha256
            or not expected.source_attempt_id
            or not expected.source_publication_sha256
            or not expected.replacement_plan
            or row.prepared_json is not None
            or row.receipt_json is not None
        ):
            return None
        await self._replacement_baseline(identity, expected.baseline, lock=True)
        live = tuple(member for member in expected.replacement_plan if member.action != "remove")
        snapshots = tuple(member.snapshot_id for member in live)
        added = tuple(member.table_id for member in live if member.action == "add")
        effects = (
            select(File.id).where(File.id == identity.file_id),
            select(SourceArtifactRow.id).where(SourceArtifactRow.id == identity.file_id),
            select(TransformRunRow.id).where(TransformRunRow.artifact_id == identity.file_id),
            select(SchemaSnapshot.id).where(SchemaSnapshot.id.in_(snapshots)),
            select(SnapshotLineageRow.snapshot_id).where(SnapshotLineageRow.snapshot_id.in_(snapshots)),
            select(Table.id).where(or_(Table.source_file_id == identity.file_id, Table.id.in_(added))),
        )
        for query in effects:
            if await self._session.scalar(query.limit(1)) is not None:
                return None
        return StructuredReplacementAbsence(
            identity, expected.source_attempt_id, expected.source_publication_sha256,
            expected.baseline_sha256, expected.replacement_plan, object_key,
        )

    async def inspect_receipt(self, identity: StructuredOperationIdentity) -> NativeObservation:
        """Project bounded immutable receipt fields without loading names or plans."""
        return await self._inspect_receipt(identity, identity.model_dump(mode="python"))

    async def inspect_source_receipt(self, identity: SourceStructuredReceiptIdentity) -> NativeObservation:
        """Inspect the exact source receipt without requiring a filename or a reusable read grant."""
        if type(identity) is not SourceStructuredReceiptIdentity:
            raise native_conflict()
        return await self._inspect_receipt(identity, asdict(identity))

    async def _inspect_receipt(
        self, identity: StructuredOperationIdentity | SourceStructuredReceiptIdentity, exact_values: dict
    ) -> NativeObservation:
        row = StructuredBulkOperation
        receipt = row.receipt_json
        scope = (
            row.id == identity.operation_id,
            row.tenant_id == identity.tenant_id,
            row.workspace_id == identity.workspace_id,
            row.actor == identity.actor,
        )
        exact = tuple(
            getattr(row, "id" if name == "operation_id" else name) == value
            for name, value in exact_values.items()
        )
        fields = [row.status, func.json_array_length(receipt["tables"]).label("table_count")]
        for name in (
            "file_id",
            "dataset_id",
            "sha256",
            "object_key",
            "source_attempt_id",
            "source_publication_sha256",
        ):
            fields.append(receipt[name].as_string().label(name))
        fields.extend(
            (
                row.source_attempt_id.label("expected_attempt"),
                row.source_publication_sha256.label("expected_digest"),
            )
        )
        fields.append(receipt["size_bytes"].as_integer().label("size_bytes"))
        for index in range(16):
            table = receipt["tables"][index]
            for name in ("catalog_table_id", "table_id", "snapshot_id"):
                fields.append(table[name].as_string().label(f"t{index}_{name}"))
            for name in ("ordinal", "n_columns", "n_rows_actual"):
                fields.append(table[name].as_integer().label(f"t{index}_{name}"))
        found = (await self._session.execute(select(*fields).where(*scope, *exact))).mappings().first()
        if found is None:
            if await self._session.scalar(select(row.id).where(*scope)) is not None:
                raise native_conflict()
            return NativeObservation("absent")
        if found["status"] in {"admitted", "prepared"}:
            return NativeObservation(found["status"])
        try:
            if (
                found["status"] != "committed"
                or type(found["table_count"]) is not int
                or not 1 <= found["table_count"] <= 16
                or UUID(found["file_id"]) != identity.file_id
                or UUID(found["dataset_id"]) != identity.dataset_id
                or found["sha256"] != identity.sha256
                or found["size_bytes"] != identity.size_bytes
                or not isinstance(found["object_key"], str)
                or not 1 <= len(found["object_key"]) <= 2048
                or found["source_attempt_id"] != found["expected_attempt"]
                or found["source_publication_sha256"] != found["expected_digest"]
                or (found["source_attempt_id"] is None) != (found["source_publication_sha256"] is None)
            ):
                raise ValueError
            tables = []
            for index in range(found["table_count"]):
                prefix = f"t{index}_"
                catalog_id = found[prefix + "catalog_table_id"]
                columns, rows = found[prefix + "n_columns"], found[prefix + "n_rows_actual"]
                if (
                    found[prefix + "ordinal"] != index
                    or not isinstance(catalog_id, str)
                    or not 1 <= len(catalog_id) <= 64
                    or type(columns) is not int
                    or not 1 <= columns <= 10000
                    or type(rows) is not int
                    or rows < 0
                ):
                    raise ValueError
                tables.append(
                    NativeTableCommit(
                        catalog_id,
                        str(UUID(found[prefix + "table_id"])),
                        str(UUID(found[prefix + "snapshot_id"])),
                        columns,
                        rows,
                    )
                )
            if len({table.table_id for table in tables}) != len(tables):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise native_conflict() from None
        return NativeObservation(
            "committed",
            NativeCommit(
                domain="structured",
                native_workspace_id=str(identity.workspace_id),
                native_source_id=str(identity.dataset_id),
                native_asset_id=str(identity.dataset_id),
                sha256=identity.sha256,
                size_bytes=identity.size_bytes,
                object_key=found["object_key"],
                file_version_id=identity.catalog_file_version_id,
                native_file_id=str(identity.file_id),
                tables=tuple(tables),
                source_attempt_id=found["source_attempt_id"],
                source_publication_sha256=found["source_publication_sha256"],
            ),
        )

    async def admit(
        self, identity: StructuredOperationIdentity, *, source_attempt_id: str | None = None
    ) -> StructuredOperationState:
        if source_attempt_id is not None and (
            not isinstance(source_attempt_id, str) or not 1 <= len(source_attempt_id) <= 64
        ):
            raise native_conflict()
        previous = await self._row(identity, lock=True)
        if previous is not None:
            if previous.source_attempt_id != source_attempt_id:
                raise native_conflict()
            return state(previous)
        clock = now()
        self._session.add(
            Dataset(
                id=identity.dataset_id,
                tenant_id=identity.tenant_id,
                workspace_id=identity.workspace_id,
                name="bulk-" + str(identity.operation_id),
                description=None,
                drift_policy="AUTO",
                default_locale=None,
                ingest_policy_json={},
                status="ACTIVE",
                created_at=clock,
                updated_at=clock,
                metadata_json={
                    "catalog_source_id": identity.catalog_source_id,
                    "bulk_operation_id": str(identity.operation_id),
                },
            )
        )
        await self._session.flush()
        values = identity.model_dump(mode="python")
        values["id"] = values.pop("operation_id")
        row = StructuredBulkOperation(
            **values, status="admitted", created_at=clock, source_attempt_id=source_attempt_id
        )
        self._session.add(row)
        await self._session.flush()
        return state(row)

    async def _replacement_baseline(
        self, identity: StructuredOperationIdentity, baseline: DatasetReplacementBaseline, *, lock=False
    ) -> None:
        if (
            baseline.dataset_id != identity.dataset_id
            or baseline.catalog_dataset_id != identity.catalog_dataset_id
            or baseline.native_file_id == identity.file_id
            or baseline.catalog_file_version_id == identity.catalog_file_version_id
        ):
            raise native_conflict()
        dataset_query = select(Dataset).where(
            Dataset.id == identity.dataset_id,
            Dataset.tenant_id == identity.tenant_id,
            Dataset.workspace_id == identity.workspace_id,
        )
        file_query = select(File).where(
            File.id == baseline.native_file_id,
            File.tenant_id == identity.tenant_id,
            File.workspace_id == identity.workspace_id,
            File.dataset_id == identity.dataset_id,
        )
        members_query = (
            select(Table, SchemaSnapshot)
            .join(SchemaSnapshot, SchemaSnapshot.id == Table.current_snapshot_id)
            .where(
                Table.tenant_id == identity.tenant_id,
                Table.workspace_id == identity.workspace_id,
                Table.dataset_id == identity.dataset_id,
                Table.source_file_id == baseline.native_file_id,
                Table.is_active.is_(True),
            )
            .order_by(Table.id)
        )
        if lock:
            dataset_query = dataset_query.with_for_update()
            file_query = file_query.with_for_update()
            members_query = members_query.with_for_update()
        dataset = await self._session.scalar(dataset_query.execution_options(populate_existing=True))
        file = await self._session.scalar(file_query.execution_options(populate_existing=True))
        if (
            dataset is None
            or dataset.status != "ACTIVE"
            or dataset.metadata_json.get("catalog_source_id") != identity.catalog_source_id
            or file is None
            or file.status != "PARSED"
            or file.content_hash_sha256 != baseline.sha256
        ):
            raise native_conflict()
        members = (await self._session.execute(members_query.execution_options(populate_existing=True))).all()
        expected = {member.table_id: member for member in baseline.members}
        active_count = await self._session.scalar(
            select(func.count())
            .select_from(Table)
            .where(
                Table.tenant_id == identity.tenant_id,
                Table.workspace_id == identity.workspace_id,
                Table.dataset_id == identity.dataset_id,
                Table.source_file_id == baseline.native_file_id,
                Table.is_active.is_(True),
            )
        )
        if len(members) != len(expected) or active_count != len(expected):
            raise native_conflict()
        for table, snapshot in members:
            member = expected.get(table.id)
            if (
                member is None
                or table.archived_at is not None
                or table.current_snapshot_id != member.snapshot_id
                or (snapshot.tenant_id, snapshot.workspace_id, snapshot.dataset_id, snapshot.table_id)
                != (identity.tenant_id, identity.workspace_id, identity.dataset_id, table.id)
                or snapshot.status != "READY"
            ):
                raise native_conflict()

    async def admit_replacement(
        self,
        identity: StructuredOperationIdentity,
        *,
        source_attempt_id: str,
        baseline: DatasetReplacementBaseline,
        baseline_sha256: str,
    ) -> StructuredOperationState:
        """Admit a new original against the entire still-current previous file."""
        try:
            baseline = DatasetReplacementBaseline.model_validate(baseline.model_dump(by_alias=True))
        except (AttributeError, ValidationError):
            raise native_conflict() from None
        if (
            not isinstance(source_attempt_id, str)
            or not 1 <= len(source_attempt_id) <= 64
            or source_attempt_id == baseline.source_attempt_id
            or not isinstance(baseline_sha256, str)
            or len(baseline_sha256) != 64
            or any(value not in "0123456789abcdef" for value in baseline_sha256)
        ):
            raise native_conflict()
        payload = baseline.model_dump(mode="json", by_alias=True)
        previous = await self._row(identity, lock=True)
        if previous is not None:
            if (
                previous.operation_kind != "replace"
                or previous.source_attempt_id != source_attempt_id
                or previous.baseline_json != payload
                or previous.baseline_sha256 != baseline_sha256
            ):
                raise native_conflict()
            return state(previous)
        await self._replacement_baseline(identity, baseline, lock=True)
        values = identity.model_dump(mode="python")
        values["id"] = values.pop("operation_id")
        row = StructuredBulkOperation(
            **values,
            operation_kind="replace",
            baseline_json=payload,
            baseline_sha256=baseline_sha256,
            source_attempt_id=source_attempt_id,
            status="admitted",
            created_at=now(),
        )
        self._session.add(row)
        await self._session.flush()
        return state(row)

    async def bind_publication(
        self, identity: StructuredOperationIdentity, binding: SourcePublicationBinding
    ) -> StructuredOperationState:
        row = await self._row(identity, lock=True)
        if (
            type(binding) is not SourcePublicationBinding
            or row is None
            or row.source_attempt_id != binding.attempt_id
            or row.plan_json is None
            or len(binding.descriptor_sha256) != 64
            or any(c not in "0123456789abcdef" for c in binding.descriptor_sha256)
        ):
            raise native_conflict()
        if row.source_publication_sha256 is not None:
            if row.source_publication_sha256 != binding.descriptor_sha256:
                raise native_conflict()
            return state(row)
        if row.status != "admitted":
            raise native_conflict()
        row.source_publication_sha256 = binding.descriptor_sha256
        await self._session.flush()
        return state(row)

    async def plan(
        self, identity: StructuredOperationIdentity, tables: tuple[StructuredTablePlan, ...]
    ) -> StructuredOperationState:
        if (
            not 1 <= len(tables) <= 16
            or tuple(t.ordinal for t in tables) != tuple(range(len(tables)))
            or len({t.table_id for t in tables}) != len(tables)
            or len({t.snapshot_id for t in tables}) != len(tables)
            or len({t.name for t in tables}) != len(tables)
            or any(t.catalog_table_id is None for t in tables)
            or len({t.catalog_table_id for t in tables}) != len(tables)
        ):
            raise native_conflict()
        row = await self._row(identity, lock=True)
        if row is None:
            raise native_conflict()
        payload = [table.model_dump(mode="json", by_alias=True) for table in tables]
        if row.plan_json is not None and row.plan_json != payload:
            raise native_conflict()
        if row.plan_json is None:
            if row.status != "admitted":
                raise native_conflict()
            row.plan_json = payload
            await self._session.flush()
        return state(row)

    async def plan_replacement(
        self, identity: StructuredOperationIdentity, members: tuple[ReplacementMemberPlan, ...]
    ) -> StructuredOperationState:
        try:
            members = tuple(
                ReplacementMemberPlan.model_validate(member.model_dump(by_alias=True)) for member in members
            )
        except (AttributeError, ValidationError):
            raise native_conflict() from None
        live = tuple(member for member in members if member.action != "remove")
        removed = tuple(member for member in members if member.action == "remove")
        if (
            not 1 <= len(members) <= 32
            or not 1 <= len(live) <= 16
            or tuple(member.ordinal for member in live) != tuple(range(len(live)))
            or len({member.name for member in live}) != len(live)
            or len({member.member_key for member in live}) != len(live)
            or len({member.member_key for member in removed}) != len(removed)
            or any(
                len({getattr(member, field) for member in members}) != len(members)
                for field in ("table_id", "catalog_table_id", "snapshot_id")
            )
        ):
            raise native_conflict()
        row = await self._row(identity, lock=True)
        if row is None or row.operation_kind != "replace":
            raise native_conflict()
        current = state(row)
        baseline = current.baseline
        if baseline is None:
            raise native_conflict()
        payload = [member.model_dump(mode="json", by_alias=True) for member in members]
        if row.plan_json is not None:
            if row.plan_json != payload:
                raise native_conflict()
            return current
        old = {member.table_id: member for member in baseline.members}
        if {member.table_id for member in members if member.action != "add"} != set(old):
            raise native_conflict()
        for member in members:
            prior = old.get(member.table_id)
            if member.action == "add":
                if prior is not None or await self._session.get(Table, member.table_id) is not None:
                    raise native_conflict()
            elif (
                prior is None
                or prior.catalog_table_id != member.catalog_table_id
                or member.action == "retain"
                and prior.snapshot_id == member.snapshot_id
                or member.action == "remove"
                and (prior.snapshot_id != member.snapshot_id or prior.member_key != member.member_key)
            ):
                raise native_conflict()
        if row.status != "admitted":
            raise native_conflict()
        await self._replacement_baseline(identity, baseline, lock=True)
        row.plan_json = payload
        await self._session.flush()
        return state(row)

    async def _file(self, identity: StructuredOperationIdentity, *, lock: bool = False) -> File:
        operation = await self._row(identity)
        if operation is None:
            raise native_conflict()
        dataset_query = select(Dataset).where(
            Dataset.id == identity.dataset_id,
            Dataset.tenant_id == identity.tenant_id,
            Dataset.workspace_id == identity.workspace_id,
        )
        file_query = select(File).where(
            File.id == identity.file_id,
            File.tenant_id == identity.tenant_id,
            File.workspace_id == identity.workspace_id,
            File.dataset_id == identity.dataset_id,
        )
        if lock:
            dataset_query = dataset_query.with_for_update()
            file_query = file_query.with_for_update()
        dataset = await self._session.scalar(dataset_query.execution_options(populate_existing=True))
        if (
            dataset is None
            or dataset.status != "ACTIVE"
            or operation.operation_kind == "initial"
            and dataset.metadata_json.get("bulk_operation_id") != str(identity.operation_id)
            or dataset.metadata_json.get("catalog_source_id") != identity.catalog_source_id
        ):
            raise native_conflict()
        row = await self._session.scalar(file_query.execution_options(populate_existing=True))
        if (
            row is None
            or row.original_filename != identity.filename
            or row.size_bytes != identity.size_bytes
            or row.content_hash_sha256 != identity.sha256
            or row.uploaded_by != identity.actor
            or row.status not in {"RECEIVED", "PARSED"}
        ):
            raise native_conflict()
        artifact = await self._session.scalar(
            select(SourceArtifactRow).where(
                SourceArtifactRow.id == identity.file_id,
                SourceArtifactRow.tenant_id == identity.tenant_id,
                SourceArtifactRow.workspace_id == identity.workspace_id,
                SourceArtifactRow.dataset_id == identity.dataset_id,
            )
        )
        if (
            artifact is None
            or artifact.actor != identity.actor
            or artifact.sha256 != identity.sha256
            or artifact.byte_size != identity.size_bytes
            or artifact.original_filename != identity.filename
        ):
            raise native_conflict()
        return row

    async def materialize_table(self, identity, plan, parsed) -> None:
        row = await self._row(identity, lock=True)
        if (
            row is None
            or row.status != "admitted"
            or row.source_attempt_id is None
            or row.source_publication_sha256 is None
            or plan not in state(row).plan
            or parsed.table_id != plan.table_id
            or parsed.name != plan.name
        ):
            raise native_conflict()
        await self._file(identity)
        current = state(row)
        replacing = current.operation_kind == "replace"
        old_ids = set()
        if replacing:
            if current.baseline is None:
                raise native_conflict()
            await self._replacement_baseline(identity, current.baseline, lock=True)
            old_ids = {member.table_id for member in current.baseline.members}
            member = next(
                (value for value in current.replacement_plan if value.table_id == plan.table_id), None
            )
            if member is None or member.action == "remove":
                raise native_conflict()
            if member.action == "retain":
                # The new snapshot is staged against this stable identity. Its live
                # name, original and current head change only in final publication.
                return
        existing = await self._session.scalar(
            select(Table.id)
            .where(
                (Table.id == plan.table_id)
                | (
                    (Table.dataset_id == identity.dataset_id)
                    & (Table.name == plan.name)
                    & Table.is_active.is_(True)
                    & Table.id.not_in(old_ids)
                )
            )
            .limit(1)
        )
        if existing is not None:
            raise native_conflict()
        self._session.add(
            Table(
                id=plan.table_id,
                tenant_id=identity.tenant_id,
                workspace_id=identity.workspace_id,
                dataset_id=identity.dataset_id,
                source_file_id=identity.file_id,
                name=plan.name,
                qualified_name=parsed.qualified_name,
                sheet_or_json_path=parsed.sheet_or_json_path,
                kind="UPLOADED",
                is_active=not replacing,
            )
        )
        await self._session.flush()

    async def _table(
        self,
        identity: StructuredOperationIdentity,
        prepared: PreparedStructuredTable,
        *,
        ready: bool,
        lock: bool = False,
    ) -> None:
        operation = await self._row(identity)
        if operation is None:
            raise native_conflict()
        current = state(operation)
        prior = (
            next(
                (member for member in current.baseline.members if member.table_id == prepared.table_id), None
            )
            if current.baseline
            else None
        )
        replacing = current.operation_kind == "replace"
        table_query = select(Table).where(
            Table.id == prepared.table_id,
            Table.tenant_id == identity.tenant_id,
            Table.workspace_id == identity.workspace_id,
            Table.dataset_id == identity.dataset_id,
        )
        snapshot_query = select(SchemaSnapshot).where(
            SchemaSnapshot.id == prepared.snapshot_id,
            SchemaSnapshot.tenant_id == identity.tenant_id,
            SchemaSnapshot.workspace_id == identity.workspace_id,
            SchemaSnapshot.dataset_id == identity.dataset_id,
            SchemaSnapshot.table_id == prepared.table_id,
        )
        if lock:
            table_query = table_query.with_for_update()
            snapshot_query = snapshot_query.with_for_update()
        table = await self._session.scalar(table_query.execution_options(populate_existing=True))
        snapshot = await self._session.scalar(snapshot_query.execution_options(populate_existing=True))
        if (
            table is None
            or snapshot is None
            or table.source_file_id != (prior.source_file_id if prior and not ready else identity.file_id)
            or (ready or prior is None)
            and table.name != prepared.name
            or (ready or prior is None)
            and prepared.qualified_name is not None
            and (table.qualified_name, table.sheet_or_json_path)
            != (prepared.qualified_name, prepared.sheet_or_json_path)
            or table.is_active != (ready or not replacing or prior is not None)
            or table.archived_at is not None
            or table.current_snapshot_id
            != (prepared.snapshot_id if ready else prior.snapshot_id if prior else None)
            or snapshot.status != ("READY" if ready else "PARTIAL")
            or snapshot.parquet_object_key != prepared.parquet_key
            or snapshot.parquet_byte_size != prepared.parquet_byte_size
            or snapshot.n_columns != prepared.n_columns
            or snapshot.n_rows_actual != prepared.n_rows_actual
            or snapshot.snapshot_hash != prepared.schema_sha256
        ):
            raise native_conflict()
        lineage = await self._session.scalar(
            select(SnapshotLineageRow).where(
                SnapshotLineageRow.snapshot_id == prepared.snapshot_id,
                SnapshotLineageRow.table_id == prepared.table_id,
                SnapshotLineageRow.tenant_id == identity.tenant_id,
                SnapshotLineageRow.workspace_id == identity.workspace_id,
                SnapshotLineageRow.dataset_id == identity.dataset_id,
            )
        )
        if (
            lineage is None
            or lineage.run_id != prepared.lineage_run_id
            or lineage.parquet_sha256 != prepared.parquet_sha256
            or lineage.parquet_byte_size != prepared.parquet_byte_size
            or lineage.schema_sha256 != prepared.schema_sha256
            or lineage.row_count != prepared.n_rows_actual
        ):
            raise native_conflict()
        run = await self._session.scalar(
            select(TransformRunRow).where(
                TransformRunRow.id == prepared.lineage_run_id,
                TransformRunRow.tenant_id == identity.tenant_id,
                TransformRunRow.workspace_id == identity.workspace_id,
                TransformRunRow.dataset_id == identity.dataset_id,
            )
        )
        if (
            run is None
            or run.actor != identity.actor
            or run.artifact_id != identity.file_id
            or run.operation != ("replace" if prior else "upload")
            or run.predecessor_snapshot_id != (prior.snapshot_id if prior else None)
        ):
            raise native_conflict()

    async def prepared(
        self, identity: StructuredOperationIdentity, tables: tuple[PreparedStructuredTable, ...]
    ) -> StructuredOperationState:
        row = await self._row(identity, lock=True)
        if row is None or row.plan_json is None or not 1 <= len(tables) <= 16:
            raise native_conflict()
        current = state(row)
        predecessors = (
            {member.table_id: member.snapshot_id for member in current.baseline.members}
            if current.baseline
            else {}
        )
        for table in tables:
            changes = table.reconcile_changes
            if (
                current.operation_kind == "replace"
                and table.qualified_name is None
                or (table.table_id in predecessors) != (changes is not None)
                or changes is not None
                and (
                    row.operation_kind != "replace"
                    or changes.tenant_id != identity.tenant_id
                    or changes.workspace_id != identity.workspace_id
                    or changes.table_id != table.table_id
                    or changes.next_snapshot_id != table.snapshot_id
                    or changes.previous_snapshot_id != predecessors.get(table.table_id)
                )
            ):
                raise native_conflict()
        payload = [table.model_dump(mode="json", by_alias=True) for table in tables]
        expected = [
            StructuredTablePlan.model_validate(
                {field: getattr(table, field) for field in StructuredTablePlan.model_fields}
            ).model_dump(mode="json")
            for table in tables
        ]
        if expected != [member.model_dump(mode="json") for member in current.plan]:
            raise native_conflict()
        if row.prepared_json is not None:
            if row.prepared_json != payload:
                raise native_conflict()
            return state(row)
        if row.status != "admitted":
            raise native_conflict()
        if row.source_attempt_id is not None and row.source_publication_sha256 is None:
            raise native_conflict()
        if current.baseline is not None:
            await self._replacement_baseline(identity, current.baseline, lock=True)
        await self._file(identity)
        for table in tables:
            await self._table(identity, table, ready=False)
        row.prepared_json = payload
        row.status = "prepared"
        await self._session.flush()
        return state(row)

    async def publication(self, identity: StructuredOperationIdentity) -> StructuredOperationState:
        row = await self._row(identity, lock=True)
        if row is None:
            raise native_conflict()
        if row.status == "committed":
            return state(row)
        if row.status != "prepared" or not row.prepared_json:
            raise native_conflict()
        current = state(row)
        tables = current.prepared
        if current.baseline is not None:
            await self._replacement_baseline(identity, current.baseline, lock=True)
        await self._file(identity, lock=True)
        for table in sorted(tables, key=lambda value: str(value.table_id)):
            await self._table(identity, table, ready=False, lock=True)
        return state(row)

    async def activate_replacement(self, identity: StructuredOperationIdentity) -> None:
        """Switch the whole reviewed member set inside the final native transaction."""
        current = await self.publication(identity)
        if current.operation_kind != "replace" or current.status != "prepared" or current.baseline is None:
            raise native_conflict()
        if any(table.qualified_name is None for table in current.prepared):
            raise native_conflict()
        previous = {member.table_id for member in current.baseline.members}
        live = {member.table_id for member in current.prepared}
        identifiers = previous | live
        rows = list(
            (
                await self._session.scalars(
                    select(Table)
                    .where(
                        Table.tenant_id == identity.tenant_id,
                        Table.workspace_id == identity.workspace_id,
                        Table.dataset_id == identity.dataset_id,
                        Table.id.in_(sorted(identifiers, key=str)),
                    )
                    .order_by(Table.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        if {row.id for row in rows} != identifiers:
            raise native_conflict()
        indexed = {row.id: row for row in rows}
        retired_at = now()
        for identifier in previous:
            indexed[identifier].is_active = False
            if identifier not in live:
                indexed[identifier].archived_at = retired_at
        # Flush deactivation before names change: the live-name unique index is
        # immediate. Readers cannot observe this intermediate transaction state.
        await self._session.flush()
        for prepared in current.prepared:
            if prepared.qualified_name is None:
                raise native_conflict()
            table = indexed[prepared.table_id]
            table.source_file_id = identity.file_id
            table.name, table.qualified_name = prepared.name, prepared.qualified_name
            table.sheet_or_json_path = prepared.sheet_or_json_path
            table.is_active, table.archived_at = True, None
        await self._session.flush()

    async def commit(self, identity: StructuredOperationIdentity) -> StructuredOperationState:
        row = await self._row(identity, lock=True)
        if row is None:
            raise native_conflict()
        if row.status == "committed":
            return state(row)
        if row.status != "prepared" or not row.prepared_json:
            raise native_conflict()
        current = state(row)
        tables = current.prepared
        file = await self._file(identity)
        for table in tables:
            await self._table(identity, table, ready=True)
        if current.baseline is not None:
            prior = {member.table_id: member for member in current.baseline.members}
            for removed in current.replacement_plan:
                if removed.action != "remove":
                    continue
                table = await self._session.get(Table, removed.table_id)
                if (
                    table is None
                    or table.is_active
                    or table.archived_at is None
                    or table.current_snapshot_id != prior[removed.table_id].snapshot_id
                    or table.source_file_id != prior[removed.table_id].source_file_id
                ):
                    raise native_conflict()
        receipt = StructuredCommitReceipt(
            file_id=identity.file_id,
            dataset_id=identity.dataset_id,
            sha256=identity.sha256,
            size_bytes=identity.size_bytes,
            object_key=file.object_store_key,
            tables=tables,
            source_attempt_id=row.source_attempt_id,
            source_publication_sha256=row.source_publication_sha256,
        )
        row.receipt_json = receipt.model_dump(mode="json", by_alias=True)
        row.status = "committed"
        file.status = "PARSED"
        await self._session.flush()
        return state(row)


@repository(name="knowledge.bulk.structured_repository")
class StructuredBulkRepository:
    def __init__(self, settings: Provider[FlyquerySettings | None]):
        self.settings = settings

    def configuration(self) -> FlyquerySettings:
        settings = self.settings.get()
        if settings is None:
            raise ServiceUnavailableException(
                "Native structured resources are unavailable", code="BULK_NATIVE_REQUIRED"
            )
        return settings

    def native(self) -> DataSource:
        return self.configuration().native_datasource()

    def _native(self) -> DataSource:
        return self.native()

    @asynccontextmanager
    async def read(self) -> AsyncIterator[StructuredBulkUnit]:
        async with infrastructure_unit(self._native(), read_only=True) as session:
            yield StructuredBulkUnit(session)

    @asynccontextmanager
    async def write(self) -> AsyncIterator[StructuredBulkUnit]:
        async with infrastructure_unit(self._native()) as session:
            yield StructuredBulkUnit(session)
