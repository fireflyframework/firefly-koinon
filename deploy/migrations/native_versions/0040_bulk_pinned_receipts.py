# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Allow one validated pinned-original receipt without weakening bulk identity guards."""

from alembic import op

revision = "koinon_0040_bulk_pinned"
down_revision = "koinon_0039_answer_release"
branch_labels = None
depends_on = None

FIELDS = (
    "schema_version",
    "key",
    "size_bytes",
    "sha256",
    "store_identity",
    "version_kind",
    "version",
)


def _valid_reference(dialect):
    reference = "NEW.object_reference_json"
    if dialect == "postgresql":
        reference += "::jsonb"
        keys = "ARRAY[" + ",".join(f"'{field}'" for field in FIELDS) + "]::text[]"
        checks = [
            f"jsonb_typeof({reference})='object'",
            f"{reference} ?& {keys}",
            f"{reference}-{keys}='{{}}'::jsonb",
        ]
        integer = "number"
        size = "size_bytes::text"
    else:
        checks = [
            f"json_type({reference})='object'",
            f"(SELECT count(*) FROM json_each({reference}))=7",
        ]
        integer = "integer"
        size = "size_bytes"

    def value(field):
        if dialect == "postgresql" and field in {"schema_version", "size_bytes"}:
            # JSONB normalizes exponent numbers; the stored JSON must still decode as integers.
            return f"(NEW.object_reference_json->>'{field}')"
        return (
            f"({reference}->>'{field}')"
            if dialect == "postgresql"
            else f"json_extract({reference},'$.{field}')"
        )

    def kind(field):
        return (
            f"jsonb_typeof({reference}->'{field}')"
            if dialect == "postgresql"
            else f"json_type({reference},'$.{field}')"
        )

    schema = "public" if dialect == "postgresql" else "main"
    expected_schema = "'1'" if dialect == "postgresql" else "1"
    string = "string" if dialect == "postgresql" else "text"
    checks += [
        f"{kind(field)}='{string}'" for field in FIELDS if field not in {"schema_version", "size_bytes"}
    ]
    checks += [
        f"{kind('schema_version')}='{integer}'",
        f"{value('schema_version')}={expected_schema}",
        f"{kind('size_bytes')}='{integer}'",
        f"{value('key')}=NEW.object_key",
        f"{value('size_bytes')}=(SELECT {size} FROM {schema}.koinon_bulk_items WHERE id=NEW.item_id)",
        f"{value('sha256')}=(SELECT sha256 FROM {schema}.koinon_bulk_items WHERE id=NEW.item_id)",
        f"{value('version_kind')} IN ('azure_etag','gcs_generation','s3_version','local_inode')",
        f"length({value('version')}) BETWEEN 1 AND 2048",
    ]
    for field in ("sha256", "store_identity"):
        checks.append(f"length({value(field)})=64")
        checks.append(
            f"{value(field)} ~ '^[0-9a-f]{{64}}$'"
            if dialect == "postgresql"
            else f"{value(field)} NOT GLOB '*[^0-9a-f]*'"
        )
    if dialect == "postgresql":
        checks.append(f"{value('version')} !~ '[[:cntrl:]]'")
    else:
        checks += [f"instr({value('version')},char({code}))=0" for code in (*range(32), 127)]
    valid = "COALESCE((" + " AND ".join(checks) + "),false)"
    return (
        valid if dialect == "postgresql" else f"CASE WHEN json_valid({reference}) THEN {valid} ELSE false END"
    )


def _sqlite_bound(reference):
    return (
        f"CASE WHEN json_valid({reference}) THEN json_type({reference})<>'null' "
        f"ELSE {reference} IS NOT NULL END"
    )


def upgrade():
    dialect = op.get_bind().dialect.name
    valid = _valid_reference(dialect)
    if dialect == "postgresql":
        op.execute(f"""CREATE OR REPLACE FUNCTION public.koinon_bulk_uploads_guard() RETURNS trigger
            LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
            BEGIN
                IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Retain bulk originals and receipts'; END IF;
                IF TG_OP='UPDATE' THEN
                    IF (to_jsonb(NEW)-ARRAY['status','permit_held','object_reference_json']::text[])
                       IS DISTINCT FROM
                       (to_jsonb(OLD)-ARRAY['status','permit_held','object_reference_json']::text[])
                       OR (NOT OLD.permit_held AND NEW.permit_held)
                       OR (OLD.status='verified' AND NEW.status<>'verified') THEN
                        RAISE EXCEPTION 'Immutable bulk identity or receipt';
                    END IF;
                    IF OLD.object_reference_json IS NOT NULL
                       AND OLD.object_reference_json::jsonb<>'null'::jsonb THEN
                        IF NEW.object_reference_json::jsonb
                           IS DISTINCT FROM OLD.object_reference_json::jsonb
                           OR (NEW.object_reference_json->>'schema_version')
                              IS DISTINCT FROM (OLD.object_reference_json->>'schema_version')
                           OR (NEW.object_reference_json->>'size_bytes')
                              IS DISTINCT FROM (OLD.object_reference_json->>'size_bytes') THEN
                            RAISE EXCEPTION 'Immutable bulk pinned receipt';
                        END IF;
                        RETURN NEW;
                    END IF;
                END IF;
                IF NEW.object_reference_json IS NOT NULL AND NEW.object_reference_json::jsonb<>'null'::jsonb
                   AND NOT ({valid}) THEN
                    RAISE EXCEPTION 'Invalid bulk pinned receipt';
                END IF;
                RETURN NEW;
            END $$""")
        op.execute(
            "CREATE TRIGGER koinon_bulk_uploads_reference_insert BEFORE INSERT ON public.koinon_bulk_uploads "
            "FOR EACH ROW EXECUTE FUNCTION public.koinon_bulk_uploads_guard()"
        )
    elif dialect == "sqlite":
        old, new = "OLD.object_reference_json", "NEW.object_reference_json"
        equal = (
            f"CASE WHEN json_valid({old}) AND json_valid({new}) THEN "
            f"NOT EXISTS(SELECT fullkey,type,atom FROM json_tree({old}) "
            f"EXCEPT SELECT fullkey,type,atom FROM json_tree({new})) "
            f"AND NOT EXISTS(SELECT fullkey,type,atom FROM json_tree({new}) "
            f"EXCEPT SELECT fullkey,type,atom FROM json_tree({old})) "
            f"ELSE {new} IS {old} END"
        )
        op.execute(
            "CREATE TRIGGER koinon_bulk_uploads_reference_update BEFORE UPDATE ON koinon_bulk_uploads "
            f"WHEN ({_sqlite_bound(old)} AND NOT ({equal})) "
            f"OR (NOT ({_sqlite_bound(old)}) AND {_sqlite_bound(new)} AND NOT ({valid})) "
            "BEGIN SELECT RAISE(ABORT,'Immutable or invalid bulk pinned receipt'); END"
        )
        op.execute(
            "CREATE TRIGGER koinon_bulk_uploads_reference_insert BEFORE INSERT ON koinon_bulk_uploads "
            f"WHEN {_sqlite_bound(new)} AND NOT ({valid}) "
            "BEGIN SELECT RAISE(ABORT,'Invalid bulk pinned receipt'); END"
        )
    else:
        raise RuntimeError("Bulk pinned receipts require PostgreSQL or SQLite")


def downgrade():
    raise RuntimeError("Pinned originals require a reviewed restore; automatic downgrade is unsupported")
