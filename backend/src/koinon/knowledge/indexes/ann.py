# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read-only catalog qualification; a same-name index is insufficient evidence."""

from sqlalchemy import text


async def ann_qualified(session, *, domain, set_id, dimensions):
    documents = domain == "documents"
    name = (
        "canon_chunk_vectors_hnsw_" + set_id.replace("-", "_") if documents else "ix_structured_vector_hnsw"
    )
    row = (
        (
            await session.execute(
                text("""
        SELECT i.indisvalid,i.indisready,i.indnkeyatts,i.indnatts,am.amname,opc.opcname,
          opn.nspname AS opschema,t.relname AS tablename,tn.nspname AS tableschema,
          replace(pg_catalog.pg_get_expr(i.indexprs,i.indrelid),'public.','') AS expression,
          pg_catalog.pg_get_expr(i.indpred,i.indrelid) AS predicate,
          a.attname AS column_name,
          replace(pg_catalog.format_type(a.atttypid,a.atttypmod),'public.','') AS column_type,
          pg_catalog.format('(set_id = %L::text)',CAST(:set_id AS text)) AS expected_predicate
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_catalog.pg_index i ON i.indexrelid=c.oid
        JOIN pg_catalog.pg_class t ON t.oid=i.indrelid
        JOIN pg_catalog.pg_namespace tn ON tn.oid=t.relnamespace
        JOIN pg_catalog.pg_am am ON am.oid=c.relam
        JOIN pg_catalog.pg_opclass opc ON opc.oid=i.indclass[0]
        JOIN pg_catalog.pg_namespace opn ON opn.oid=opc.opcnamespace
        LEFT JOIN pg_catalog.pg_attribute a ON a.attrelid=t.oid AND a.attnum=i.indkey[0]
        WHERE n.nspname='public' AND c.relname=:name
    """),
                {"name": name, "set_id": set_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if not row or not (
        row["indisvalid"]
        and row["indisready"]
        and row["indnkeyatts"] == row["indnatts"] == 1
        and row["amname"] == "hnsw"
        and row["opschema"] == row["tableschema"] == "public"
    ):
        return False
    if documents:
        cast = "vector" if dimensions <= 2000 else "halfvec"
        return (
            64 <= dimensions <= 4000
            and row["tablename"] == "canon_chunk_vectors"
            and row["opcname"] == cast + "_cosine_ops"
            and row["expression"] == f"(embedding)::{cast}({dimensions})"
            and row["predicate"] == row["expected_predicate"]
        )
    return (
        row["tablename"] == "flyquery_embedding_vectors"
        and row["opcname"] == "vector_cosine_ops"
        and row["expression"] is None
        and row["predicate"] is None
        and row["column_name"] == "embedding"
        and row["column_type"] == "vector(1536)"
    )
