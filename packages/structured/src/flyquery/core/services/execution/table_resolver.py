# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""TableResolver — map AST table names to their current parquet snapshot paths.

Given a dataset_id and a list of unqualified table names (as reported by
``AstClassifier``), looks up active registered tables and their current
schema snapshots, and returns a ``{name: snapshot_path}`` dict. This dict is passed
directly to ``DuckDBExecutor.execute`` as ``attached_tables``.

Path construction
-----------------
* ``object_store_base`` is the root of the blob store (e.g. ``/var/lib/flyquery/blobs``
  for LocalFs or ``s3://my-bucket/flyquery`` for S3).
* ``parquet_object_key`` is the relative path stored in ``flyquery_schema_snapshots``
  (e.g. ``flyquery/ten-a/ws-id/ds-id/tables/table-id/v3.parquet``).
* The constructed path is ``{object_store_base}/{parquet_object_key}``.
  This resolver performs metadata lookup and string construction only; it
  does not download snapshots, stage local files, or load DuckDB extensions.

The qualified executor workflow uses registered local Parquet paths with
external access and extension autoload/install disabled. ``duckdb_httpfs``
does not enable remote reads in that executor. A remote object-store URI
would need a separately implemented, owned local-snapshot staging step;
this resolver does not provide one. See ``docs/security-model.md`` under
"SQL read boundary" for the execution policy and qualification limits.
"""

from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy.ext.asyncio import AsyncSession

from flyquery.core.services.query import provenance


class TableResolver:
    """Resolves table names to parquet paths via the current schema snapshot.

    :param session: async SQLAlchemy session (request-scoped)
    :param settings: :class:`FlyquerySettings` — reads ``object_store_base``
    """

    def __init__(self, session: AsyncSession, settings) -> None:
        self._session = session
        self._settings = settings

    async def resolve(
        self,
        dataset_id: uuid.UUID,
        table_names: list[str],
        object_store_base: str | None = None,
        pins: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Return a mapping of table name → constructed snapshot path.

        Tables that are active and have a current snapshot are included.
        Tables that are not found (not active, no snapshot, wrong dataset)
        are silently omitted so the caller can decide how to handle missing
        tables (unregistered references are rejected by admission/executor checks).

        :param dataset_id: dataset to scope the lookup
        :param table_names: unqualified table names from the AST
        :param object_store_base: override for ``settings.object_store_base``
        :param pins: optional ``{table_name: snapshot_id}`` — a follow-up
            drill-down turn pins each table to the snapshot it resolved to
            on the first turn, so a mid-conversation re-ingest does not
            silently switch the answer to a newer schema. Unpinned tables
            fall back to ``current_snapshot_id``.
        :return: ``{name: path}`` dict for all resolvable tables
        """
        if not table_names:
            return {}

        from flyquery.core.services.storage.object_store_factory import storage_base

        base = (object_store_base or storage_base(self._settings)).rstrip("/")

        rows = await self._session.execute(
            sa.text("""
                SELECT t.name, ss.parquet_object_key, ss.id AS snapshot_id, t.id AS table_id
                FROM flyquery_tables t
                JOIN flyquery_schema_snapshots ss
                    ON ss.table_id = t.id
                   AND ss.id = COALESCE(
                           (CAST(:pins AS jsonb) ->> t.name)::uuid,
                           t.current_snapshot_id
                       )
                WHERE t.dataset_id = :ds
                  AND t.name = ANY(:names)
                  AND t.is_active = true
            """),
            {"ds": dataset_id, "names": list(table_names), "pins": json.dumps(pins or {})},
        )

        observed = list(rows.mappings())
        provenance.resolved(dataset_id, observed)
        out: dict[str, str] = {}
        for r in observed:
            key: str = r["parquet_object_key"]
            out[r["name"]] = f"{base}/{key}"
        return out

    async def table_kinds_by_name(self, dataset_id: uuid.UUID, table_names: list[str]) -> dict[str, str]:
        """Return ``{name: kind}`` for the active tables in the dataset.

        Used by the firewall/bad-tables guard. Lives here (service layer)
        rather than in a controller so the raw SQL stays out of the web tier.
        """
        if not table_names:
            return {}
        rows = await self._session.execute(
            sa.text("""
                SELECT name, kind FROM flyquery_tables
                WHERE dataset_id = :ds AND name = ANY(:names) AND is_active = true
            """),
            {"ds": dataset_id, "names": list(table_names)},
        )
        return {r["name"]: r["kind"] for r in rows.mappings()}

    async def current_snapshots(self, dataset_id: uuid.UUID, table_names: list[str]) -> dict[str, str]:
        """Return ``{table_name: current_snapshot_id}`` for the given tables.

        Used to record THIS turn's snapshot pins so a later drill-down turn
        can reproduce the exact schema version it answered against.
        """
        if not table_names:
            return {}
        rows = await self._session.execute(
            sa.text("""
                SELECT name, current_snapshot_id
                FROM flyquery_tables
                WHERE dataset_id = :ds AND name = ANY(:names) AND is_active = true
                  AND current_snapshot_id IS NOT NULL
            """),
            {"ds": dataset_id, "names": list(table_names)},
        )
        return {r["name"]: str(r["current_snapshot_id"]) for r in rows.mappings()}


class ProductTableResolver:
    """Resolve exact snapshot paths only after detached identity admission."""

    def __init__(self, sessions, settings):
        self._sessions, self._settings = sessions, settings
        self._pins = {}

    def bind_snapshot_pins(self, pins):
        self._pins = dict(pins)

    async def _read(self, statement, parameters):
        async with infrastructure_unit(self._sessions, read_only=True) as session:
            result = await session.execute(sa.text(statement), parameters)
            return [dict(row) for row in result.mappings()]

    async def _tables(self, dataset_id, table_names, pins=None):
        pins = self._pins if pins is None else pins
        if not table_names:
            return []
        if len(table_names) > 500:
            raise ServiceUnavailableException("Too many query tables", code="EVIDENCE_UNAVAILABLE")
        identities = await self._read(
            """SELECT t.id AS table_id,ss.id AS snapshot_id
            FROM flyquery_tables t JOIN flyquery_schema_snapshots ss ON ss.table_id=t.id
              AND ss.id=COALESCE((CAST(:pins AS jsonb)->>t.name)::uuid,t.current_snapshot_id)
            WHERE t.dataset_id=:ds AND t.name=ANY(:names) AND t.is_active=true AND ss.status='READY'""",
            {"ds": dataset_id, "names": table_names, "pins": json.dumps(pins or {})},
        )
        selected = await provenance.admit_rows("table", identities)
        if list(selected) != identities:
            raise ServiceUnavailableException(
                "A required SQL snapshot was denied", code="EVIDENCE_UNAVAILABLE"
            )
        if not selected:
            return []
        values = json.dumps([{key: str(value) for key, value in row.items()} for row in selected])
        rows = await self._read(
            """SELECT t.id AS table_id,t.name,t.kind,ss.id AS snapshot_id,ss.parquet_object_key
            FROM flyquery_tables t JOIN flyquery_schema_snapshots ss ON ss.table_id=t.id
            JOIN jsonb_to_recordset(CAST(:pins AS jsonb)) AS p(table_id uuid,snapshot_id uuid)
              ON t.id=p.table_id AND ss.id=p.snapshot_id
            WHERE t.dataset_id=:ds AND t.is_active=true AND ss.status='READY'""",
            {"ds": dataset_id, "pins": values},
        )
        if {(row["table_id"], row["snapshot_id"]) for row in rows} != {
            (row["table_id"], row["snapshot_id"]) for row in selected
        }:
            raise ServiceUnavailableException("Admitted SQL snapshots changed", code="EVIDENCE_UNAVAILABLE")
        return rows

    async def resolve(self, dataset_id, table_names, object_store_base=None, pins=None):
        from flyquery.core.services.storage.object_store_factory import storage_base

        rows = await self._tables(dataset_id, table_names, pins)
        provenance.resolved(dataset_id, rows)
        base = (object_store_base or storage_base(self._settings)).rstrip("/")
        return {row["name"]: f"{base}/{row['parquet_object_key']}" for row in rows}

    async def table_kinds_by_name(self, dataset_id, table_names):
        return {row["name"]: row["kind"] for row in await self._tables(dataset_id, table_names)}

    async def list_kinds_for_dataset_by_names(self, dataset_id, table_names):
        return [
            {"name": row["name"], "kind": row["kind"]} for row in await self._tables(dataset_id, table_names)
        ]

    async def current_snapshots(self, dataset_id, table_names):
        return {row["name"]: str(row["snapshot_id"]) for row in await self._tables(dataset_id, table_names)}
