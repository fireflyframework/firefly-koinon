# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generate standalone SDK field contracts without importing server or framework code."""

import argparse
import copy
import ast
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "mcp_applications": "backend/src/koinon/mcp_applications/dtos.py",
    "external_file_reviews": "backend/src/koinon/knowledge/external_reviews/file_dtos.py",
    "mcp": "backend/src/koinon/mcp/dtos.py",
    "external_reviews": "backend/src/koinon/knowledge/external_reviews/dtos.py",
    "organization_branding": "backend/src/koinon/organization_branding/dtos.py",
    "organization_knowledge": "backend/src/koinon/organization_knowledge/dtos.py",
    "organization_chat": "backend/src/koinon/organization_chat/dtos.py",
    "authorized_applications": "backend/src/koinon/authorized_applications/dtos.py",
    "coordinates": "backend/src/koinon/knowledge/provenance/coordinate_dtos.py",
    "curated": "backend/src/koinon/knowledge/curated/dtos.py",
    "provenance": "backend/src/koinon/knowledge/provenance/dtos.py",
    "answer_audit": "backend/src/koinon/assistants/audit_dtos.py",
    "indexes": "backend/src/koinon/knowledge/indexes/dtos.py",
    "identity": "backend/src/koinon/corporate_identity/dtos.py",
    "attachments": "backend/src/koinon/knowledge/attachments/dtos.py",
    "evidence": "backend/src/koinon/evidence/dtos.py",
    "exports": "backend/src/koinon/exports/dtos.py",
    "sharing": "backend/src/koinon/sharing/dtos.py",
    "proposals": "backend/src/koinon/assistants/proposal_dtos.py",
}
HEADER = (
    "# Copyright 2026 Firefly Software Foundation\n"
    "# SPDX-License-Identifier: Apache-2.0\n"
)


