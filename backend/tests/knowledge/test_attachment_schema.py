# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.data.relational.sqlalchemy import Base

from koinon.knowledge.attachments.entities import AttachmentBase


def test_private_file_tables_require_explicit_migration_and_are_not_auto_created_at_catalog_boot():
    names = {table.name for table in AttachmentBase.metadata.tables.values()}
    assert {"koinon_chat_attachments", "koinon_chat_attachment_chunks"} <= names
    assert not names.intersection(table.name for table in Base.metadata.tables.values())
