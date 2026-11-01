# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import re

from java_codegen import ROOT, emit

root = ROOT
schema_path = root / "../contract/schemas.json"
defs = json.loads(schema_path.read_text())["$defs"]
out = root / "src/main/java/org/fireflyframework/koinon/sdk/model"
out.mkdir(parents=True, exist_ok=True)
header = "// Copyright 2026 Firefly Software Foundation\n// SPDX-License-Identifier: Apache-2.0\npackage org.fireflyframework.koinon.sdk.model;\n\n"
enums = {
    "McpOAuthClientStatus": ["all", "enabled", "disabled"],
    "McpOAuthClientSort": ["name", "updated_at"],
    "McpOAuthClientOrder": ["asc", "desc"],
}
names = {
    tuple(sorted(v)): k
    for k, v in {
        "ProfilePresentationMode": ["organization", "personal"],
        "ProfileFieldSource": ["directory", "verified_claims", "local"],
        "ProfileObservationSource": ["directory", "verified_claims", "local", "personal"],
        "ProfileSyncStatus": ["not_configured", "not_bound", "queued", "running", "current", "stale", "unavailable", "conflict"],
        "ProfileFieldName": ["display_name", "avatar", "job_title", "department", "manager"],
        "ProfileFieldStatus": ["not_observed", "current", "empty", "unavailable", "unsupported", "stale"],
        "OrganizationUnitKind": ["division", "department", "team"],
        "OrganizationDirectoryVisibility": ["administrators", "shared_workspaces"],
        "OrganizationManagedField": ["job_title", "unit_id", "manager_id"],
        "OrganizationPersonSource": ["unassigned", "manual", "provider"],
        "OrganizationObservationStatus": ["not_observed", "current", "unavailable"],
        "OrganizationMappingSource": ["verified_claims"],
        "SourceReferencePageBasis": ["recorded_loader"],
        "ResourceKind": [
            "workspace",
            "project",
            "collection",
            "corpus",
            "source",
            "document",
            "dataset",
            "chunk",
            "table",
            "index_version",
            "query_session",
        ],
        "MembershipRole": ["viewer", "analyst", "editor", "operator", "admin"],
        "ModelApi": ["chat", "responses", "messages"],
        "NativeModelClass": [
            "OpenAIChatModel",
            "OpenAIResponsesModel",
            "AnthropicModel",
        ],
        "ProviderKind": ["ollama", "openai", "anthropic"],
        "AgentTool": ["search_knowledge", "inspect_schema", "query_dataset", "propose_catalog_update"],
        "MessageStatus": ["queued", "running", "completed", "failed", "cancelled"],
        "AgentStatus": ["ready", "needs_setup", "unverified", "disabled"],
        "CheckStatus": ["passed", "failed", "needs_setup", "unverified"],
        "ObservationStatus": ["passed", "failed", "unknown"],
        "KnowledgeDomain": ["documents", "structured"],
        "KnowledgeAnswerMode": ["rag", "rlm"],
        "McpOAuthScope": ["catalog:read", "catalog:write", "ingest:write", "knowledge:search", "query:execute", "chat:use", "evidence:read", "activity:read"],
        "McpRegisteredClientClientAuth": ["public", "confidential"],
        "KnowledgeSettingsOrigin": ["deployment", "organization"],
        "ConnectionMode": ["provider", "current_agent"],
        "RoleKind": ["embedding", "generative"],
        "ReasoningEffort": ["none", "minimal", "low", "medium", "high", "xhigh"],
        "OutputVerbosity": ["low", "medium", "high"],
        "ModelOutputMode": ["default", "native"],
        "BrandingValuesFontFamily": ["Manrope", "Inter"],
        "ExecutionStatus": ["OK", "REFINED_OK", "FAILED", "REJECTED_BY_FIREWALL"],
        "ChartHint": ["line", "bar", "table", "pie", "none"],
        "EvidenceKind": ["search", "query", "schema", "lineage", "attachment", "proposal"],
    }.items()
}


def camel(s):
    value = re.sub(r"_([a-z])", lambda m: m[1].upper(), s)
    return {
        "default": "defaultValue",
        "class": "className",
        "enum": "enumValue",
        "native": "nativeValue",
    }.get(value, value)


def pascal(s):
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[_\W]+", s) if w)


