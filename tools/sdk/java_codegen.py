# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared deterministic Java generation and format-independent drift checking."""

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "sdk/java"
PARSER = argparse.ArgumentParser(description=__doc__)
PARSER.add_argument(
    "--check",
    action="store_true",
    help="Fail if generated Java tokens or fixtures differ",
)
ARGS = PARSER.parse_args()
# Preserve string/character literals and comments while ignoring formatter-only whitespace.
JAVA_TOKEN = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/|\w+|[^\s]'
)


def emit(path: Path, content: str) -> None:
    if path.suffix == ".java":
        imports = re.findall(r"^import ([^;]+);\n", content, re.MULTILINE)
        body = re.sub(r"^import [^;]+;\n", "", content, flags=re.MULTILINE)
        used = [
            item
            for item in imports
            if item.endswith(".*")
            or re.search(r"\b" + re.escape(item.rsplit(".", 1)[-1]) + r"\b", body)
        ]
        package_end = body.index(";", body.index("package ")) + 1
        content = (
            body[:package_end]
            + "\n"
            + "".join("import " + item + ";\n" for item in sorted(used))
            + body[package_end:]
        )
    if ARGS.check:
        current = path.read_text() if path.exists() else ""
        equal = (
            JAVA_TOKEN.findall(current) == JAVA_TOKEN.findall(content)
            if path.suffix == ".java"
            else current == content
        )
        if not equal:
            raise SystemExit(
                f"Generated output is stale: {path.relative_to(ROOT.parents[1])}"
            )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
