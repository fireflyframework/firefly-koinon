# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import sys
import tempfile
from types import SimpleNamespace

from koinon.knowledge.attachments.parser import PrivateAttachmentParser
from koinon.knowledge.attachments.settings import AttachmentSettings
from koinon.knowledge.attachments.storage import AttachmentStorage
from koinon.storage.settings import AttachmentStorageProfile


async def test_cloud_parser_uses_ephemeral_scratch_without_writing_to_application(tmp_path, monkeypatch):
    application = tmp_path / "application"
    application.mkdir(mode=0o500)
    scratch = tmp_path / "scratch"
    scratch.mkdir(mode=0o700)
    monkeypatch.chdir(application)
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    settings = AttachmentSettings()
    profile = AttachmentStorageProfile(
        backend="azure",
        azure_account_url="https://example.blob.core.windows.net",
        azure_container="attachments",
    )
    storage = AttachmentStorage(settings, profile)
    parser = PrivateAttachmentParser(storage, settings)
    try:
        result = await parser.parse(
            SimpleNamespace(filename="facts.txt", declared_media_type="text/plain"),
            b"Cloud originals do not require a local storage root.",
        )
        assert result["text"] == "Cloud originals do not require a local storage root."
        assert list(application.iterdir()) == []
        assert list(scratch.iterdir()) == []
    finally:
        await storage.close()
        application.chmod(0o700)


async def test_real_bounded_child_extracts_text_and_cleans_private_temporary_directory(tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    scratch.mkdir(mode=0o700)
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    settings = AttachmentSettings(storage_root=str(tmp_path / "private"))
    parser = PrivateAttachmentParser(AttachmentStorage(settings), settings)
    result = await parser.parse(
        SimpleNamespace(filename="facts.txt", declared_media_type="text/plain"),
        b"Only this private file contains the number 12.",
    )
    assert result["text"] == "Only this private file contains the number 12."
    assert list(scratch.iterdir()) == []
    assert list((tmp_path / "private").iterdir()) == []


async def test_parser_child_does_not_write_bytecode_to_its_module_directory(tmp_path, monkeypatch):
    modules = tmp_path / "modules"
    package = modules / "koinon" / "knowledge" / "attachments"
    package.mkdir(parents=True)
    for directory in (modules / "koinon", modules / "koinon" / "knowledge", package):
        (directory / "__init__.py").write_text("")
    (package / "extraction.py").write_text(
        "import json, os, sys\n"
        "json.loads(sys.stdin.buffer.read())\n"
        "print(json.dumps({'result': {'bytecode_disabled': sys.dont_write_bytecode, "
        "'scratch_mode': os.stat(os.getcwd()).st_mode & 0o777}}))\n"
    )
    monkeypatch.setattr(sys, "path", [str(modules)])
    settings = AttachmentSettings(storage_root=str(tmp_path / "private"))
    parser = PrivateAttachmentParser(AttachmentStorage(settings), settings)

    result = await parser.parse(
        SimpleNamespace(filename="facts.txt", declared_media_type="text/plain"), b"A private document."
    )

    assert result["bytecode_disabled"] is True
    assert result["scratch_mode"] == 0o700
    assert list(modules.rglob("*.pyc")) == []
