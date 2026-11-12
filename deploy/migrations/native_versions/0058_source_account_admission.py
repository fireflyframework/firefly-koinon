# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Add private cross-process source admission without modifying retained content.

Deploy before coordinator consumers. Keep synchronization disabled in a mixed
old/new deployment. DDL rolls back atomically on interruption. Rollback disables
new enumeration, retains coordination rows, and repairs forward; never reset the
non-cycling ticket or fencing sequences.
"""

from alembic import op

revision = "koinon_0058_account_admission"
down_revision = "koinon_0057_proof_indexes"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Shared account admission requires PostgreSQL")
    from koinon.integrations.content_sources.account_operation_entities import (
        ACCOUNT_OPERATION_TABLES,
        FENCE_SEQUENCE,
        TICKET_SEQUENCE,
    )

    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("SET LOCAL statement_timeout='60s'")
    FENCE_SEQUENCE.create(op.get_bind(), checkfirst=True)
    TICKET_SEQUENCE.create(op.get_bind(), checkfirst=True)
    for table in ACCOUNT_OPERATION_TABLES:
        table.create(op.get_bind())


def downgrade():
    raise RuntimeError("Disable source enumeration and repair forward; retain fencing sequences")
