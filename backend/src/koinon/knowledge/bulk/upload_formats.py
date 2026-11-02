# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Installed parser hints; byte validation and worker execution remain authoritative."""

from importlib.util import find_spec

from flycanon.core.services.ingestion.loaders import default_registry
from flyquery.core.services.ingestion.format_detect import FORMAT_EXTENSIONS
from flyquery.core.services.ingestion.reader_factory import get_reader, supported_compressions

from koinon.knowledge.bulk.dtos import UploadFormat

_DOCUMENT_DEPENDENCIES = {
    "docx": ("docx",),
    "pptx": ("pptx",),
    "xlsx": ("openpyxl",),
    "pdf": ("pymupdf", "pypdf"),
    "html": ("bs4",),
    "xml": ("lxml",),
    "rtf": ("striprtf",),
    "odt": ("odf",),
    "ods": ("odf",),
    "odp": ("odf",),
    "markdown": (),
    "text": (),
    "csv": (),
    "tsv": (),
    "json": (),
}
_DATASET_DEPENDENCIES = {
    "csv": ("duckdb",),
    "tsv": ("duckdb",),
    "json": ("duckdb",),
    "jsonl": ("duckdb",),
    "parquet": ("pyarrow",),
    "orc": ("pyarrow",),
    "arrow": ("pyarrow",),
    "avro": ("fastavro", "pyarrow"),
    "xlsx": ("python_calamine", "duckdb"),
    "xls": ("python_calamine", "duckdb"),
    "ods": ("python_calamine", "duckdb"),
}


def _installed(dependencies: tuple[str, ...]) -> bool:
    return all(find_spec(name) is not None for name in dependencies)


def upload_formats() -> list[UploadFormat]:
    result = []
    for kind in default_registry().registered_kinds():
        name = kind.value
        # Aggregate, image and transcript loaders require distinct intake paths.
        if name not in _DOCUMENT_DEPENDENCIES:
            continue
        extensions = {"text": [".txt", ".text"], "markdown": [".md", ".markdown"]}.get(name, ["." + name])
        available = _installed(_DOCUMENT_DEPENDENCIES[name])
        result.append(
            UploadFormat(
                mode="document",
                extensions=extensions,
                available=available,
                reason=None if available else "Parser dependencies are unavailable",
            )
        )
    for name, extensions in FORMAT_EXTENSIONS.items():
        available = _installed(_DATASET_DEPENDENCIES[name])
        if available:
            try:
                get_reader(name)
            except ImportError:
                available = False
        result.append(
            UploadFormat(
                mode="dataset",
                extensions=[
                    *extensions,
                    *(
                        extension + "." + compression
                        for extension in extensions
                        for compression in supported_compressions()
                    ),
                ],
                available=available,
                reason=None if available else "Parser dependencies are unavailable",
            )
        )
    return result
