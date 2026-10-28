# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pure, bounded private parsing. The worker invokes this module in an isolated child process."""

import base64
import io
import json
import re
from dataclasses import asdict
from hashlib import sha256
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from koinon.knowledge.attachments.settings import AttachmentSettings


class ExtractionFailure(ValueError):
    def __init__(self, message, code="ATTACHMENT_EXTRACTION_FAILED"):
        super().__init__(message)
        self.code = code


TEXT_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".json": "application/json",
    ".html": "text/html",
    ".htm": "text/html",
    ".xml": "application/xml",
}
OFFICE_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def archive_members(content, settings):
    try:
        archive = ZipFile(io.BytesIO(content))
    except BadZipFile as error:
        raise ExtractionFailure("This archive is damaged", "ATTACHMENT_ARCHIVE_INVALID") from error
    members = [value for value in archive.infolist() if not value.is_dir()]
    if len(members) > 1000 or sum(value.file_size for value in members) > settings.max_expanded_bytes:
        archive.close()
        raise ExtractionFailure(
            "Archive expansion exceeds the configured limit", "ATTACHMENT_EXPANSION_LIMIT"
        )
    for value in members:
        path = PurePosixPath(value.filename)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in value.filename
            or any(ord(char) < 32 for char in value.filename)
            or value.flag_bits & 1
            or (value.external_attr >> 16) & 0o170000 == 0o120000
        ):
            archive.close()
            raise ExtractionFailure(
                "Archive contains unsafe or encrypted entries", "ATTACHMENT_ARCHIVE_UNSAFE"
            )
    return archive, members


