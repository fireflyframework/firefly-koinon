# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared connection-aware environment for independent preserved histories."""

from alembic import context

configuration = context.config
connection = configuration.attributes.get("connection")
if connection is None:
    raise RuntimeError("Use deploy/migrate.py with an explicit migration datasource")
context.configure(
    connection=connection,
    target_metadata=configuration.attributes.get("target_metadata"),
    version_table=configuration.attributes["version_table"],
    compare_type=True,
)
with context.begin_transaction():
    context.run_migrations()
