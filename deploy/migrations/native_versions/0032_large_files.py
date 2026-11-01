# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded queued Library originals; preserve all existing bytes and admissions."""

import sqlalchemy as sa
from alembic import op

revision = "koinon_0032_large_files"
down_revision = "koinon_0031_activity"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("koinon_bulk_batches") as table:
        table.drop_constraint("ck_bulk_batch_bounds", type_="check")
        table.create_check_constraint(
            "ck_bulk_batch_bounds",
            "revision BETWEEN 1 AND 2147483647 AND total_bytes BETWEEN 1 AND 536870912",
        )
    with op.batch_alter_table("koinon_bulk_items") as table:
        table.drop_constraint("ck_bulk_item_bounds", type_="check")
        table.create_check_constraint(
            "ck_bulk_item_bounds",
            "mode IN ('document','dataset') AND ordinal BETWEEN 0 AND 99 AND size_bytes BETWEEN 1 AND 134217728",
        )
    op.add_column(
        "koinon_bulk_uploads",
        sa.Column("object_reference_json", sa.JSON(), nullable=True),
    )

    with op.batch_alter_table("koinon_external_file_reviews") as table:
        table.add_column(sa.Column("bulk_batch_id", sa.String(36), nullable=True))
        table.add_column(sa.Column("blob_reference_json", sa.JSON(), nullable=True))
        table.create_foreign_key(
            "fk_external_file_bulk_batch",
            "koinon_bulk_batches",
            ["bulk_batch_id"],
            ["id"],
        )


def downgrade():
    connection = op.get_bind()
    if connection.execute(
        sa.text(
            "SELECT 1 FROM koinon_external_file_reviews WHERE bulk_batch_id IS NOT NULL OR blob_reference_json IS NOT NULL LIMIT 1"
        )
    ).first():
        raise RuntimeError(
            "Retained large-file reviews require this schema; downgrade would lose their receipts"
        )
    if (
        connection.execute(
            sa.text(
                "SELECT 1 FROM koinon_bulk_uploads WHERE object_reference_json IS NOT NULL LIMIT 1"
            )
        ).first()
        or connection.execute(
            sa.text(
                "SELECT 1 FROM koinon_bulk_items WHERE size_bytes > 33554432 LIMIT 1"
            )
        ).first()
        or connection.execute(
            sa.text(
                "SELECT 1 FROM koinon_bulk_batches WHERE total_bytes > 268435456 LIMIT 1"
            )
        ).first()
    ):
        raise RuntimeError(
            "Retained large-file admissions require this schema; downgrade would lose their receipt or bounds"
        )
    with op.batch_alter_table("koinon_external_file_reviews") as table:
        table.drop_constraint("fk_external_file_bulk_batch", type_="foreignkey")
        table.drop_column("blob_reference_json")
        table.drop_column("bulk_batch_id")
    op.drop_column("koinon_bulk_uploads", "object_reference_json")
    with op.batch_alter_table("koinon_bulk_items") as table:
        table.drop_constraint("ck_bulk_item_bounds", type_="check")
        table.create_check_constraint(
            "ck_bulk_item_bounds",
            "mode IN ('document','dataset') AND ordinal BETWEEN 0 AND 99 AND size_bytes BETWEEN 1 AND 33554432",
        )
    with op.batch_alter_table("koinon_bulk_batches") as table:
        table.drop_constraint("ck_bulk_batch_bounds", type_="check")
        table.create_check_constraint(
            "ck_bulk_batch_bounds",
            "revision BETWEEN 1 AND 2147483647 AND total_bytes BETWEEN 1 AND 268435456",
        )
