# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Scoped versioned schema/example vectors, independent from preserved inline vectors."""

from uuid import UUID

from pyfly.data.transaction import infrastructure_unit
from sqlalchemy import text

OBJECTS_SQL = """
WITH objects AS (
 SELECT o.id,'schema'::text AS kind,
   jsonb_build_object('id',o.id,'kind','schema','qualified_name',o.qualified_name,
     'data_type',o.data_type,'description',o.description,'synonyms_json',o.synonyms_json,
     'profile_json',o.profile_json,'sample_values_json',o.sample_values_json) AS payload,
   encode(sha256(convert_to(jsonb_build_array(o.qualified_name,o.data_type,o.description,
     o.synonyms_json,o.profile_json,o.sample_values_json)::text,'UTF8')),'hex') AS source_hash
 FROM flyquery_schema_objects o
 WHERE o.tenant_id=:tenant AND o.workspace_id=:workspace AND o.is_active=true
 UNION ALL
 SELECT e.id,'example'::text,
   jsonb_build_object('id',e.id,'kind','example','question',e.question,'generated_sql',e.generated_sql),
   encode(sha256(convert_to(jsonb_build_array(e.question,e.generated_sql)::text,'UTF8')),'hex')
 FROM flyquery_examples e
 WHERE e.tenant_id=:tenant AND e.workspace_id=:workspace AND e.quality IN ('APPROVED','PROPOSED')
)
"""


class EmbeddingSetRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def params(self, tenant_id, workspace_id, set_id):
        return {"tenant": tenant_id, "workspace": UUID(str(workspace_id)), "set_id": set_id}

    async def missing(self, *, tenant_id, workspace_id, set_id, limit=32):
        params = {**self.params(tenant_id, workspace_id, set_id), "limit": limit}
        async with infrastructure_unit(self.session_factory) as session:
            rows = (
                (
                    await session.execute(
                        text(
                            OBJECTS_SQL
                            + """
                SELECT o.payload,o.source_hash FROM objects o
                LEFT JOIN flyquery_embedding_vectors v ON v.set_id=:set_id
                  AND v.tenant_id=:tenant AND v.workspace_id=:workspace
                  AND v.kind=o.kind AND v.object_id=o.id
                WHERE v.content_hash IS DISTINCT FROM o.source_hash
                ORDER BY o.kind,o.id LIMIT :limit
            """
                        ),
                        params,
                    )
                )
                .mappings()
                .all()
            )
            return [
                {**row["payload"], "id": UUID(row["payload"]["id"]), "source_hash": row["source_hash"]}
                for row in rows
            ]

    async def counts(self, *, tenant_id, workspace_id, set_id):
        params = self.params(tenant_id, workspace_id, set_id)
        async with infrastructure_unit(self.session_factory) as session:
            row = (
                (
                    await session.execute(
                        text(
                            OBJECTS_SQL
                            + """
                SELECT count(*) AS chunk_count,count(v.object_id) AS vector_count
                FROM objects o LEFT JOIN flyquery_embedding_vectors v ON v.set_id=:set_id
                  AND v.tenant_id=:tenant AND v.workspace_id=:workspace
                  AND v.kind=o.kind AND v.object_id=o.id AND v.content_hash=o.source_hash
            """
                        ),
                        params,
                    )
                )
                .mappings()
                .one()
            )
            return dict(row)

    async def upsert(self, *, tenant_id, workspace_id, set_id, rows):
        params = self.params(tenant_id, workspace_id, set_id)
        async with infrastructure_unit(self.session_factory) as session:
            for row in rows:
                await session.execute(
                    text(
                        OBJECTS_SQL
                        + """
                    INSERT INTO flyquery_embedding_vectors
                      (set_id,kind,object_id,tenant_id,workspace_id,content_hash,embedding,model,text)
                    SELECT :set_id,o.kind,o.id,:tenant,:workspace,o.source_hash,
                      CAST(:embedding AS vector),:model,''
                    FROM objects o JOIN flyquery_embedding_sets s ON s.id=:set_id
                      AND s.tenant_id=:tenant AND s.workspace_id=:workspace
                    WHERE o.id=:object_id AND o.kind=:kind AND o.source_hash=:source_hash
                      AND s.status IN ('building','active','ready')
                    ON CONFLICT(set_id,kind,object_id) DO UPDATE SET
                      content_hash=EXCLUDED.content_hash,embedding=EXCLUDED.embedding,model=EXCLUDED.model
                """
                    ),
                    {
                        **params,
                        "object_id": UUID(str(row["id"])),
                        "kind": row["kind"],
                        "source_hash": row["content_hash"],
                        "embedding": str(row["embedding"]),
                        "model": row["model"],
                    },
                )