def enum_type(values, owner, field):
    key = tuple(sorted(values))
    name = names.setdefault(key, owner + pascal(field))
    enums[name] = values
    return name


unions = {}
branch_interfaces = {}

def union_name(schema):
    variants = schema.get("oneOf", schema.get("anyOf", []))
    if not schema.get("discriminator") or not all("$ref" in variant for variant in variants):
        return None
    refs = tuple(variant["$ref"].split("/")[-1] for variant in variants)
    name = "IdentityProviderCredential" if "KeycloakCredential" in refs else "IdentityProviderSettings" if "KeycloakSettings" in refs else "AttachmentPromotionInput" if "AddKnowledge" in refs else "ExportReviewRequest" if "ConversationExportInput" in refs else None
    name = name or ("KnowledgeCommitOutcome" if "CommittedKnowledge" in refs else "KnowledgeOrigin" if "UserStatementOrigin" in refs else "KnowledgeEvidence" if "UserStatementEvidence" in refs else None)
    if name:
        unions[name] = (schema["discriminator"]["propertyName"], refs)
        for branch in refs:
            branch_interfaces.setdefault(branch, set()).add(name)
    return name

def find_unions(value):
    if isinstance(value, dict):
        union_name(value)
        for child in value.values():
            find_unions(child)
    elif isinstance(value, list):
        for child in value:
            find_unions(child)


find_unions(defs)

def java_type(s, owner="", field=""):
    if owner == "ObservedCost" and field == "amount":
        return "BigDecimal"
    union = union_name(s)
    if union:
        return union
    if "$ref" in s:
        name = s["$ref"].split("/")[-1]
        if owner == "OrganizationBrandingInput" and field == "branding" and name == "BrandingInputValues":
            # Server-only decode staging keeps the existing structurally identical client input.
            return "BrandingValues"
        if name == "JsonValue":
            return "JsonNode"
        if name.startswith("Page_"):
            return "Page<" + name[5:-1] + ">"
        return name
    variants = s.get("anyOf", s.get("oneOf"))
    if variants:
        real = [v for v in variants if v.get("type") != "null"]
        return java_type(real[0], owner, field) if len(real) == 1 else "JsonNode"
    if isinstance(s.get("const"), str):
        return enum_type([s["const"]], owner, field)
    if "enum" in s and all(isinstance(v, str) for v in s["enum"]):
        return enum_type(s["enum"], owner, field)
    kind = s.get("type")
    if kind == "array":
        return "List<" + java_type(s.get("items", {}), owner, field) + ">"
    if kind == "object":
        extra = s.get("additionalProperties")
        if isinstance(extra, dict):
            inner = java_type(extra, owner, field)
            if inner != "JsonNode":
                return "Map<String," + inner + ">"
        return "JsonNode"
    if kind == "boolean":
        return "Boolean"
    if kind == "integer":
        return (
            "Integer"
            if s.get("maximum", 2**63) < 2**31
            and s.get("minimum", -(2**31)) >= -(2**31)
            else "Long"
        )
    if kind == "number":
        return "BigDecimal"
    if kind == "string":
        if owner == "GlossaryTermRead" and field in {"created_at", "updated_at"}:
            return "String"
        return (
            "Instant"
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
            else "String"
        )
    return "JsonNode"


def nullable(s):
    return any(v.get("type") == "null" for v in s.get("anyOf", []))


