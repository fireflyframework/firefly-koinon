# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Readable JSON Schema types, constraints and reference pages."""

from __future__ import annotations

import json
import re
from typing import Any

Schema = dict[str, Any]
LICENSE = "<!-- Copyright 2026 Firefly Software Foundation -->\n<!-- SPDX-License-Identifier: Apache-2.0 -->\n"


def code(value: object) -> str:
    text = str(value).replace("\n", " ")
    if any(character in text for character in "|`<>&"):
        escaped = "".join(
            character
            if character.isalnum() or character == " "
            else f"&#{ord(character)};"
            for character in text
        )
        return "<code>" + escaped + "</code>"
    return "`" + text + "`"


def literal(value: object) -> str:
    return code(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class SchemaReference:
    def __init__(self, document: Schema):
        self.definitions: dict[str, Schema] = document["$defs"]
        self.aliases: dict[str, list[str]] = {name: [] for name in self.definitions}
        filenames: set[str] = set()
        for name in self.definitions:
            filename = self.filename(name)
            if not slug(name) or filename in filenames:
                raise ValueError(f"Duplicate or empty model filename: {name}")
            filenames.add(filename)
        for alias, value in document.get("models", {}).items():
            self.aliases[self.ref_name(value["$ref"])].append(alias)
        self.validate(document)

    def filename(self, name: str) -> str:
        return slug(name) + ".md"

    def ref_name(self, ref: str) -> str:
        if not ref.startswith("#/$defs/"):
            raise ValueError(f"Unsupported schema reference: {ref}")
        name = ref.removeprefix("#/$defs/").replace("~1", "/").replace("~0", "~")
        if name not in self.definitions:
            raise ValueError(f"Unknown schema reference: {ref}")
        return name

    def validate(self, value: Any) -> None:
        if not isinstance(value, dict):
            return
        if "$ref" in value:
            self.ref_name(value["$ref"])
        for keyword in ("$defs", "properties", "patternProperties", "dependentSchemas"):
            for schema in value.get(keyword, {}).values():
                self.validate(schema)
        for keyword in ("anyOf", "oneOf", "allOf", "prefixItems"):
            for schema in value.get(keyword, []):
                self.validate(schema)
        for keyword in (
            "items",
            "additionalProperties",
            "unevaluatedProperties",
            "unevaluatedItems",
            "contains",
            "propertyNames",
            "not",
            "if",
            "then",
            "else",
        ):
            if keyword in value:
                self.validate(value[keyword])
        for ref in value.get("discriminator", {}).get("mapping", {}).values():
            self.ref_name(ref)

    def name_link(self, name: str, prefix: str = "") -> str:
        if name == "void":
            return "No response body"
        key = name if name in self.definitions else re.sub(r"[^a-zA-Z0-9_]", "_", name)
        if key not in self.definitions:
            raise ValueError(f"Unknown operation schema: {name}")
        return f"[{code(name)}]({prefix}{self.filename(key)})"

    def describe(self, schema: Any, prefix: str = "") -> str:
        if schema is True or schema == {}:
            return "Any JSON value"
        if schema is False:
            return "No value permitted"
        if "$ref" in schema:
            return self.name_link(self.ref_name(schema["$ref"]), prefix)
        for union in ("anyOf", "oneOf", "allOf"):
            if union in schema:
                join = " or " if union != "allOf" else " and "
                return join.join(self.describe(item, prefix) for item in schema[union])
        kind = schema.get("type")
        if isinstance(kind, list):
            return " or ".join(code(value) for value in kind)
        if kind == "array":
            return "Array of " + self.describe(schema.get("items", {}), prefix)
        if kind == "object":
            additional = schema.get("additionalProperties", True)
            if isinstance(additional, dict):
                return "Map of string keys to " + self.describe(additional, prefix)
            return code("object")
        if kind:
            return code(kind)
        if "const" in schema:
            return literal(schema["const"])
        if "enum" in schema:
            return " or ".join(literal(item) for item in schema["enum"])
        return "Any JSON value"

    def constraints(self, schema: Any, context: str = "") -> list[str]:
        if not isinstance(schema, dict):
            return []
        rows: list[str] = []
        labels = {
            "minimum": "Minimum",
            "maximum": "Maximum",
            "exclusiveMinimum": "Greater than",
            "exclusiveMaximum": "Less than",
            "multipleOf": "Multiple of",
            "minLength": "Minimum length",
            "maxLength": "Maximum length",
            "pattern": "Pattern",
            "format": "Format",
            "minItems": "Minimum items",
            "maxItems": "Maximum items",
            "uniqueItems": "Unique items",
            "minProperties": "Minimum properties",
            "maxProperties": "Maximum properties",
            "contentEncoding": "Content encoding",
            "contentMediaType": "Content media type",
            "writeOnly": "Write only",
            "readOnly": "Read only",
            "deprecated": "Deprecated",
        }
        for key, label in labels.items():
            if key in schema:
                rows.append(f"{context}{label}: {literal(schema[key])}")
        if "enum" in schema:
            rows.append(
                context
                + "Allowed values: "
                + ", ".join(literal(v) for v in schema["enum"])
            )
        if "const" in schema:
            rows.append(context + "Exact value: " + literal(schema["const"]))
        if "additionalProperties" in schema:
            extra = schema["additionalProperties"]
            detail = (
                "not permitted"
                if extra is False
                else "permitted"
                if extra is True
                else self.describe(extra)
            )
            rows.append(context + "Additional properties: " + detail)
        if schema.get("description"):
            rows.append(context + str(schema["description"]).replace("\n", " "))
        if "discriminator" in schema:
            discriminator = schema["discriminator"]
            rows.append(
                context + "Discriminator field: " + code(discriminator["propertyName"])
            )
            for value, ref in discriminator.get("mapping", {}).items():
                rows.append(
                    f"{context}For {literal(value)}: {self.name_link(self.ref_name(ref))}"
                )
        for keyword in ("anyOf", "oneOf", "allOf"):
            for index, branch in enumerate(schema.get(keyword, []), 1):
                label = f"{keyword} branch {index} ({self.describe(branch)}): "
                rows.extend(self.constraints(branch, context + label))
        if isinstance(schema.get("additionalProperties"), dict):
            rows.extend(
                self.constraints(
                    schema["additionalProperties"], context + "Each map value: "
                )
            )
        if "items" in schema:
            rows.extend(self.constraints(schema["items"], context + "Each item: "))
        return rows

    def render_model(self, name: str) -> str:
        schema = self.definitions[name]
        lines = [LICENSE, f"# {name}", "", "[All wire models](index.md)", ""]
        if self.aliases[name]:
            lines += [
                "Model aliases: "
                + ", ".join(code(v) for v in sorted(self.aliases[name]))
                + ".",
                "",
            ]
        else:
            lines += [
                "Supporting wire definition. It is not a separate public model alias in the canonical manifest.",
                "",
            ]
        lines += ["Type: " + self.describe(schema) + ".", ""]
        if "properties" in schema:
            lines += [
                "## Fields",
                "",
                "Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.",
                "",
                "| Field | Type | Required | Default |",
                "| --- | --- | --- | --- |",
            ]
            for field, value in schema["properties"].items():
                default = (
                    literal(value["default"]) if "default" in value else "Not specified"
                )
                lines.append(
                    f"| {code(field)} | {self.describe(value)} | {'Yes' if field in schema.get('required', []) else 'No'} | {default} |"
                )
        constraints = self.constraints(schema)
        if constraints:
            lines += ["", "## Model constraints", ""] + [
                "- " + row for row in constraints
            ]
        fields = [
            (field, self.constraints(value))
            for field, value in schema.get("properties", {}).items()
        ]
        if any(rows for _, rows in fields):
            lines += ["", "## Field constraints", ""]
            for field, rows in fields:
                if rows:
                    lines += [f"### {field}", ""] + ["- " + row for row in rows] + [""]
        lines += [
            "",
            "## Exact JSON Schema",
            "",
            "This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.",
            "",
            '??? note "Complete JSON Schema"',
            "",
            "    ```json",
            "\n".join(
                "    " + line
                for line in json.dumps(
                    schema, indent=2, ensure_ascii=False
                ).splitlines()
            ),
            "    ```",
            "",
        ]
        return "\n".join(lines)

    def render_all(self) -> dict[str, str]:
        lines = [
            LICENSE,
            "# Wire models",
            "",
            f"The canonical schema contains {len(self.definitions)} definitions and {sum(len(v) for v in self.aliases.values())} named model aliases. Supporting definitions are included so every schema reference can be followed. Language-specific generated names can differ from wire names; consult the SDK imports in the workflow guides.",
            "",
            "Each page lists field presence, nullability, defaults and validation constraints. The downloadable [complete schema](../sdk-schemas.json) remains the machine-readable contract.",
            "",
        ]
        letters = sorted({name[0].upper() for name in self.definitions})
        lines += [" ".join(f"[{letter}](#{letter.lower()})" for letter in letters), ""]
        for letter in letters:
            lines += [f"## {letter}", ""]
            lines += [
                f"- [{code(name)}]({self.filename(name)})"
                for name in sorted(self.definitions)
                if name[0].upper() == letter
            ]
            lines += [""]
        return {
            "models/index.md": "\n".join(lines),
            **{
                f"models/{self.filename(name)}": self.render_model(name)
                for name in sorted(self.definitions)
            },
        }
