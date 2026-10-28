# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

from koinon.knowledge.attachments.parser import PrivateAttachmentParser
from koinon.knowledge.attachments.settings import AttachmentSettings
from koinon.knowledge.attachments.storage import AttachmentStorage


async def test_real_bounded_child_extracts_text_and_cleans_private_temporary_directory(tmp_path):
    settings = AttachmentSettings(storage_root=str(tmp_path / "private"))
    parser = PrivateAttachmentParser(AttachmentStorage(settings), settings)
    result = await parser.parse(
        SimpleNamespace(filename="facts.txt", declared_media_type="text/plain"),
        b"Only this private file contains the number 12.",
    )
    assert result["text"] == "Only this private file contains the number 12."
    assert list((tmp_path / "private" / ".parsers").iterdir()) == []