request_names = {
    x["request_schema"]
    for x in json.loads((root / "../contract/operations.json").read_text())[
        "operations"
    ]
    if isinstance(x.get("request_schema"), str)
}
skip = {
    "Page",
    "AuthorSummary",
    "JsonValue",
    "EvidenceResult",
    "BinaryDownload",
    "AvatarUpload",
    "BulkFileUpload",
    "AttachmentUpload",
    "DatasetFileUpload",
    "SourceUpload",
    "DocumentReplacement",
    "TableReplacement",
}
created = []
for name, definition in defs.items():
    if name in skip or name in unions or name.startswith("Page_"):
        continue
    properties = definition.get("properties")
    if properties is None:
        continue
    if definition.get("additionalProperties") is False and name not in {
        "McpOAuthClient", "McpOAuthClientCredential", "McpOAuthClientReadiness", "McpOAuthClientPage",
    }:
        request_names.add(name)
    fields = []
    for wire, value in properties.items():
        kind = java_type(value, name, wire)
        wrapped = name in request_names and nullable(value)
        fields.append(
            (
                wire,
                camel(wire),
                "JsonField<" + kind + ">" if wrapped else kind,
                kind,
                wrapped,
            )
        )
    body = (
        header
        + "import com.fasterxml.jackson.annotation.JsonProperty;\nimport com.fasterxml.jackson.databind.JsonNode;\nimport java.math.BigDecimal;\nimport java.time.Instant;\nimport java.util.List;\nimport java.util.Map;\n\n/** Typed canonical "
        + name
        + " contract. */\npublic record "
        + name
        + "(\n"
        + ("    " if fields else "")
        + ",\n    ".join(
            "@JsonProperty(" + json.dumps(wire) + ") " + kind + " " + key
            for wire, key, kind, _, _ in fields
        )
        + "\n) " + ("implements " + ",".join(sorted(branch_interfaces[name])) + " " if name in branch_interfaces else "") + "{\n"
    )
    copies = []
    accessors = []
    added_memory_fields = {
        "FolderCreate": "memory_enabled", "FolderPatch": "memory_enabled", "ChatFolder": "memory_enabled",
        "OrganizationChatSettings": "memory", "OrganizationChatSettingsInput": "memory", "AnswerAudit": "memory",
        "ShareCreate": "include_remembered_context", "ShareReview": "remembered_context_present",
        "KnowledgeIntentInput": "include_remembered_context", "KnowledgeIntent": "remembered_context_present",
        "KnowledgeConfirmation": "include_remembered_context", "DocumentEvidence": "basis", "StructuredEvidence": "basis",
    }
    if name in added_memory_fields:
        added = added_memory_fields[name]
        previous = [field for field in fields if field[0] != added]
        body += (
            "    public " + name + "("
            + ", ".join(kind + " " + key for _, key, kind, _, _ in previous)
            + "){this(" + ",".join("null" if wire == added else key for wire, key, _, _, _ in fields) + ");}\n"
        )
    if name == "SearchHit":
        previous = [field for field in fields if field[0] != "source_reference"]
        body += (
            "    public SearchHit("
            + ", ".join(kind + " " + key for _, key, kind, _, _ in previous)
            + "){this("
            + ",".join("null" if wire == "source_reference" else key for wire, key, _, _, _ in fields)
            + ");}\n"
        )
    if name == "RlmToolReceipt":
        previous = [field for field in fields if field[0] != "knowledge_item_ids"]
        body += (
            "    public RlmToolReceipt("
            + ", ".join(kind + " " + key for _, key, kind, _, _ in previous)
            + "){this("
            + ",".join("List.of()" if wire == "knowledge_item_ids" else key for wire, key, _, _, _ in fields)
            + ");}\n"
        )
    if name == "AttachmentObservation":
        body += (
            "    public AttachmentObservation { configured = Boolean.TRUE.equals(configured); }\n"
            "    public AttachmentObservation(Boolean available, String reason) {\n"
            "        this(available, reason, false);\n    }\n"
        )
    if name in {"CatalogUpdate", "ConversationSnapshot", "ExportReview", "ShareReview", "SharedConversation"}:
        assert fields[-1][0] == ("expected_updated_at" if name == "CatalogUpdate" else "identity")
        previous = fields[:-1]
        body += (
            "    public " + name + "("
            + ", ".join(kind + " " + key for _, key, kind, _, _ in previous)
            + "){this(" + ",".join(key for _, key, _, _, _ in previous) + ",null);}\n"
        )
    for wire, key, kind, raw, wrapped in fields:
        if wrapped:
            continue
        if name == "RlmToolReceipt" and wire in {"source_ids", "knowledge_item_ids"}:
            copies.append(key + "=" + key + "==null?List.of():List.copyOf(" + key + ");")
            continue
        if kind == "JsonNode":
            copies.append(key + "=ModelValues.json(" + key + ");")
            accessors.append(
                "    @Override public JsonNode "
                + key
                + "(){return ModelValues.json("
                + key
                + ");}"
            )
        elif kind == "List<JsonNode>":
            copies.append(key + "=ModelValues.jsonList(" + key + ");")
            accessors.append(
                "    @Override public List<JsonNode> "
                + key
                + "(){return ModelValues.jsonList("
                + key
                + ");}"
            )
        elif kind.startswith("List<"):
            copies.append(key + "=" + key + "==null?null:List.copyOf(" + key + ");")
        elif kind.startswith("Map<"):
            copies.append(key + "=" + key + "==null?null:Map.copyOf(" + key + ");")
    if copies:
        body += (
            "    public "
            + name
            + " {\n        "
            + "\n        ".join(copies)
            + "\n    }\n"
        )
    body += "\n".join(accessors) + "\n"
    if name in request_names or name in {
        "ModelParameters",
        "KnowledgeScope",
        "Presentation",
    }:
        body += (
            "    public static "
            + name
            + " empty(){return new "
            + name
            + "("
            + ",".join("null" for _ in fields)
            + ");}\n"
        )
        for wire, key, kind, raw, wrapped in fields:
            body += (
                "    public "
                + name
                + " with"
                + pascal(wire)
                + "("
                + raw
                + " value){return new "
                + name
                + "("
                + ",".join(
                    ("JsonField.of(value)" if wrapped else "value") if k == key else k
                    for _, k, _, _, _ in fields
                )
                + ");}\n"
            )
            if wrapped:
                body += (
                    "    public "
                    + name
                    + " clear"
                    + pascal(wire)
                    + "(){return new "
                    + name
                    + "("
                    + ",".join(
                        "JsonField.clear()" if k == key else k
                        for _, k, _, _, _ in fields
                    )
                    + ");}\n"
                )
                body += (
                    "    public "
                    + name
                    + " omit"
                    + pascal(wire)
                    + "(){return new "
                    + name
                    + "("
                    + ",".join("null" if k == key else k for _, k, _, _, _ in fields)
                    + ");}\n"
                )
    if name not in {"TokenCreated", "InvitationCreated", "InvitationToken"} and (name == "McpOAuthClientCredential" or any(value.get("format") == "password" for value in properties.values())):
        body += '    @Override public String toString(){return "' + name + '[credentials=<redacted>]";}\n'
    if name == "TokenCreated":
        body += '    @Override public String toString(){return "TokenCreated[id="+id+", token=<redacted>]";}\n'
    if name in {"InvitationCreated", "InvitationToken"}:
        body += (
            '    @Override public String toString(){return "'
            + name
            + '[token=<redacted>]";}\n'
        )
    body += "}\n"
    emit(out / (name + ".java"), body)
    created.append(name)
