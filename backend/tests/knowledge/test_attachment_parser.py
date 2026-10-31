# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import sys
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


async def test_parser_child_does_not_write_bytecode_to_its_module_directory(tmp_path, monkeypatch):
    modules = tmp_path / "modules"
    package = modules / "koinon" / "knowledge" / "attachments"
    package.mkdir(parents=True)
    for directory in (modules / "koinon", modules / "koinon" / "knowledge", package):
        (directory / "__init__.py").write_text("")
    (package / "extraction.py").write_text(
        "import json, sys\n"
        "json.loads(sys.stdin.buffer.read())\n"
        "print(json.dumps({'result': {'bytecode_disabled': sys.dont_write_bytecode}}))\n"
    )
    monkeypatch.setattr(sys, "path", [str(modules)])
    settings = AttachmentSettings(storage_root=str(tmp_path / "private"))
    parser = PrivateAttachmentParser(AttachmentStorage(settings), settings)

    result = await parser.parse(
        SimpleNamespace(filename="facts.txt", declared_media_type="text/plain"), b"A private document."
    )

    assert result["bytecode_disabled"] is True
    assert list(modules.rglob("*.pyc")) == []
