# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded file-to-text parsing. Originals remain files, never child stdin/DB payloads."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import resource
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import psutil
from koinon_storage.client_lifecycle import ClientLifecycle
from koinon_storage.process_guard import arm_parent_bound_deadline


@dataclass(frozen=True)
class DocumentFilePolicy:
    raw_max_bytes: int = 128 * 1024**2
    expanded_max_bytes: int = 256 * 1024**2
    xml_max_bytes: int = 32 * 1024**2
    scratch_max_bytes: int = 1024**3
    child_rss_max_bytes: int = 768 * 1024**2
    wall_seconds: int = 120
    text_max_bytes: int = 16 * 1024**2
    chunks_max: int = 4096
    archive_members_max: int = 4096

    def __post_init__(self):
        for name, value in asdict(self).items():
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} requires a positive integer")
        maxima = {
            "raw_max_bytes": 128 * 1024**2,
            "expanded_max_bytes": 256 * 1024**2,
            "xml_max_bytes": 32 * 1024**2,
            "scratch_max_bytes": 1024**3,
            "child_rss_max_bytes": 768 * 1024**2,
            "wall_seconds": 120,
            "text_max_bytes": 16 * 1024**2,
            "chunks_max": 4096,
            "archive_members_max": 4096,
        }
        if any(getattr(self, name) > maximum for name, maximum in maxima.items()):
            raise ValueError("Document parser exceeds its bounded file profile")


@dataclass(frozen=True)
class ParsedDocumentFile:
    text: str
    kind: str
    raw_bytes: int
    peak_rss_bytes: int
    metadata: dict
    sections: list[dict] = field(default_factory=list)


def _rss(pid):
    try:
        process = psutil.Process(pid)
        return sum(
            item.memory_info().rss
            for item in (process, *process.children(recursive=True))
            if item.is_running()
        )
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return 0


async def parse_document_file(path, *, filename, policy: DocumentFilePolicy):
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= policy.raw_max_bytes:
        raise ValueError("Document exceeds the admitted regular-file byte bound")
    # Include the original spool and bounded output, even though the spool is caller-owned.
    if path.stat().st_size + policy.text_max_bytes * 2 > policy.scratch_max_bytes:
        raise ValueError("Document exceeds the parser scratch budget")
    with tempfile.TemporaryDirectory(prefix="koinon-parse-", dir=path.parent) as directory:
        folder = Path(directory)
        specification = folder / "request.json"
        output = folder / "result.json"
        specification.write_text(
            json.dumps(
                {
                    "path": str(path),
                    "filename": filename,
                    "policy": asdict(policy),
                    "output": str(output),
                    "parent_pid": os.getpid(),
                }
            )
        )
        env = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "LANG", "LC_ALL", "PYTHONPATH", "FLYCANON_PDF_OCR_ENGINE", "FLYCANON_OCR_LANG"}
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            __name__,
            str(specification),
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=False,
        )
        waiting = asyncio.create_task(process.wait())
        started = time.monotonic()
        peak = 0
        try:
            while process.returncode is None:
                peak = max(peak, _rss(process.pid))
                if peak > policy.child_rss_max_bytes or time.monotonic() - started > policy.wall_seconds:
                    raise ValueError("Document parser exceeded its memory or time budget")
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(asyncio.shield(waiting), timeout=0.05)
            if (
                process.returncode
                or not output.exists()
                or output.stat().st_size > policy.text_max_bytes * 2 + 65536
            ):
                raise ValueError("Document could not be parsed within the configured resource policy")
            result = json.loads(output.read_text())
            if (
                result["peak_rss_bytes"] > policy.child_rss_max_bytes
                or len(result["text"].encode()) > policy.text_max_bytes
            ):
                raise ValueError("Document parser exceeded its registered output or memory budget")
            return ParsedDocumentFile(**result)
        finally:
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    parent = psutil.Process(process.pid)
                    for child in parent.children(recursive=True):
                        with contextlib.suppress(psutil.NoSuchProcess):
                            child.kill()
                    process.kill()
            await ClientLifecycle._await_task(waiting)


def _child(specification):
    request = json.loads(Path(specification).read_text())
    policy = DocumentFilePolicy(**request["policy"])
    arm_parent_bound_deadline(policy.wall_seconds, request["parent_pid"])
    path = Path(request["path"])
    suffix = Path(request["filename"] or "").suffix.lower()
    if suffix in {".docx", ".pptx"}:
        kind = suffix[1:]
        from flycanon.core.services.ingestion.office_package import extract_office

        text, sections, metadata = extract_office(path, kind, policy)
    else:
        from flycanon.core.mappers.intake_mapper import _render_document
        from flycanon.core.services.ingestion.loaders import default_registry
        from flycanon.interfaces.enums import SourceKind

        kind = suffix.lstrip(".")
        try:
            selected = SourceKind(kind)
        except ValueError:
            selected = SourceKind.text
        loader = default_registry().get(selected)
        if loader is None:
            raise ValueError("This document format has no installed parser")
        document = loader.load(path.read_bytes(), filename=request["filename"])
        text = _render_document(document, artifact_label=request["filename"], index=0)
        sections = [asdict(section) for section in document.sections]
        metadata = {
            "parser": "bounded-format-loader",
            "extraction_coverage": "configured_loader_text",
            "image_interpretation": "not_independently_verified",
            "original_media": "retained",
        }
    if len(text.encode()) > policy.text_max_bytes:
        raise ValueError("Document text exceeds its configured byte limit")
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = int(usage if sys.platform == "darwin" else usage * 1024)
    if peak > policy.child_rss_max_bytes:
        raise ValueError("Document parser exceeded its memory budget")
    rendered = json.dumps(
        {
            "text": text,
            "kind": kind,
            "raw_bytes": path.stat().st_size,
            "peak_rss_bytes": peak,
            "metadata": metadata,
            "sections": sections,
        },
        ensure_ascii=False,
    )
    if len(rendered.encode()) > min(
        policy.text_max_bytes * 2 + 65536, policy.scratch_max_bytes - path.stat().st_size
    ):
        raise ValueError("Document parser output exceeds its scratch budget")
    Path(request["output"]).write_text(rendered)


if __name__ == "__main__":
    _child(sys.argv[1])