for name, (discriminator, branches) in unions.items():
    body = header + "import com.fasterxml.jackson.annotation.JsonSubTypes;\nimport com.fasterxml.jackson.annotation.JsonTypeInfo;\n"
    body += '@JsonTypeInfo(use=JsonTypeInfo.Id.NAME,include=JsonTypeInfo.As.EXISTING_PROPERTY,property=' + json.dumps(discriminator) + ',visible=true)\n@JsonSubTypes({'
    body += ",".join("@JsonSubTypes.Type(value=" + branch + ".class,name=" + json.dumps(defs[branch]["properties"][discriminator]["const"]) + ")" for branch in branches)
    body += "})\npublic sealed interface " + name + " permits " + ",".join(branches) + " {}\n"
    emit(out / (name + ".java"), body)
enums["EvidenceKind"] = defs["EvidenceResult"]["properties"]["kind"]["enum"]
for name, values in enums.items():
    constants = []
    for value in values:
        constants.append(
            re.sub(r"[^A-Z0-9_]", "_", re.sub(r"(?<=[a-z])(?=[A-Z])", "_", value).upper())
            + "("
            + json.dumps(value)
            + ")"
        )
    body = (
        header
        + "import com.fasterxml.jackson.annotation.JsonCreator;\nimport com.fasterxml.jackson.annotation.JsonValue;\n\npublic enum "
        + name
        + " {\n    "
        + ",\n    ".join(constants)
        + ";\n    private final String value;\n    "
        + name
        + "(String value){this.value=value;}\n    @JsonValue public String value(){return value;}\n    @JsonCreator public static "
        + name
        + ' from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown '
        + name
        + ' value: "+value);}\n}\n'
    )
    emit(out / (name + ".java"), body)
print(
    "Generated",
    len(created),
    "DTO records and",
    len(enums),
    "wire enums from",
    hashlib.sha256(schema_path.read_bytes()).hexdigest(),
)
emit(
    root / "src/test/resources/canonical-enums.json", json.dumps(enums, indent=2) + "\n"
)
