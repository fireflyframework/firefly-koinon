# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Firefly Software Foundation
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

"""Parquet reader (pass-through copy + schema introspection)."""

from __future__ import annotations

from pathlib import Path

from flyquery.core.services.ingestion.coordinates import record_coordinates
from flyquery.core.services.ingestion.native_call import run_native
from flyquery.core.services.ingestion.reader import (
    ColumnSchema,
    MaterialiseResult,
    ProposedTable,
    TableExtractionRules,
)
from flyquery.core.services.ingestion.resources import account_path, copy_file, output_size


class ParquetReader:
    formats = ("parquet",)

    async def enumerate_tables(self, source_path: str, rules: TableExtractionRules) -> list[ProposedTable]:
        return await run_native(self._enumerate_sync, source_path)

    async def materialise(
        self,
        source_path: str,
        table: ProposedTable,
        target_parquet_key: str,
        *,
        workspace_locale: str,
        type_infer_sample_rows: int,
        max_title_rows: int = 3,
    ) -> MaterialiseResult:
        return await run_native(self._materialise_sync, source_path, target_parquet_key)

    @staticmethod
    def _enumerate_sync(source_path: str) -> list[ProposedTable]:
        import pyarrow.parquet as pq

        meta = pq.ParquetFile(source_path)
        return [
            ProposedTable(
                name=Path(source_path).stem,
                sheet_or_json_path=None,
                n_columns=len(meta.schema_arrow),
                n_rows_estimate=meta.metadata.num_rows,
            )
        ]

    @staticmethod
    def _materialise_sync(source_path: str, target_parquet_key: str) -> MaterialiseResult:
        account_path(source_path)
        account_path(target_parquet_key)
        import pyarrow as pa
        import pyarrow.parquet as pq

        Path(target_parquet_key).parent.mkdir(parents=True, exist_ok=True)
        copy_file(source_path, target_parquet_key)
        meta = pq.ParquetFile(target_parquet_key)
        names = meta.schema_arrow.names
        # Use logical type names from the Arrow schema for richer types
        arrow_schema = meta.schema_arrow
        columns = tuple(
            ColumnSchema(
                name=names[i],
                data_type=str(arrow_schema.field(i).type),
                is_nullable=arrow_schema.field(i).nullable,
                position=i,
            )
            for i in range(len(names))
        )
        return MaterialiseResult(
            target_parquet_key=target_parquet_key,
            parquet_byte_size=output_size(target_parquet_key),
            n_rows_actual=meta.metadata.num_rows,
            columns=columns,
            coordinates=record_coordinates(
                source_path,
                "parquet",
                "parquet",
                arrow_schema,
                meta.metadata.num_rows,
                dependencies=(("pyarrow", pa.__version__),),
            ),
        )
