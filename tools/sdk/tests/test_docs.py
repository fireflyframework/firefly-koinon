# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reference coverage and rendering contracts; no backend imports or services."""

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/sdk"))
spec = importlib.util.spec_from_file_location("sdk_docs", ROOT / "tools/sdk/docs.py")
assert spec and spec.loader
docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs)


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / "sdk/contract/operations.json").read_text())
        self.schemas = json.loads((ROOT / "sdk/contract/schemas.json").read_text())

    def test_every_operation_and_definition_has_browsable_reference(self):
        self.assertTrue(
            callable(getattr(docs, "build_reference", None)),
            "The generator must create browsable operation and schema reference pages",
        )
        outputs = docs.build_reference(self.contract, self.schemas)
        api = "\n".join(v for k, v in outputs.items() if k.startswith("api/"))
        for op in self.contract["operations"]:
            self.assertEqual(api.count(f"<!-- operation: {op['operation']} -->"), 1)
        model_pages = {
            k: v
            for k, v in outputs.items()
            if k.startswith("models/") and k != "models/index.md"
        }
        self.assertEqual(len(model_pages), len(self.schemas["$defs"]))
        for name in self.schemas["$defs"]:
            self.assertIn(f"[`{name}`]", outputs["models/index.md"])


class RenderingContracts(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / "sdk/contract/operations.json").read_text())
        self.schemas = json.loads((ROOT / "sdk/contract/schemas.json").read_text())

    def test_operation_defaults_headers_and_multiple_success_statuses_are_exact(self):
        output = docs.build_reference(self.contract, self.schemas)
        audit = output["api/platform.md"]
        self.assertIn("| `page` | query | `QueryParam[int]` | No | `1` |", audit)
        self.assertIn('| `q` | query | `QueryParam[str]` | No | `""` |', audit)
        self.assertIn(
            "| `subject` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |",
            audit,
        )
        self.assertIn(
            "Idempotency-Key (required; caller-supplied stable operation key)",
            output["api/curated-knowledge.md"],
        )
        self.assertIn(
            "| Success status | `200`, `202` |", output["api/curated-knowledge.md"]
        )
        self.assertIn("[`Page[AuditEvent]`](../models/page-auditevent.md)", audit)
        self.assertIn("X-Koinon-Source-Version", output["api/sources.md"])

    def test_required_nullable_defaults_and_nested_constraints_are_readable(self):
        sample = {
            "$defs": {
                "Example": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["required_null"],
                    "properties": {
                        "required_null": {
                            "anyOf": [
                                {"type": "string", "maxLength": 4},
                                {"type": "null"},
                            ]
                        },
                        "zero": {"type": "integer", "minimum": 0, "default": 0},
                        "off": {"type": "boolean", "default": False},
                        "maybe": {"type": ["string", "null"], "default": None},
                        "items": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["a|b", "c"]},
                            "maxItems": 2,
                        },
                    },
                }
            },
            "models": {"Example": {"$ref": "#/$defs/Example"}},
        }
        from reference import SchemaReference

        page = SchemaReference(sample).render_all()["models/example.md"]
        self.assertIn(
            "| `required_null` | `string` or `null` | Yes | Not specified |", page
        )
        self.assertIn("| `zero` | `integer` | No | `0` |", page)
        self.assertIn("| `off` | `boolean` | No | `false` |", page)
        self.assertIn("| `maybe` | `string` or `null` | No | `null` |", page)
        self.assertIn("Maximum length: `4`", page)
        self.assertIn(
            'Each item: Allowed values: <code>&#34;a&#124;b&#34;</code>, `"c"`', page
        )
        self.assertIn("Additional properties: not permitted", page)
        self.assertIn('"maxItems": 2', page)

    def test_discriminator_branches_are_linked_without_fabricated_example(self):
        from reference import SchemaReference

        sample = {
            "$defs": {
                "Choice": {
                    "oneOf": [{"$ref": "#/$defs/A"}],
                    "discriminator": {
                        "propertyName": "kind",
                        "mapping": {"a": "#/$defs/A"},
                    },
                },
                "A": {"type": "object", "properties": {"kind": {"const": "a"}}},
            },
            "models": {},
        }
        output = SchemaReference(sample).render_all()
        self.assertIn("Discriminator field: `kind`", output["models/choice.md"])
        self.assertIn('For `"a"`: [`A`](a.md)', output["models/choice.md"])
        self.assertIn(
            "schema definition, not an example request", output["models/choice.md"]
        )

    def test_incomplete_or_ambiguous_metadata_fails_closed(self):
        from reference import SchemaReference

        bad = copy.deepcopy(self.contract)
        bad["operations"][0]["sdk_java"] = None
        with self.assertRaises(ValueError):
            docs.build_reference(bad, self.schemas)
        bad = copy.deepcopy(self.contract)
        bad["operations"][0]["operation"] = "UnknownController.call"
        with self.assertRaisesRegex(ValueError, "Unclassified"):
            docs.build_reference(bad, self.schemas)
        bad = copy.deepcopy(self.contract)
        bad["canonical_operation_count"] -= 1
        with self.assertRaisesRegex(ValueError, "count"):
            docs.build_reference(bad, self.schemas)
        with self.assertRaisesRegex(ValueError, "Unknown schema"):
            SchemaReference({"$defs": {"A": {"$ref": "#/$defs/Missing"}}, "models": {}})
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            SchemaReference({"$defs": {"A_B": {}, "A-B": {}}, "models": {}})

    def test_compatibility_operations_remain_separate_and_keep_revision_guidance(self):
        outputs = docs.build_reference(self.contract, self.schemas)
        self.assertEqual(len(self.contract["qualified_compatibility_operations"]), 10)
        api = "\n".join(v for k, v in outputs.items() if k.startswith("api/"))
        for operation in self.contract["qualified_compatibility_operations"]:
            self.assertNotIn(f"<!-- operation: {operation['operation']} -->", api)
            self.assertIn(operation["sdk_python"], outputs["sdk-api.md"])
        self.assertIn("preserve microseconds", outputs["sdk-api.md"])

    def test_write_and_check_detect_missing_or_modified_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            outputs = {"api/index.md": "# API\n", "models/index.md": "# Models\n"}
            self.assertTrue(
                callable(getattr(docs, "write_reference", None)),
                "Reference checking must detect missing or edited generated pages",
            )
            docs.write_reference(target, outputs, check=False)
            docs.write_reference(target, outputs, check=True)
            (target / "api/index.md").write_text("# Changed\n")
            with self.assertRaisesRegex(ValueError, "drift"):
                docs.write_reference(target, outputs, check=True)
            (target / "api/index.md").unlink()
            with self.assertRaisesRegex(ValueError, "drift"):
                docs.write_reference(target, outputs, check=True)

    def test_generation_is_repeatable_and_input_is_not_mutated(self):
        contract, schemas = copy.deepcopy(self.contract), copy.deepcopy(self.schemas)
        first = docs.build_reference(contract, schemas)
        self.assertEqual(first, docs.build_reference(contract, schemas))
        self.assertEqual(contract, self.contract)
        self.assertEqual(schemas, self.schemas)

    def test_every_exact_schema_can_be_recovered_without_keyword_loss(self):
        import re

        from reference import SchemaReference

        renderer = SchemaReference(self.schemas)
        outputs = renderer.render_all()
        for name, schema in self.schemas["$defs"].items():
            with self.subTest(model=name):
                text = outputs["models/" + renderer.filename(name)]
                match = re.search(r"    ```json\n(.*?)\n    ```", text, re.DOTALL)
                self.assertIsNotNone(match)
                assert match is not None
                raw = "\n".join(line[4:] for line in match[1].splitlines())
                self.assertEqual(json.loads(raw), schema)
                for field in schema.get("properties", {}):
                    self.assertEqual(text.count(f"| `{field}` |"), 1)

    def test_each_operation_retains_all_declared_parameters_headers_and_responses(self):
        from reference.api import area_for
        from reference.schema import code, literal

        outputs = docs.build_reference(self.contract, self.schemas)
        for operation in self.contract["operations"]:
            with self.subTest(operation=operation["operation"]):
                text = outputs["api/" + area_for(operation) + ".md"]
                section = text.split(
                    "<!-- operation: " + operation["operation"] + " -->"
                )[1].split("<!-- operation: ")[0]
                self.assertIn(
                    f"```http\n{operation['method']} {operation['path']}\n```",
                    section,
                )
                for parameter in operation["parameters"]:
                    default = (
                        literal(parameter["default"])
                        if "default" in parameter
                        else "Not specified"
                    )
                    row = f"| {code(parameter['name'])} | {parameter['location']} | {code(parameter['annotation'])} | {'Yes' if parameter['required'] else 'No'} | {default} |"
                    self.assertIn(row, section)
                for header in operation["headers"]:
                    self.assertIn(code(header), section)
                for status in operation.get(
                    "success_statuses", [operation["success_status"]]
                ):
                    self.assertIn(code(status), section)
                self.assertIn(code(operation["encoding"]), section)

    def test_literal_defaults_are_not_mistaken_for_schema_references(self):
        from reference import SchemaReference

        sample = {
            "$defs": {
                "Object": {
                    "type": "object",
                    "properties": {
                        "payload": {
                            "type": "object",
                            "default": {"$ref": "business-data"},
                        }
                    },
                }
            },
            "models": {},
        }
        output = SchemaReference(sample).render_all()
        self.assertIn("business-data", output["models/object.md"])

    def test_retained_glossary_uses_pinned_native_parameters_and_statuses(
        self,
    ):
        outputs = docs.build_reference(self.contract, self.schemas)
        self.assertTrue(
            "api/retained-glossary.md" in outputs,
            "Retained operation details must be browsable separately",
        )
        page = outputs["api/retained-glossary.md"]
        self.assertIn("X-Workspace-ID", page)
        self.assertIn("If-Match (exact unparsed updated_at string)", page)
        self.assertIn("[`GlossaryTermUpdate`](../models/glossarytermupdate.md)", page)
        self.assertEqual(page.count("<!-- compatibility-operation: "), 10)
        self.assertIn("| `limit` | query | `QueryParam[int]` | No | `100` |", page)
        self.assertIn("| `offset` | query | `QueryParam[int]` | No | `0` |", page)
        self.assertIn(
            "| `term_id` | path | `PathVar[uuid.UUID]` | Yes | Not specified |", page
        )
        self.assertIn(
            "| `body` | body | `Valid[Body[GlossaryTermCreate]]` | Yes | Not specified |",
            page,
        )
        self.assertIn("| `X-Tenant-ID` | header | `str` | Yes | Not specified |", page)
        self.assertIn(
            "| `X-Workspace-ID` | header | `str` | Yes | Not specified |", page
        )
        self.assertIn("| Success status | `201` |", page)
        self.assertIn("| Success status | `204` |", page)

    def test_retained_native_and_guard_source_drift_prevents_generation(self):
        for key in ("native_source_sha256", "guard_sha256"):
            with self.subTest(pin=key):
                contract = copy.deepcopy(self.contract)
                contract["qualified_compatibility_operations"][0][key] = "0" * 64
                with self.assertRaisesRegex(ValueError, "source pin"):
                    docs.build_reference(contract, self.schemas)


if __name__ == "__main__":
    unittest.main()
