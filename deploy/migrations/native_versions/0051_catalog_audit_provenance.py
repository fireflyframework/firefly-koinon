# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retain typed catalog audit dependencies through moves and deletion.

Cutover excludes writers with a five-second lock acquisition ceiling. Legacy
observations remain unknown; audit JSON never supplies historical evidence.
The transaction rolls back all schema/backfill/capture on failure. Retry this
forward migration after resolving malformed legacy references or writer load.
After activation retain the schema and guards; corrections require another
forward migration. Do not roll back to an executable that bypasses capture.
"""

import sqlalchemy as sa
from alembic import op

revision = "koinon_0051_audit_provenance"
down_revision = "koinon_0050_reader_selection"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Retained audit provenance requires PostgreSQL")
    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute(
        "LOCK TABLE public.lattice_catalog, public.koinon_curated_source_roots, "
        "public.lattice_audit IN SHARE ROW EXCLUSIVE MODE"
    )
    op.create_index("ix_catalog_audit_resource", "lattice_audit", ["resource_id"])
    op.create_table(
        "koinon_catalog_history_identities",
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("lattice_tenants.id"), primary_key=True),
        sa.Column("resource_id", sa.String(64), primary_key=True),
        sa.Column("coverage", sa.String(32), nullable=False),
        sa.UniqueConstraint("resource_id", name="uq_catalog_history_resource"),
        sa.CheckConstraint("coverage IN ('complete','legacy_unknown')", name="ck_catalog_history_coverage"),
    )
    op.create_table(
        "koinon_catalog_history_edges",
        sa.Column("tenant_id", sa.String(64), primary_key=True),
        sa.Column("dependent_id", sa.String(64), primary_key=True),
        sa.Column("origin_id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(32), primary_key=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dependent_id"],
            ["koinon_catalog_history_identities.tenant_id", "koinon_catalog_history_identities.resource_id"],
            name="fk_catalog_history_dependent",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "origin_id"],
            ["koinon_catalog_history_identities.tenant_id", "koinon_catalog_history_identities.resource_id"],
            name="fk_catalog_history_origin",
        ),
        sa.CheckConstraint("kind IN ('parent','curated_source')", name="ck_catalog_history_kind"),
    )
    op.create_index(
        "ix_catalog_history_origin",
        "koinon_catalog_history_edges",
        ["tenant_id", "origin_id", "dependent_id"],
    )
    # All endpoint observations are retained. Conflicting tenant identities abort
    # cutover rather than quietly classifying malformed legacy data as local.
    op.execute("""INSERT INTO public.koinon_catalog_history_identities(tenant_id,resource_id,coverage)
        SELECT tenant_id,id,'legacy_unknown' FROM public.lattice_catalog
        UNION SELECT tenant_id,parent_id,'legacy_unknown' FROM public.lattice_catalog
          WHERE parent_id IS NOT NULL
        UNION SELECT tenant_id,item_id,'legacy_unknown' FROM public.koinon_curated_source_roots
        UNION SELECT tenant_id,source_asset_id,'legacy_unknown' FROM public.koinon_curated_source_roots""")
    op.execute("""INSERT INTO public.koinon_catalog_history_edges(tenant_id,dependent_id,origin_id,kind)
        SELECT tenant_id,id,parent_id,'parent' FROM public.lattice_catalog WHERE parent_id IS NOT NULL
        UNION SELECT tenant_id,item_id,source_asset_id,'curated_source'
          FROM public.koinon_curated_source_roots""")
    from koinon.catalog.history_guards import statements

    for statement in statements():
        op.execute(statement)


def downgrade():
    raise RuntimeError("Retained audit evidence cannot be removed; use a reviewed forward migration")
