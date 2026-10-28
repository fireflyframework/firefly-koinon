# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private explicit-consent intents and acknowledged native knowledge metadata."""

import sqlalchemy as sa
from alembic import op
from pyfly.data.relational.sqlalchemy.types import UtcDateTime

revision = "koinon_0014_curated_knowledge"
down_revision = "koinon_0013_exports_shares"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "koinon_knowledge_intents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("destination_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("target_item_id", sa.String(64), nullable=False),
        sa.Column("authorization_digest", sa.String(64), nullable=False),
        sa.Column("originating_token_ids", sa.JSON(), nullable=False),
        sa.Column("preview_token_id", sa.String(64), nullable=True),
        sa.Column("confirming_token_id", sa.String(64), nullable=True),
        sa.Column("confirmation_key", sa.String(160), nullable=True),
        sa.Column("receipt_json", sa.JSON(), nullable=True),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("expires_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "subject",
            "confirmation_key",
            name="uq_knowledge_confirmation_key",
        ),
    )
    op.create_index(
        "ix_knowledge_intent_owner",
        "koinon_knowledge_intents",
        ["tenant_id", "subject", "status"],
    )
    op.create_table(
        "koinon_curated_catalog_state",
        sa.Column(
            "item_id",
            sa.String(64),
            sa.ForeignKey("lattice_catalog.id"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("native_item_id", sa.String(64), nullable=False),
        sa.Column("native_workspace_id", sa.String(64), nullable=False),
        sa.Column("head_version", sa.Integer(), nullable=False),
        sa.Column("head_version_id", sa.String(64), nullable=False),
        sa.Column("head_operation_id", sa.String(64), nullable=False),
        sa.Column("serving_version", sa.Integer(), nullable=True),
        sa.Column("serving_version_id", sa.String(64), nullable=True),
        sa.Column("serving_operation_id", sa.String(64), nullable=True),
        sa.Column("root_count", sa.Integer(), nullable=False),
    )
    for column in ("tenant_id", "workspace_id"):
        op.create_index(
            "ix_koinon_curated_catalog_state_" + column,
            "koinon_curated_catalog_state",
            [column],
        )
    op.create_table(
        "koinon_curated_source_roots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(64),
            sa.ForeignKey("lattice_tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.String(64),
            sa.ForeignKey("koinon_curated_catalog_state.item_id"),
            nullable=False,
        ),
        sa.Column("native_version_id", sa.String(64), nullable=False),
        sa.Column(
            "source_asset_id",
            sa.String(64),
            sa.ForeignKey("lattice_catalog.id"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "item_id", "native_version_id", "source_asset_id", name="uq_curated_root"
        ),
    )
    op.create_index(
        "ix_curated_root_version",
        "koinon_curated_source_roots",
        ["tenant_id", "item_id", "native_version_id"],
    )


def downgrade():
    raise RuntimeError(
        "Use reviewed backup/restore recovery; consent and committed receipts must be preserved"
    )
