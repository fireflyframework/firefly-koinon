# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import zipfile

import pytest

from flycanon.core.services.ingestion.file_parser import DocumentFilePolicy, parse_document_file


def office(path, kind="docx", *, malicious=False):
    namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    xml = f'<w:document xmlns:w="{namespace}"><w:body><w:p><w:r><w:t>Retained paragraph</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Retained table</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'
    if malicious:
        xml = '<!DOCTYPE root [<!ENTITY secret SYSTEM "file:///etc/passwd">]><root>&secret;</root>'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
        archive.writestr("[Content_Types].xml", "<Types/>")
    return path


async def test_file_parser_recovers_office_paragraphs_and_tables_without_loading_images(tmp_path):
    path = office(tmp_path / "retained.docx")
    parsed = await parse_document_file(path, filename="retained.docx", policy=DocumentFilePolicy())
    assert "Retained paragraph" in parsed.text and "Retained table" in parsed.text
    assert parsed.kind == "docx" and parsed.raw_bytes == path.stat().st_size
    assert parsed.peak_rss_bytes > 0
    assert not list(tmp_path.glob("koinon-parse-*"))


@pytest.mark.parametrize("filename", ["legacy.ppt", "unknown.bin", "book.epub", "message.eml"])
async def test_unregistered_document_formats_never_fall_back_to_plain_text(tmp_path, filename):
    path = tmp_path / filename
    path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1\x00Retained binary content")
    with pytest.raises(ValueError, match="format"):
        await parse_document_file(path, filename=filename, policy=DocumentFilePolicy())


@pytest.mark.parametrize("filename", ["renamed.txt", "renamed.md", "no-extension"])
@pytest.mark.parametrize("content", [b"text\x00binary", b"\xff\xfe\x01\x00", b"PK\x03\x04archive"])
async def test_text_routes_reject_binary_bytes_instead_of_lossy_decoding(tmp_path, filename, content):
    path = tmp_path / filename
    path.write_bytes(content)
    with pytest.raises(ValueError):
        await parse_document_file(path, filename=filename, policy=DocumentFilePolicy())


@pytest.mark.parametrize(
    "filename,kind",
    [
        ("note.md", "markdown"),
        ("note.markdown", "markdown"),
        ("note.txt", "text"),
        ("note.text", "text"),
        ("note", "text"),
    ],
)
async def test_text_aliases_keep_their_actual_format_and_unicode(tmp_path, filename, kind):
    path = tmp_path / filename
    path.write_text("# Review\n\nCafé revenue is 125.\n")
    parsed = await parse_document_file(path, filename=filename, policy=DocumentFilePolicy())
    assert parsed.kind == kind and "Café revenue is 125." in parsed.text


async def test_explicit_extensionless_text_mime_is_supported_but_cannot_disguise_legacy_binary(tmp_path):
    from flycanon.core.services.ingestion.file_parser import UnsupportedDocumentFormat, document_file_kind

    path = tmp_path / "note"
    path.write_text("# Heading\n\nPlain Unicode café.")
    parsed = await parse_document_file(
        path, filename=None, content_type="text/markdown", policy=DocumentFilePolicy()
    )
    assert parsed.kind == "markdown" and "café" in parsed.text
    with pytest.raises(UnsupportedDocumentFormat, match="save as .pptx") as error:
        document_file_kind("legacy.ppt", "text/plain")
    assert error.value.code == "DOCUMENT_FORMAT_UNSUPPORTED"


async def test_document_spreadsheet_obeys_expanded_package_budget(tmp_path):
    from openpyxl import Workbook

    path = tmp_path / "review.xlsx"
    workbook = Workbook()
    workbook.active.append(["Region", "Revenue"])
    workbook.active.append(["North", 125])
    workbook.save(path)
    workbook.close()
    with pytest.raises(ValueError):
        await parse_document_file(
            path, filename=path.name, policy=DocumentFilePolicy(expanded_max_bytes=16)
        )