def render(source):
    tree = ast.parse(source.read_text())
    if source.parent.name == "evidence":
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "Presentation":
                node.id = "EvidencePresentation"
            elif isinstance(node, ast.ClassDef) and node.name == "Presentation":
                node.name = "EvidencePresentation"
    declarations = []
    if source.parent.name == "organization_branding":
        image_tree = ast.parse(source.with_name("images.py").read_text())
        limit = next(
            node for node in image_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "MAX_DATA_URL_LENGTH" for target in node.targets)
        )
        assert isinstance(ast.literal_eval(limit.value), int)
        declarations.append(limit)
    inputs = {"StrictInput"}
    for node in tree.body:
        if isinstance(node, ast.Assign) and all(
            isinstance(target, ast.Name) for target in node.targets
        ):
            declarations.append(node)
        elif isinstance(node, ast.ClassDef) and node.name not in {
            "StrictInput",
            "AttachmentHistorySummary",
            "ExternalReviewChallenge",
            "ExternalFileReviewChallenge",
        }:
            bases = [ast.unparse(base) for base in node.bases]
            has_input_config = any(
                isinstance(item, ast.Assign)
                and isinstance(item.value, ast.Call)
                and any(
                    keyword.arg == "extra"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value == "forbid"
                    for keyword in item.value.keywords
                )
                for item in node.body
            )
            frozen = any(isinstance(item, ast.Assign) and isinstance(item.value, ast.Call) and any(keyword.arg == "frozen" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in item.value.keywords) for item in node.body)
            is_input = (
                node.name.endswith("Input")
                or (has_input_config and not frozen)
                or any(base in inputs for base in bases)
            )
            if is_input:
                inputs.add(node.name)
            node.bases = [
                ast.Name(
                    id="InputModel" if is_input else "ResponseModel", ctx=ast.Load()
                )
                if base in {"StrictInput", "BaseModel"}
                else original
                for base, original in zip(bases, node.bases, strict=True)
            ]
            if source.parent.name == "external_reviews" and (node.name.endswith("Input") or node.name == "ExternalReviewDecision"):
                node.bases = [ast.Name(id="InputModel", ctx=ast.Load())]
            node.decorator_list = []
            node.body = [
                item
                for item in node.body
                if (isinstance(item, ast.AnnAssign)
                    and isinstance(item.target, ast.Name)
                    and item.target.id != "model_config")
                or (source.parent.name == "organization_knowledge" and node.name == "KnowledgePolicyValue"
                    and isinstance(item, ast.Assign))
            ] or [ast.Pass()]
            if source.parent.name == "curated" and node.name == "KnowledgeConfirmation":
                original = next(value for value in ast.parse(source.read_text()).body if isinstance(value, ast.ClassDef) and value.name == node.name)
                node.body.extend(value for value in original.body if isinstance(value, ast.FunctionDef) and value.name == "explicit")
                validator = next(value for value in node.body if isinstance(value, ast.FunctionDef))
                validator.args.args[1].annotation = ast.Name(id="object", ctx=ast.Load())
                validator.returns = ast.parse("Literal[True]", mode="eval").body
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.annotation, ast.Name) and item.annotation.id == "dict":
                    item.annotation = ast.parse("dict[str, JsonValue]", mode="eval").body
                if isinstance(item, ast.AnnAssign) and isinstance(item.value, ast.Call):
                    for keyword in item.value.keywords:
                        if keyword.arg == "default_factory" and isinstance(keyword.value, ast.Name) and keyword.value.id in {"list", "dict"} and isinstance(item.annotation, ast.Subscript):
                            keyword.value = copy.deepcopy(item.annotation)
            declarations.append(node)
    module = ast.fix_missing_locations(ast.Module(body=declarations, type_ignores=[]))
    names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
    available = {
        "datetime": ["datetime"],
        "typing": ["Annotated", "Literal"],
        "uuid": ["UUID"],
        "pydantic": ["AwareDatetime", "ConfigDict", "Field", "JsonValue", "RootModel", "SecretStr", "StrictBool", "StrictFloat", "StrictInt", "StrictStr", "field_validator"],
        "koinon_sdk._base": ["DocumentRevisionPreconditions", "InputModel", "ResponseModel"],
        "koinon_sdk.contracts": ["Role"],
    }
    declared = {node.name for node in module.body if isinstance(node, ast.ClassDef)}
    declared.update(target.id for node in module.body if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name))
    names -= declared
    available["koinon_sdk.evidence"] = ["ConversationIdentity", "ConversationMessage", "Frozen", "Identifier", "Revision", "SourceReference", "StoredResult"]
    available["koinon_sdk.exports"] = ["Input", "MessageSelection"]
    available["koinon_sdk.organization_knowledge"] = ["OrganizationKnowledgeSnapshot"]
    if source.parent.name == "external_reviews":
        available["koinon_sdk.evidence"] = ["SourceReference"]
        available["koinon_sdk.curated"] = ["Action", "Frozen", "Identifier", "KnowledgeContent", "KnowledgeIntent", "KnowledgeDestination", "Sha256"]
    imports = "\n".join(
        "from " + key + " import " + ", ".join(name for name in values if name in names)
        for key, values in available.items()
        if any(name in names for name in values)
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    description = (
        '"""Generated wire fields.\n\n'
        f"Source: {source.relative_to(ROOT)}\n"
        f"SHA256: {digest}\n\n"
        "Server authorization and semantic validation remain authoritative.\n"
        '"""\n'
    )
    content = HEADER + description + imports + "\n\n\n" + ast.unparse(module) + "\n"
    organized = subprocess.run(
        [sys.executable, "-B", "-m", "ruff", "check", "--select", "I", "--fix", "--stdin-filename", str(ROOT / "sdk/python/src/koinon_sdk/_generated.py")],
        input=content, text=True, capture_output=True, check=True,
    ).stdout
    formatted = subprocess.run(
        [sys.executable, "-B", "-m", "ruff", "format", "--stdin-filename", str(ROOT / "sdk/python/src/koinon_sdk/_generated.py")],
        input=organized, text=True, capture_output=True, check=True,
    ).stdout
    lines = []
    for line in formatted.splitlines():
        if len(line) > 110 and line.lstrip().startswith("description="):
            indent = line[:len(line) - len(line.lstrip())]
            literal = line.strip().removeprefix("description=")
            suffix = "," if literal.endswith(",") else ""
            value = ast.literal_eval(literal.removesuffix(","))
            lines.append(indent + "description=(")
            lines.extend(indent + "    " + repr(value[index:index + 70])
                         for index in range(0, len(value), 70))
            lines.append(indent + ")" + suffix)
        else:
            lines.append(line)
    return subprocess.run(
        [sys.executable, "-B", "-m", "ruff", "format", "--stdin-filename", str(ROOT / "sdk/python/src/koinon_sdk/_generated.py")],
        input="\n".join(lines) + "\n", text=True, capture_output=True, check=True,
    ).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name, relative in SOURCES.items():
        target = ROOT / f"sdk/python/src/koinon_sdk/{name}.py"
        content = render(ROOT / relative)
        if args.check:
            assert target.exists() and ast.dump(
                ast.parse(target.read_text())
            ) == ast.dump(ast.parse(content)), (
                f"Stale generated SDK contract: {target.relative_to(ROOT)}"
            )
        else:
            target.write_text(content)


if __name__ == "__main__":
    main()
