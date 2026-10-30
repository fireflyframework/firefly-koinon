# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import runpy
from pathlib import Path

from java_codegen import ROOT, emit

root = ROOT
contract = json.loads((root / "../contract/schemas.json").read_text())
defs = contract["$defs"]
api = runpy.run_path(str(Path(__file__).with_name("generate_java_api.py")))
ops = api["ops"]
mapping = api["mapping"]
filters = api["filters"]


def fixture(s, field="", depth=0):
    if "$ref" in s:
        name = s["$ref"].split("/")[-1]
        if name == "JsonValue":
            return {
                "decimal": "12345678901234567890.12345678901234567890",
                "integer": "9007199254740993",
            }
        value = fixture(defs[name], field, depth + 1)
        if name == "OrganizationKnowledgeSnapshot":
            value["origin"] = "organization"
            value["digest"] = hashlib.sha256(json.dumps(
                {key: item for key, item in value.items() if key != "digest"},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
            ).encode()).hexdigest()
        return value
    if "const" in s:
        return s["const"]
    if "enum" in s:
        return s["enum"][0]
    if "anyOf" in s or "oneOf" in s:
        return fixture(
            next(v for v in s.get("anyOf", s.get("oneOf")) if v.get("type") != "null"),
            field,
            depth + 1,
        )
    t = s.get("type")
    if t == "null":
        return None
    if t == "object":
        if "properties" in s:
            return {k: fixture(v, k, depth + 1) for k, v in s["properties"].items()}
        a = s.get("additionalProperties")
        return (
            {"example": fixture(a, field, depth + 1)}
            if isinstance(a, dict)
            else {"decimal": "12345678901234567890.12345678901234567890"}
        )
    if t == "array":
        return [fixture(s.get("items", {}), field, depth + 1)]
    if t == "boolean":
        return False
    if t == "integer":
        return max(s.get("minimum", 1), 1)
    if t == "number":
        return max(s.get("minimum", 0.25), 0.25)
    if t == "string":
        if s.get("pattern") in {"^[a-f0-9]{64}$", "^[0-9a-f]{64}$"}:
            return "a" * 64
        value = (
            "2026-10-27T12:34:56Z"
            if field
            in {
                "created_at",
                "updated_at",
                "expires_at",
                "last_used_at",
                "revoked_at",
                "observed_at",
            }
            or s.get("format") == "date-time"
            else field + "-value"
        )
        value = value.ljust(s.get("minLength", 0), "x")
        return value[:s["maxLength"]] if "maxLength" in s else value
    return {"decimal": "12345678901234567890.12345678901234567890"}


fixtures = {
    n: fixture(s)
    for n, s in defs.items()
    if n
    not in [
        "JsonValue",
        "BinaryDownload",
        "AvatarUpload",
        "AttachmentUpload",
        "DatasetFileUpload",
        "SourceUpload",
        "DocumentReplacement",
        "TableReplacement",
    ]
}
if "OrganizationKnowledgeSnapshot" in fixtures:
    fixtures["OrganizationKnowledgeSnapshot"] = fixture({"$ref": "#/$defs/OrganizationKnowledgeSnapshot"})
fixtures["EvidenceResult"] = {
    "id": "evidence-1",
    "run_id": "run-1",
    "kind": "search",
    "data": fixtures["SearchResponse"],
}
operations = []
for op in ops:
    group, method = mapping[op["operation"]]
    queries = [p for p in op["parameters"] if p["location"] == "query"]
    filtername = filters.get(op["operation"], "WorkspaceFilter") if queries else None
    queries = {
        p["name"]: (
            2
            if "int" in p["annotation"]
            else False
            if "bool" in p["annotation"]
            else p["name"] + " value"
        )
        for p in queries
    }
    if op["operation"] in {"KnowledgeIndexesController.list_indexes", "KnowledgeIndexesController.choices", "KnowledgeIndexesController.choice"}:
        queries["domain"] = "documents"
    if op["operation"] == "MembershipController.members":
        queries.update(role="viewer", scope="workspace")
    if op["operation"] == "MembershipController.invitations_list":
        queries["status"] = "pending"
    path = op["path"]
    ids = {
        p["name"]: 2 if "int" in p["annotation"] else p["name"] + " value"
        for p in op["parameters"]
        if p["location"] == "path"
    }
    ids["tenant_id"] = "tenant value"
    for name, value in ids.items():
        path = path.replace("{" + name + "}", str(value))
    response = op["response_schema"]
    response_fixture = fixtures.get(
        response,
        fixtures.get(response.replace("Page[", "Page_").replace("]", "_"))
        if response
        else None,
    )
    operations.append(
        {
            "operation": op["operation"],
            "group": group,
            "method": method,
            "http": op["method"],
            "path": path,
            "ids": ids,
            "query": queries,
            "filter": filtername,
            "request": op["request_schema"],
            "response": response,
            "body": response_fixture,
            "status": op["success_status"],
            "encoding": op["encoding"],
            "precondition": op["operation"].startswith("ContentController."),
            "idempotency": any(header.startswith("Idempotency-Key") for header in op["headers"]),
        }
    )
emit(root / "../contract/fixtures.json", json.dumps({"fixtures": fixtures}, indent=2) + "\n")
resources = root / "src/test/resources"
resources.mkdir(parents=True, exist_ok=True)
emit(
    resources / "canonical-model-fixtures.json",
    json.dumps({"definition_count": len(defs), "excluded_definitions": sorted(set(defs) - set(fixtures)), "fixtures": fixtures}, indent=2) + "\n",
)
emit(
    resources / "canonical-operation-fixtures.json",
    json.dumps(operations, indent=2) + "\n",
)
print(
    "Fixtures",
    len(fixtures),
    "of",
    len(defs),
    "definitions; operations",
    len(operations),
)
