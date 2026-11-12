# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retain source-authorized structure without changing original content evidence.

Expand before deploying version-aware consumers; keep metadata dispatch disabled
until all workers/readers support structural pointers. The transaction rolls back
DDL on failure. Roll back the feature by disabling metadata dispatch and repair
forward, retaining immutable proofs and version-aware readers. Never downgrade
to readers that interpret a structural pointer as an ordinary local revision.
"""

from alembic import op

revision = "koinon_0059_structure_proofs"
down_revision = "koinon_0058_account_admission"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Source structural publication requires PostgreSQL")
    from koinon.integrations.content_sources.structure_publication_entities import (
        SourceStructurePublication,
    )
    from koinon.integrations.content_sources.structure_publication_guards import (
        statements,
    )

    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("SET LOCAL statement_timeout='60s'")
    op.execute(
        "ALTER TABLE public.koinon_content_publication_baselines "
        "ADD COLUMN previous_structure_publication_id varchar(64)"
    )
    SourceStructurePublication.__table__.create(op.get_bind())
    op.execute(
        "ALTER TABLE public.koinon_content_publication_baselines ADD CONSTRAINT "
        "fk_content_publication_structure FOREIGN KEY "
        "(previous_structure_publication_id,tenant_id,mapping_id,object_id,previous_attempt_id) "
        "REFERENCES public.koinon_content_structure_publications "
        "(id,tenant_id,mapping_id,object_id,content_attempt_id)"
    )
    op.execute(
        "CREATE INDEX ix_content_publication_structure ON "
        "public.koinon_content_publication_baselines(previous_structure_publication_id)"
    )
    op.execute(
        "CREATE INDEX ix_content_publication_ack ON public.koinon_content_publication_baselines "
        "(tenant_id,mapping_id,object_id,acknowledgement_sha256)"
    )
    for statement in statements():
        op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Disable metadata dispatch and repair forward; retain immutable structural evidence"
    )
