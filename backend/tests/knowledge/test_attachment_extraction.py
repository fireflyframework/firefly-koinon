# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
from zipfile import ZipFile

import pytest

from koinon.knowledge.attachments.extraction import ExtractionFailure, extract
from koinon.knowledge.attachments.settings import AttachmentSettings


def test_private_text_keeps_exact_numbers_and_codepoint_provenance():
    original = ("😀 precise 9007199254740993 12.340000\n" * 150).encode()
    result = extract(original, "facts.txt", "text/plain", AttachmentSettings())
    assert "9007199254740993 12.340000" in result["text"]
    assert result["chunks"]
    for chunk in result["chunks"]:
        assert result["text"][chunk["char_start"] : chunk["char_end"]] == chunk["text"]
    assert len(result["text"]) < len(result["text"].encode())


def test_unknown_binary_and_mismatched_declared_image_fail_without_text_fallback():
    for name, mime, content in [
        ("opaque.bin", None, b"\x00\xff\x01"),
        ("spoof.png", "image/png", b"private text"),
    ]:
        with pytest.raises(ExtractionFailure):
            extract(content, name, mime, AttachmentSettings())


def test_bundle_rejects_paths_and_expansion_before_loading_members():
    archive = BytesIO()
    with ZipFile(archive, "w") as stream:
        stream.writestr("../outside.txt", "secret")
    with pytest.raises(ExtractionFailure) as error:
        extract(archive.getvalue(), "files.zip", "application/zip", AttachmentSettings())
    assert error.value.code == "ATTACHMENT_ARCHIVE_UNSAFE"


def test_invalid_text_and_xml_entities_are_not_repaired_or_resolved():
    for name, content in [
        ("bad.txt", b"\xffhello"),
        ("bad.xml", b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///private">]><x>&e;</x>'),
    ]:
        with pytest.raises(ExtractionFailure):
            extract(content, name, None, AttachmentSettings())


def test_verified_image_is_reencoded_and_pixel_bounded():
    from PIL import Image

    original = BytesIO()
    Image.new("RGB", (10, 8), "red").save(original, format="PNG", pnginfo=None)
    result = extract(original.getvalue(), "small.png", "image/png", AttachmentSettings())
    assert result["kind"] == "image" and result["media_type"] == "image/png"
    assert (result["image_width"], result["image_height"]) == (10, 8)
    with pytest.raises(ExtractionFailure):
        extract(original.getvalue(), "small.png", "image/png", AttachmentSettings(max_image_pixels=50))


def test_complete_private_workbook_text_names_each_sheet_instead_of_silently_flattening():
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active.title = "Actuals"
    workbook.active.append(["region", "amount"])
    workbook.active.append(["north", 12])
    forecast = workbook.create_sheet("Forecast")
    forecast.append(["region", "amount"])
    forecast.append(["north", 19])
    original = BytesIO()
    workbook.save(original)
    result = extract(original.getvalue(), "regions.xlsx", None, AttachmentSettings())
    assert "Section: Actuals" in result["text"] and "Section: Forecast" in result["text"]
    assert {tuple(chunk["section_path"]) for chunk in result["chunks"]} == {("Actuals",), ("Forecast",)}
    for chunk in result["chunks"]:
        assert result["text"][chunk["char_start"] : chunk["char_end"]] == chunk["text"]