@pytest.mark.parametrize("content", [b"\xd0\xcf\x11\xe0\x00legacy", b"%PDF-1.7 binary", b"plain words"])
async def test_renamed_rtf_requires_an_actual_rtf_header(tmp_path, content):
    path = tmp_path / "renamed.rtf"
    path.write_bytes(content)
    with pytest.raises(ValueError):
        await parse_document_file(path, filename=path.name, policy=DocumentFilePolicy())


async def test_valid_rtf_keeps_its_registered_text_loader(tmp_path):
    path = tmp_path / "review.rtf"
    path.write_bytes(b"{\\rtf1\\ansi North\\tab 125\\par}")
    parsed = await parse_document_file(path, filename=path.name, policy=DocumentFilePolicy())
    assert parsed.kind == "rtf" and "North" in parsed.text and "125" in parsed.text


@pytest.mark.parametrize("case", ["xml", "xml_utf16", "duplicate", "expanded", "text", "scratch"])
async def test_file_parser_fails_closed_on_unsafe_or_over_budget_office(tmp_path, case):
    path = office(tmp_path / "unsafe.docx", malicious=case == "xml")
    if case == "xml_utf16":
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "word/document.xml", "<!DOCTYPE document><document><p>text</p></document>".encode("utf-16")
            )
    values = {}
    if case == "duplicate":
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("word/document.xml", "<root/>")
    if case == "expanded":
        values["expanded_max_bytes"] = 16
    if case == "text":
        values["text_max_bytes"] = 4
    if case == "scratch":
        values["scratch_max_bytes"] = 16
    with pytest.raises(ValueError):
        await parse_document_file(path, filename="unsafe.docx", policy=DocumentFilePolicy(**values))
    assert not list(tmp_path.glob("koinon-parse-*"))


async def test_custom_office_part_paths_follow_relationship_slide_order_and_page_provenance(tmp_path):
    path = tmp_path / "custom.pptx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/custom/deck.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="main" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="custom/deck.xml"/></Relationships>',
        )
        archive.writestr(
            "custom/deck.xml",
            '<p:presentation xmlns:p="urn:p" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId id="1" r:id="second"/><p:sldId id="2" r:id="first"/></p:sldIdLst></p:presentation>',
        )
        archive.writestr(
            "custom/_rels/deck.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="first" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="parts/a.xml"/><Relationship Id="second" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="parts/b.xml"/></Relationships>',
        )
        for name, text in [("a", "Last slide"), ("b", "First slide")]:
            archive.writestr(f"custom/parts/{name}.xml", f"<slide><p><t>{text}</t></p></slide>")
    parsed = await parse_document_file(path, filename="custom.pptx", policy=DocumentFilePolicy())
    assert parsed.text.index("First slide") < parsed.text.index("Last slide")
    assert [(section["page"], section["body"]) for section in parsed.sections] == [
        (1, "First slide"),
        (2, "Last slide"),
    ]
    assert parsed.metadata["extraction_coverage"] == "text_and_tables"
    assert parsed.metadata["image_interpretation"] == "not_performed"


async def test_custom_word_part_headers_tables_and_body_keep_distinct_provenance(tmp_path):
    path = tmp_path / "custom.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types><Override PartName="/custom/main.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        )
        archive.writestr(
            "custom/main.xml",
            "<document><body><p><t>Body first</t></p><tbl><tr><tc><p><t>Table cell</t></p></tc></tr></tbl><p><t>Body last</t></p></body></document>",
        )
        archive.writestr(
            "custom/_rels/main.xml.rels",
            '<Relationships><Relationship Id="header" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header.xml"/></Relationships>',
        )
        archive.writestr("custom/header.xml", "<header><p><t>Retained header</t></p></header>")
    parsed = await parse_document_file(path, filename="custom.docx", policy=DocumentFilePolicy())
    assert parsed.text.index("Body first") < parsed.text.index("Table cell") < parsed.text.index("Body last")
    assert any(s["path"] == ["Header"] and s["body"] == "Retained header" for s in parsed.sections)
    assert all(s["page"] is None for s in parsed.sections)


