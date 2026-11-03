# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Measure real bounded Office parsing without a database or model provider."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import importlib.metadata
import inspect
import json
import platform
import re
import resource
import subprocess
import sys
import time
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from flycanon.core.services.ingestion import file_parser, loaders, office_package

CASES = {
    "docx": (100, 1000, 4000),
    "xlsx": (1000, 10000, 50000),
    "csv": (1000, 10000, 50000),
    "pptx": (10, 100, 500),
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def marker(index: int) -> str:
    return f"Evidence-{index:08d}-café"


def make_fixture(path: Path, kind: str, count: int) -> None:
    if kind not in CASES or not 1 <= count <= max(CASES[kind]):
        raise ValueError("Unsupported local fixture size")
    if path.exists():
        raise FileExistsError(path)
    if kind == "docx":
        from docx import Document

        document = Document()
        for index in range(count):
            document.add_paragraph(marker(index) + ": " + "Retained organization knowledge. " * 8)
        document.save(str(path))
    elif kind == "pptx":
        from pptx import Presentation
        from pptx.util import Inches

        deck = Presentation()
        for index in range(count):
            slide = deck.slides.add_slide(deck.slide_layouts[6])
            frame = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(5)).text_frame
            frame.text = marker(index) + ": " + "Retained organization knowledge. " * 8
        deck.save(str(path))
    elif kind == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("Evidence")
        sheet.append(["Evidence", "Region", "Revenue", "Year"])
        for index in range(count):
            sheet.append([marker(index), "North", index * 17, 2026])
        workbook.save(path)
        workbook.close()
    else:
        with path.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["Evidence", "Region", "Revenue", "Year"])
            for index in range(count):
                writer.writerow([marker(index), "North", index * 17, 2026])


def child_cpu_seconds() -> float:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


async def measure(path: Path, count: int) -> dict:
    before_hash = digest(path)
    raw_bytes = path.stat().st_size
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            expanded_bytes = sum(item.file_size for item in archive.infolist())
    else:
        expanded_bytes = raw_bytes
    policy = file_parser.DocumentFilePolicy()
    cpu_before, children_before = time.process_time(), child_cpu_seconds()
    started = time.perf_counter()
    parsed = await file_parser.parse_document_file(path, filename=path.name, policy=policy)
    elapsed = time.perf_counter() - started
    parent_cpu = time.process_time() - cpu_before
    child_cpu = child_cpu_seconds() - children_before
    if digest(path) != before_hash:
        raise RuntimeError("Parser changed the original fixture")
    found = re.findall(r"Evidence-(\d{8})-café", parsed.text)
    if len(found) != count or {int(value) for value in found} != set(range(count)):
        raise RuntimeError("Parser lost or duplicated evidence markers")
    if list(path.parent.glob("koinon-parse-*")):
        raise RuntimeError("Parser left scratch directories behind")
    if parsed.raw_bytes != raw_bytes:
        raise RuntimeError("Parser reported a different original size")
    return {
        "kind": parsed.kind,
        "units": count,
        "original_sha256": before_hash,
        "original_bytes": raw_bytes,
        "expanded_bytes": expanded_bytes,
        "text_bytes": len(parsed.text.encode()),
        "sections": len(parsed.sections),
        "markers_verified": count,
        "elapsed_seconds": elapsed,
        "parent_cpu_seconds": parent_cpu,
        "child_cpu_seconds": child_cpu,
        "child_peak_rss_bytes": parsed.peak_rss_bytes,
        "policy": asdict(policy),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--formats", nargs="+", choices=list(CASES), default=list(CASES))
    parser.add_argument("--sample", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--count", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.sample is not None:
        if args.count is None or not 1 <= args.count <= 50000:
            parser.error("A bounded sample count is required")
        print(json.dumps(asyncio.run(measure(args.sample, args.count))))
        return
    if args.output is None or not 1 <= args.repeats <= 5:
        parser.error("Supply --output and between one and five repetitions")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = {}
    for module in (file_parser, office_package, loaders):
        filename = inspect.getsourcefile(module)
        if filename is None:
            raise RuntimeError("Cannot identify the measured implementation")
        sources[module.__name__] = digest(Path(filename))
    repository = Path(__file__).resolve().parents[2]
    manifest = {
        "started_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "pyfly": importlib.metadata.version("pyfly"),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True,
        ).strip(),
        "working_tree_dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repository, text=True,
        ).strip()),
        "source_sha256": sources,
        "probe_sha256": digest(Path(__file__)),
        "repeats": args.repeats,
        "formats": args.formats,
        "scope": "Native document parsing only; no upload, queue, database, embeddings or chat",
        "cache_note": "Fresh parent and parser child per sample; OS caches and shared-host load uncontrolled",
        "samples": [],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    total_bytes = 0
    for kind in dict.fromkeys(args.formats):
        for count in CASES[kind]:
            path = output / f"evidence-{count}.{kind}"
            make_fixture(path, kind, count)
            total_bytes += path.stat().st_size
            if total_bytes > 512 * 1024**2:
                raise RuntimeError("Local fixture storage budget exceeded")
            for repeat in range(args.repeats):
                run = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "--sample", str(path),
                     "--count", str(count)],
                    capture_output=True, text=True, timeout=150, check=False,
                )
                stem = f"{kind}-{count}-{repeat + 1}"
                (output / f"{stem}.stderr.log").write_text(run.stderr)
                if run.returncode:
                    (output / f"{stem}.failed.log").write_text(run.stdout)
                    raise RuntimeError(f"Parser sample failed: {stem}; diagnostic retained")
                result = json.loads(run.stdout)
                (output / f"{stem}.json").write_text(json.dumps(result, indent=2) + "\n")
                manifest["samples"].append({
                    "receipt": f"{stem}.json", "sha256": digest(output / f"{stem}.json"),
                })
                print(f"{stem}: {result['elapsed_seconds']:.3f}s, all {count} markers retained", flush=True)
    manifest["completed_at"] = datetime.now(UTC).isoformat()
    manifest["fixture_bytes"] = total_bytes
    (output / "complete.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
