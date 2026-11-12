# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reserve validation capacity before capturing provider evidence.

Stop old preparation writers for this coordinated transition. PostgreSQL adds a
constant default without updating retained rows or firing revision guards. Old
proofs, manifests and cleanup tombstones retain their recorded values. New
writers reserve first and capture proof once in a later bounded transaction.

DDL and function replacements commit together; interruption rolls back and can
be retried. After commit, repair forward rather than removing retained evidence.
"""

from alembic import op

revision = "koinon_0055_validation_root"
down_revision = "koinon_0054_mapping_validations"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Validation root admission requires PostgreSQL")
    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("SET LOCAL statement_timeout='60s'")
    op.execute("""ALTER TABLE public.koinon_content_mapping_validations
      ADD COLUMN root_captured boolean NOT NULL DEFAULT true""")
    op.execute("""ALTER TABLE public.koinon_content_mapping_validations
      ALTER COLUMN root_captured SET DEFAULT false,
      ALTER COLUMN root_kind DROP NOT NULL,
      ALTER COLUMN root_proof_sha256 DROP NOT NULL""")
    from koinon.integrations.content_sources.mapping_validation_guards import root_capture_statements

    for statement in root_capture_statements():
        op.execute(statement)


def downgrade():
    raise RuntimeError("Retain validation reservations and proof history; use a reviewed forward migration")
