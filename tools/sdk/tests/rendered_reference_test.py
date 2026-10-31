# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Run with documentation requirements installed: verify actual rendered text."""

import string
import sys
import unittest
from html.parser import HTMLParser
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reference.schema import code, literal


class InlineCode(HTMLParser):
    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.values: list[str] = []
        self.current: list[str] = []
        self.cells = 0
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.cells += 1
        if tag == "code":
            self.active = True
            self.current = []

    def handle_data(self, data):
        if self.active:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "code":
            self.values.append("".join(self.current))
            self.active = False


class RenderedReferenceTests(unittest.TestCase):
    def test_nullable_union_and_special_characters_render_exactly_in_tables(self):
        markdown = import_module("markdown")
        values = [
            "QueryParam[str | None]",
            "a|b",
            "`one``two`",
            '<value> & "text"',
            "&amp; &#124;",
            r"\\path|next",
            r"\[x\]|<none>",
            r"\*<value>\_",
            string.punctuation,
        ]
        for value in values:
            with self.subTest(value=value):
                source = (
                    "| Type | Detail |\n| --- | --- |\n| "
                    + code(value)
                    + " | unchanged |"
                )
                parsed = InlineCode(markdown.markdown(source, extensions=["tables"]))
                self.assertEqual(parsed.values, [value])
                self.assertEqual(parsed.cells, 2)

    def test_enum_pattern_and_linked_types_render_exactly_outside_tables(self):
        markdown = import_module("markdown")
        values = ["a|b", "`<item>`", "[A-Z]+|<none>", "&copy;", r"^\w+\.\w+|<none>$"]
        import json

        for value in values:
            with self.subTest(value=value):
                source = (
                    "- Allowed value: "
                    + literal(value)
                    + "\n\n["
                    + code(value)
                    + "](models/example.md)"
                )
                parsed = InlineCode(markdown.markdown(source, extensions=["tables"]))
                self.assertEqual(
                    parsed.values,
                    [
                        json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                        value,
                    ],
                )


if __name__ == "__main__":
    unittest.main()
