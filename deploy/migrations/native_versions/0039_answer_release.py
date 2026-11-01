# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Append-only output releases without rewriting existing conversations or tool evidence."""

from alembic import op

revision = "koinon_0039_answer_release"
down_revision = "koinon_0038_operator_contacts"
branch_labels = None
depends_on = None


def release_guards(dialect: str) -> tuple[str, ...]:
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Answer release journals require PostgreSQL or SQLite")
    if dialect == "sqlite":
        return (
            "CREATE UNIQUE INDEX uq_koinon_answer_release_generation ON koinon_chat_tool_results "
            "(run_id, COALESCE(json_extract(payload,'$.generation_id'),''), "
            "CASE WHEN json_extract(payload,'$.generation_id') IS NULL THEN "
            "COALESCE(json_extract(payload,'$.reset_sequence'),0) ELSE 0 END) WHERE kind='answer_release'",
            "CREATE TRIGGER koinon_answer_release_update BEFORE UPDATE ON koinon_chat_tool_results "
            "WHEN OLD.kind='answer_release' OR NEW.kind='answer_release' "
            "BEGIN SELECT RAISE(ABORT,'Answer release receipt is immutable'); END",
            "CREATE TRIGGER koinon_answer_release_delete BEFORE DELETE ON koinon_chat_tool_results "
            "WHEN OLD.kind='answer_release' "
            "BEGIN SELECT RAISE(ABORT,'Answer release receipt cannot be deleted'); END",
        )
    return (
        "CREATE UNIQUE INDEX uq_koinon_answer_release_generation ON public.koinon_chat_tool_results "
        "(run_id, (COALESCE(payload::jsonb->>'generation_id','')), "
        "(CASE WHEN payload::jsonb->>'generation_id' IS NULL THEN "
        "COALESCE((payload::jsonb->>'reset_sequence')::integer,0) ELSE 0 END)) WHERE kind='answer_release'",
        "CREATE FUNCTION public.koinon_answer_release_guard() RETURNS trigger LANGUAGE plpgsql "
        "SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN "
        "IF TG_OP='TRUNCATE' THEN "
        "IF EXISTS (SELECT 1 FROM public.koinon_chat_tool_results WHERE kind='answer_release') THEN "
        "RAISE EXCEPTION 'Answer release receipts cannot be truncated' USING ERRCODE='23000'; END IF; "
        "RETURN NULL; END IF; "
        "IF OLD.kind='answer_release' OR (TG_OP='UPDATE' AND NEW.kind='answer_release') THEN "
        "RAISE EXCEPTION 'Answer release receipt is immutable' USING ERRCODE='23000'; END IF; "
        "IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END; $$",
        "CREATE TRIGGER koinon_answer_release_rows BEFORE UPDATE OR DELETE "
        "ON public.koinon_chat_tool_results FOR EACH ROW "
        "EXECUTE FUNCTION public.koinon_answer_release_guard()",
        "CREATE TRIGGER koinon_answer_release_truncate BEFORE TRUNCATE "
        "ON public.koinon_chat_tool_results FOR EACH STATEMENT "
        "EXECUTE FUNCTION public.koinon_answer_release_guard()",
    )


def upgrade():
    for statement in release_guards(op.get_bind().dialect.name):
        op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Answer release receipts require a reviewed restore; automatic downgrade is unsupported"
    )