async def test_parser_resource_failure_and_cancellation_reap_only_the_owned_child(tmp_path, monkeypatch):
    import asyncio

    import psutil

    from flycanon.core.services.ingestion import file_parser

    path = office(tmp_path / "owned.docx")
    observed = []

    def over_budget(pid):
        observed.append(pid)
        return 1024**3

    monkeypatch.setattr(file_parser, "_rss", over_budget)
    with pytest.raises(ValueError, match="memory or time"):
        await parse_document_file(path, filename="owned.docx", policy=DocumentFilePolicy())
    assert observed and not psutil.pid_exists(observed[-1])
    observed.clear()

    def active(pid):
        observed.append(pid)
        return 0

    monkeypatch.setattr(file_parser, "_rss", active)
    task = asyncio.create_task(parse_document_file(path, filename="owned.docx", policy=DocumentFilePolicy()))
    while not observed:
        await asyncio.sleep(0.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not psutil.pid_exists(observed[-1]) and path.exists()
    assert not list(tmp_path.glob("koinon-parse-*"))


@pytest.mark.parametrize("status", ["", "VmHWM: missing kB", "VmHWM: -1 kB", "VmHWM: 0 kB", "VmHWM: 12 MB", "VmHWM: 12 kB\nVmHWM: 13 kB"])
def test_linux_parser_peak_rejects_missing_or_malformed_kernel_measurements(monkeypatch, status):
    from flycanon.core.services.ingestion import file_parser

    monkeypatch.setattr(file_parser.sys, "platform", "linux")
    monkeypatch.setattr(file_parser.Path, "read_text", lambda self: status)
    with pytest.raises(ValueError, match="peak resident"):
        file_parser._peak_rss_bytes()


def test_linux_parser_peak_uses_its_post_exec_memory_high_water(monkeypatch):
    from types import SimpleNamespace

    from flycanon.core.services.ingestion import file_parser

    monkeypatch.setattr(file_parser.sys, "platform", "linux")
    monkeypatch.setattr(file_parser.Path, "read_text", lambda self: "Name:\tpython\nVmHWM:\t12345 kB\n")
    monkeypatch.setattr(file_parser.resource, "getrusage", lambda who: SimpleNamespace(ru_maxrss=900000))
    assert file_parser._peak_rss_bytes() == 12345 * 1024


def test_macos_parser_peak_keeps_native_byte_units(monkeypatch):
    from types import SimpleNamespace

    from flycanon.core.services.ingestion import file_parser

    monkeypatch.setattr(file_parser.sys, "platform", "darwin")
    monkeypatch.setattr(file_parser.resource, "getrusage", lambda who: SimpleNamespace(ru_maxrss=123456))
    assert file_parser._peak_rss_bytes() == 123456



def test_parser_child_rejects_its_own_over_budget_peak_after_actual_extraction(tmp_path, monkeypatch):
    import json
    import os
    from dataclasses import asdict

    from flycanon.core.services.ingestion import file_parser

    source = office(tmp_path / "own-peak.docx")
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "path": str(source), "filename": source.name, "kind": "docx",
        "policy": asdict(DocumentFilePolicy()), "output": str(tmp_path / "result.json"),
        "parent_pid": os.getpid(),
    }))
    monkeypatch.setattr(file_parser, "arm_parent_bound_deadline", lambda seconds, parent: None)
    monkeypatch.setattr(file_parser, "_peak_rss_bytes", lambda: 769 * 1024**2)
    with pytest.raises(ValueError, match="exceeded its memory budget"):
        file_parser._child(request)
    assert not (tmp_path / "result.json").exists()
