# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

_path = Path(__file__).resolve().parents[1] / "migrate.py"
_spec = importlib.util.spec_from_file_location("revision_history_migrate", _path)
_migrate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migrate)


@pytest.mark.parametrize("name,versions", _migrate.HISTORIES)
def test_revision_identifiers_fit_the_postgresql_version_column(name, versions):
    context = MigrationContext.configure(dialect_name="postgresql")
    version_table = context.impl.version_table_impl(
        version_table=f"koinon_{name}_version",
        version_table_schema=None,
        version_table_pk=True,
    )
    maximum = version_table.c.version_num.type.length
    config = _migrate.history_config(name, versions, None)
    revisions = tuple(ScriptDirectory.from_config(config).walk_revisions())
    assert revisions
    oversized = {
        revision.revision: len(revision.revision)
        for revision in revisions
        if len(revision.revision) > maximum
    }
    assert not oversized, f"{name} revision identifiers exceed {maximum}: {oversized}"