def strict_text(content):
    try:
        result = content.decode("utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    except UnicodeError as error:
        raise ExtractionFailure(
            "Save this text file as UTF-8 or UTF-16", "ATTACHMENT_TEXT_ENCODING"
        ) from error
    if "\x00" in result or any(ord(char) < 32 and char not in "\n\r\t\f" for char in result):
        raise ExtractionFailure("This file contains binary control characters", "ATTACHMENT_TEXT_ENCODING")
    return result


def text_result(sections, mime, settings, *, page_count=None, kind="document", warnings=()):
    from pyfly.agentic.content.chunking import TextChunker

    text, chunks = "", []
    chunker = TextChunker(chunk_size=384, chunk_overlap=0)
    for section in sections:
        body = section["text"].strip()
        if not body:
            continue
        path = section.get("section_path") or []
        heading = "Section: " + " > ".join(path) + "\n" if path else ""
        base = len(text) + (2 if text else 0) + len(heading)
        text += ("\n\n" if text else "") + heading + body
        if len(text.encode()) > settings.max_text_bytes:
            raise ExtractionFailure("Extracted text exceeds its configured limit", "ATTACHMENT_TEXT_LIMIT")
        spans = list(re.finditer(r"\S+", body))
        cursor = 0
        for native in chunker.chunk(body):
            count = len(re.findall(r"\S+", native.content))
            start, end = spans[cursor].start(), spans[cursor + count - 1].end()
            cursor += count
            # Native token chunking normalizes whitespace; source offsets use the original normalized section.
            for bounded_start in range(start, end, 2000):
                bounded_end = min(end, bounded_start + 2000)
                value = body[bounded_start:bounded_end]
                chunks.append(
                    {
                        "text": value,
                        "char_start": base + bounded_start,
                        "char_end": base + bounded_end,
                        "page": section.get("page"),
                        "section_path": section.get("section_path", []),
                        "sha256": sha256(value.encode()).hexdigest(),
                    }
                )
                if len(chunks) > settings.max_chunks:
                    raise ExtractionFailure(
                        "Extracted chunks exceed their configured limit", "ATTACHMENT_CHUNK_LIMIT"
                    )
    if not chunks:
        raise ExtractionFailure(
            "No readable text was found; OCR is not configured", "ATTACHMENT_TEXT_UNAVAILABLE"
        )
    return {
        "kind": kind,
        "media_type": mime,
        "normalized_media_type": "text/plain",
        "text": text,
        "chunks": chunks,
        "page_count": page_count,
        "warnings": list(warnings),
    }


def extract(content, filename, declared_type, settings: AttachmentSettings):
    settings.validate()
    if not content or len(content) > settings.max_file_bytes:
        raise ExtractionFailure("File exceeds the configured byte limit", "ATTACHMENT_TOO_LARGE")
    suffix = PurePosixPath(filename).suffix.lower()
    mime = {
        **TEXT_TYPES,
        **OFFICE_TYPES,
        **IMAGE_TYPES,
        ".pdf": "application/pdf",
        ".zip": "application/zip",
    }.get(suffix)
    if mime is None:
        raise ExtractionFailure("Choose a supported file extension", "ATTACHMENT_FORMAT_UNSUPPORTED")
    claimed = (declared_type or "").split(";", 1)[0].strip().lower()
    if claimed and claimed not in {mime, "application/octet-stream", "text/plain", "application/zip"}:
        raise ExtractionFailure(
            "The declared media type does not match the file", "ATTACHMENT_MEDIA_MISMATCH"
        )
    if suffix in IMAGE_TYPES:
        from PIL import Image, ImageOps

        if len(content) > settings.max_image_bytes:
            raise ExtractionFailure("Image exceeds the configured byte limit", "ATTACHMENT_IMAGE_TOO_LARGE")
        try:
            with Image.open(io.BytesIO(content)) as probe:
                if Image.MIME.get(probe.format or "") != mime:
                    raise ExtractionFailure(
                        "Image bytes do not match the selected format", "ATTACHMENT_MEDIA_MISMATCH"
                    )
                if probe.width * probe.height > settings.max_image_pixels:
                    raise ExtractionFailure(
                        "Image exceeds the configured pixel limit", "ATTACHMENT_IMAGE_TOO_LARGE"
                    )
                probe.verify()
            with Image.open(io.BytesIO(content)) as image:
                if getattr(image, "n_frames", 1) != 1:
                    raise ExtractionFailure(
                        "Use a still image rather than an animation", "ATTACHMENT_IMAGE_ANIMATED"
                    )
                normalized = ImageOps.exif_transpose(image).convert("RGB")
                output = io.BytesIO()
                normalized.save(output, format="PNG")
                if output.tell() > 16 * 1024 * 1024:
                    raise ExtractionFailure(
                        "Normalized image exceeds the model byte ceiling", "ATTACHMENT_IMAGE_TOO_LARGE"
                    )
                return {
                    "kind": "image",
                    "media_type": mime,
                    "normalized_media_type": "image/png",
                    "data": base64.b64encode(output.getvalue()).decode(),
                    "chunks": [],
                    "text": "",
                    "image_width": normalized.width,
                    "image_height": normalized.height,
                    "page_count": None,
                    "warnings": ["Selected-model image support must be verified separately"],
                }
        except ExtractionFailure:
            raise
        except Exception as error:
            raise ExtractionFailure(
                "The image could not be safely decoded", "ATTACHMENT_IMAGE_INVALID"
            ) from error
    if suffix == ".zip":
        archive, members = archive_members(content, settings)
        try:
            if len(members) > settings.max_artifacts:
                raise ExtractionFailure("Archive has too many files", "ATTACHMENT_ARTIFACT_LIMIT")
            sections = []
            for member in members:
                if PurePosixPath(member.filename).suffix.lower() == ".zip":
                    raise ExtractionFailure("Nested archives are unsupported", "ATTACHMENT_ARCHIVE_UNSAFE")
                child = extract(archive.read(member), member.filename, None, settings)
                if child["kind"] != "document":
                    raise ExtractionFailure(
                        "Bundles currently require readable documents", "ATTACHMENT_BUNDLE_KIND"
                    )
                for chunk in child["chunks"]:
                    sections.append(
                        {
                            "text": chunk["text"],
                            "page": chunk.get("page"),
                            "section_path": [member.filename, *chunk["section_path"]],
                        }
                    )
            return text_result(sections, mime, settings, kind="bundle")
        finally:
            archive.close()
    if suffix in OFFICE_TYPES:
        archive, _ = archive_members(content, settings)
        archive.close()
    if suffix in TEXT_TYPES:
        decoded = strict_text(content)
        if suffix == ".json":
            try:
                json.loads(
                    decoded,
                    parse_float=str,
                    parse_int=str,
                    parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
                )
            except ValueError as error:
                raise ExtractionFailure(
                    "This JSON document is invalid", "ATTACHMENT_DOCUMENT_INVALID"
                ) from error
        if suffix in {".xml", ".html", ".htm"} and re.search(r"<!\s*(DOCTYPE|ENTITY)", decoded, re.I):
            raise ExtractionFailure("External declarations are unsupported", "ATTACHMENT_XML_UNSAFE")
        if suffix not in {".html", ".htm", ".xml", ".md", ".markdown"}:
            return text_result([{"text": decoded}], mime, settings)
        content = decoded
    from flycanon.core.services.ingestion import loaders

    if suffix == ".pdf":
        import pymupdf

        try:
            with pymupdf.open(stream=content, filetype="pdf") as pdf:
                if pdf.needs_pass or pdf.page_count > settings.max_pages:
                    raise ExtractionFailure(
                        "PDF is encrypted or exceeds the page limit", "ATTACHMENT_PDF_LIMIT"
                    )

            class NoAmbientOCR(loaders.PdfLoader):
                def _ocr_pages(self, pdf_bytes, page_indices):
                    return {}

            document = NoAmbientOCR().load(content)
            if len(document.sections) != document.page_count:
                raise ExtractionFailure(
                    "Scanned pages require an explicitly configured OCR service", "ATTACHMENT_OCR_REQUIRED"
                )
        except ExtractionFailure:
            raise
        except Exception as error:
            raise ExtractionFailure("This PDF cannot be safely read", "ATTACHMENT_PDF_INVALID") from error
    else:
        loader = {
            ".docx": loaders.DocxLoader,
            ".xlsx": loaders.XlsxLoader,
            ".pptx": loaders.PptxLoader,
            ".md": loaders.MarkdownLoader,
            ".markdown": loaders.MarkdownLoader,
            ".html": loaders.HtmlLoader,
            ".htm": loaders.HtmlLoader,
            ".xml": loaders.XmlLoader,
        }[suffix]
        document = loader().load(content, filename=filename)
    return text_result(
        [
            {"text": section.body, "page": section.page, "section_path": section.path}
            for section in document.sections
        ],
        mime,
        settings,
        page_count=document.page_count,
    )


def child_main():
    import resource
    import socket
    import sys

    def no_network(*args, **kwargs):
        raise RuntimeError("Private parsers cannot open network connections")

    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    socket.create_connection = no_network
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    except ValueError:
        if sys.platform != "darwin":
            raise
        # Darwin does not implement this limit; the parent also fences observed child RSS.
    try:
        value = json.loads(sys.stdin.buffer.read(90 * 1024 * 1024))
        result = extract(
            base64.b64decode(value["content"], validate=True),
            value["filename"],
            value["media_type"],
            AttachmentSettings(**value["settings"]),
        )
        response = {"result": result}
    except Exception as error:
        response = {
            "error": {
                "code": str(getattr(error, "code", "ATTACHMENT_EXTRACTION_FAILED"))[:64],
                "message": str(error)[:500]
                if isinstance(error, ExtractionFailure)
                else "Private parsing failed; verify the format and installed extractor prerequisites",
            }
        }
    sys.stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")))


def extraction_input(content, row, settings):
    values = asdict(settings)
    values["storage_root"] = None
    return json.dumps(
        {
            "content": base64.b64encode(content).decode(),
            "filename": row.filename,
            "media_type": row.declared_media_type,
            "settings": values,
        }
    ).encode()


if __name__ == "__main__":
    child_main()
