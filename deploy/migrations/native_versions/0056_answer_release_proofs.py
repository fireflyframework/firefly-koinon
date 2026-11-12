# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Add private immutable release attestations without rewriting historical rows.

Deploy with a role that can create the isolated function owner. Keep recorded
reads disabled until publisher, bounded backfill and independent acceptance pass.
Failure rolls this additive transaction back. After commit, retain the tables
and repair forward; disabling recorded reads is the compatible rollback.
"""

from alembic import op

revision = "koinon_0056_release_proofs"
down_revision = "koinon_0055_validation_root"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Answer release proof enforcement requires PostgreSQL")
    from koinon.answers.release_proof_entities import PROOF_TABLES
    from koinon.answers.release_proof_guards import guard_statements

    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("SET LOCAL statement_timeout='60s'")
    for table in PROOF_TABLES:
        table.create(op.get_bind())
    for statement in guard_statements():
        op.execute(statement)


def downgrade():
    raise RuntimeError("Retain immutable answer proofs; disable recorded reads and repair forward")
