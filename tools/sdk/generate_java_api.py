# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
import re

from java_codegen import ROOT, emit

root = ROOT
ops = json.loads((root / "../contract/operations.json").read_text())["operations"]
out = root / "src/main/java/org/fireflyframework/koinon/sdk/api"
models = root / "src/main/java/org/fireflyframework/koinon/sdk/model"
header = "// Copyright 2026 Firefly Software Foundation\n// SPDX-License-Identifier: Apache-2.0\n"
mapping = {}


def add(controller, group, methods):
    for key, value in methods.items():
        mapping[controller + "." + key] = (group, value)


add("OrganizationChatController", "OrganizationChatApi", {"get": "get", "update": "update"})
add("OrganizationKnowledgeController", "OrganizationKnowledgeApi", {"get": "get", "update": "update"})
add("AuditController", "AuditApi", {"audit": "list"})
add("DatasetFilesController", "DatasetsApi", {"append": "appendFile"})
add(
    "CatalogController",
    "CatalogApi",
    {
        ("catalog_" + key): value
        for key, value in {
            "list": "list",
            "create": "create",
            "get": "get",
            "patch": "update",
            "archive": "archive",
            "restore": "restore",
            "delete": "delete",
        }.items()
    },
)
add("ContextController", "PlatformApi", {"context": "context"})
add("CapabilitiesController", "PlatformApi", {"capabilities": "capabilities"})
add("JobController", "JobsApi", {"list": "list", "get": "get", "cancel": "cancel"})
add(
    "MembershipController",
    "MembersApi",
    {
        "members": "list",
        "member_create": "add",
        "member_patch": "update",
        "member_delete": "remove",
    },
)
add(
    "AgentController",
    "AgentsApi",
    {
        "agents": "list",
        "agent_create": "create",
        "agent_update": "update",
        "agent_validate": "validate",
    },
)
add(
    "MembershipController",
    "InvitationsApi",
    {
        "invitations_list": "list",
        "invitation_create": "create",
        "invitation_revoke": "revoke",
    },
)
add(
    "MembershipController",
    "InvitationAccessApi",
    {"invitation_inspect": "inspect", "invitation_redeem": "redeem"},
)
add(
    "AssistantController",
    "ChatApi",
    {
        "activities": "activities",
        "audit": "audit",
        "threads": "threads",
        "thread_create": "createThread",
        "messages": "messages",
        "submit": "submit",
        "cancel": "cancel",
        "retry": "retry",
        "events": "events",
        "result": "result",
    },
)
add("ProviderController", "ConfigurationApi", {"configuration": "get"})
add(
    "ProviderController",
    "ProvidersApi",
    {
        "provider_create": "create",
        "provider_update": "update",
        "provider_validate": "validate",
    },
)
add(
    "KnowledgeConnectionsController",
    "KnowledgeConnectionsApi",
    {
        "roles": "roles",
        "list_connections": "list",
        "create": "create",
        "update": "update",
        "get": "get",
        "delete": "remove",
    },
)
add("KnowledgeController", "SourcesApi", {"upload": "upload"})
add(
    "KnowledgeController",
    "KnowledgeApi",
    {"search": "search", "query": "query", "lineage": "lineage"},
)
add("KnowledgeController", "DatasetsApi", {"schema": "schema"})
add("TableProvenanceController", "DatasetsApi", {"snapshot": "tableProvenance", "history": "tableSnapshots"})
add("TableCoordinateController", "DatasetsApi", {"manifest":"tableCoordinates", "cells":"tableCoordinateCells", "rows":"tableCoordinateRows", "columns":"tableCoordinateColumns"})
add("CuratedKnowledgeController", "KnowledgeIntentsApi", {"preview":"preview", "intent":"get", "confirm":"confirm", "cancel":"cancel"})
add("CuratedKnowledgeController", "KnowledgeItemsApi", {"list":"list", "get":"get", "version":"version"})
add(
    "KnowledgeController",
    "DocumentsApi",
    {"document_chunks": "chunks", "document_original": "original"},
)
add(
    "ContentController",
    "DocumentsApi",
    {"reingest_document": "reingest", "document": "replace"},
)
add(
    "ContentController",
    "DatasetsApi",
    {"reingest_table": "reingestTable", "table": "replaceTable"},
)
add(
    "ProfileController",
    "ProfileApi",
    {
        "get": "get",
        "update": "update",
        "avatar": "avatar",
        "set_avatar": "uploadAvatar",
        "delete_avatar": "deleteAvatar",
    },
)
add("ProfileController", "PeopleApi", {"people": "list", "person_avatar": "avatar"})
add("AuthorizedApplicationController", "AuthorizedApplicationsApi", {"list": "list", "detail": "get", "revoke": "revoke"})
add(
    "PersonalTokenController",
    "TokensApi",
    {"list": "list", "scopes": "scopes", "create": "create", "revoke": "revoke"},
)


add("ChatAttachmentsController", "ChatAttachmentsApi", {"capabilities":"capabilities", "upload":"upload", "list_files":"list", "get":"get", "original":"original", "chunks":"chunks", "cancel":"cancel", "retry":"retry", "delete":"remove", "knowledge":"promote"})
add("ChatHistoryController", "ChatApi", {"thread":"get", "patch_thread":"update", "title_suggestion":"suggestTitle"})
add("ChatHistoryController", "ChatFoldersApi", {"folders":"list", "create_folder":"create", "folder":"get", "patch_folder":"update", "delete_folder":"delete"})
add("KnowledgeIndexesController", "KnowledgeIndexesApi", {"list_indexes":"list", "choices":"choices", "choice":"choice", "get":"get", "plan":"plan", "create":"create", "activate":"activate", "cancel":"cancel", "resume":"resume"})
add("CorporateIdentityController", "IdentityApi", {"list":"list", "create":"create", "get":"get", "update":"update", "test":"test", "test_status":"testStatus", "groups":"groups", "mappings":"mappings", "mapping_create":"createMapping", "mapping_update":"updateMapping", "mapping_remove":"removeMapping", "activate":"activate", "disable":"disable"})

add("ExportController", "ExportsApi", {"review":"review", "create":"create", "list":"list", "get":"get", "download":"download", "cancel":"cancel"})
add("ShareController", "SharesApi", {"review":"review", "create":"create", "list":"list", "get":"get", "revoke":"revoke"})
add("EvidenceController", "EvidenceApi", {"conversation":"conversation"})

add("CatalogProposalController", "ChatProposalsApi", {"get":"get", "confirm":"confirm", "cancel":"cancel"})

def camel(s):
    return re.sub(r"_([a-z])", lambda m: m[1].upper(), s)


def upper(s):
    return s[:1].upper() + s[1:]


filters = {
    "OrganizationChatController.get": "OrganizationChatFilter",
    "AuthorizedApplicationController.list": "AuthorizedApplicationFilter",
    "TableCoordinateController.manifest": "TableCoordinateFilter",
    "TableCoordinateController.rows": "TableCoordinatePageFilter",
    "TableCoordinateController.columns": "TableCoordinatePageFilter",
    "CuratedKnowledgeController.list": "KnowledgeItemFilter",
    "TableProvenanceController.snapshot": "TableProvenanceFilter",
    "TableProvenanceController.history": "TableSnapshotFilter",
    "ExportController.list": "ExportFilter",
    "ShareController.list": "ShareFilter",
    "ChatAttachmentsController.list_files": "AttachmentFilter",
    "ChatAttachmentsController.chunks": "AttachmentChunkFilter",
    "ChatAttachmentsController.delete": "AttachmentDeleteFilter",
    "ChatHistoryController.folders": "FolderFilter",
    "ChatHistoryController.delete_folder": "FolderDeleteFilter",
    "KnowledgeIndexesController.list_indexes": "IndexFilter",
    "KnowledgeIndexesController.choices": "IndexFilter",
    "KnowledgeIndexesController.choice": "IndexScope",
    "CorporateIdentityController.list": "IdentityFilter",
    "CorporateIdentityController.groups": "IdentityGroupFilter",
    "CorporateIdentityController.mappings": "IdentityMappingFilter",
    "CorporateIdentityController.mapping_remove": "IdentityMappingDeleteFilter",
    "AuditController.audit": "AuditFilter",
    "MembershipController.members": "MembershipFilter",
    "MembershipController.invitations_list": "InvitationFilter",
    "CatalogController.catalog_list": "CatalogFilter",
    "AgentController.agents": "AgentFilter",
    "AssistantController.threads": "ThreadFilter",
    "AssistantController.activities": "ActivityFilter",
    "AssistantController.messages": "MessageFilter",
    "KnowledgeController.document_chunks": "ChunkFilter",
    "ProfileController.people": "PeopleFilter",
    "PersonalTokenController.list": "TokenFilter",
    "PersonalTokenController.scopes": "TokenScopeFilter",
    "KnowledgeController.lineage": "LineageFilter",
    "KnowledgeConnectionsController.delete": "ConnectionDeleteFilter",
}
groups = {}
manifest = {}
filter_defs = {}
for op in ops:
    queries = [p for p in op["parameters"] if p["location"] == "query"]
    if not queries:
        continue
    name = filters.get(op["operation"], "WorkspaceFilter")
    filter_defs[name] = queries
for name, queries in filter_defs.items():
    fields = []
    for p in queries:
        wire = p["name"]
        kind = (
            "Integer"
            if "int" in p["annotation"]
            else "Boolean"
            if "bool" in p["annotation"]
            else "String"
        )
        kind = {
            ("MembershipFilter", "role"): "MembershipRole",
            ("MembershipFilter", "scope"): "MembershipScope",
            ("InvitationFilter", "status"): "InvitationStatus",
            ("IndexFilter", "domain"): "KnowledgeDomain",
            ("IndexScope", "domain"): "KnowledgeDomain",
        }.get((name, wire), kind)
        fields.append((wire, camel(wire), kind, p.get("required", False)))
    body = (
        header
        + "package org.fireflyframework.koinon.sdk.model;\nimport org.fireflyframework.koinon.sdk.RequestOptions;\nimport java.util.Objects;\npublic record "
        + name
        + "("
        + ",".join(t + " " + n for _, n, t, _ in fields)
        + ") {\n"
    )
    body += (
        "public static "
        + name
        + " empty(){return new "
        + name
        + "("
        + ",".join("null" for _ in fields)
        + ");}\n"
    )
    if name == "CatalogFilter":
        previous = [field for field in fields if field[0] not in {"format", "tag"}]
        body += (
            "public CatalogFilter("
            + ",".join(t + " " + n for _, n, t, _ in previous)
            + "){this("
            + ",".join("null" if wire in {"format", "tag"} else n for wire, n, _, _ in fields)
            + ");}\n"
        )
    for wire, n, t, required in fields:
        body += (
            "public "
            + name
            + " with"
            + upper(n)
            + "("
            + t
            + " value){return new "
            + name
            + "("
            + ",".join("value" if n == n2 else n2 for _, n2, _, _ in fields)
            + ");}\n"
        )
    body += "public RequestOptions applyTo(RequestOptions options){\n"
    for wire, n, t, required in fields:
        encoded = (
            n + ".value()"
            if t in {"MembershipRole", "MembershipScope", "InvitationStatus", "KnowledgeDomain"}
            else "String.valueOf(" + n + ")"
        )
        if required:
            body += (
                "Objects.requireNonNull("
                + n
                + ","
                + json.dumps(wire + " is required")
                + ");\n"
            )
        body += (
            "if("
            + n
            + "!=null)options=options.query("
            + json.dumps(wire)
            + ","
            + encoded
            + ");\n"
        )
    body += "return options;}\n}\n"
    emit(models / (name + ".java"), body)


def rtype(op):
    s = op.get("response_schema")
    if s is None or s in ["None", "NoneType", "void"]:
        return "Void"
    if s.startswith("Page["):
        return s.replace("[", "<").replace("]", ">")
    if op["operation"] == "AssistantController.events":
        return "EventStream<StreamEvent>"
    if s in ["BinaryContent", "BinaryDownload"]:
        return "BinaryResponse"
    return s


for op in ops:
    group, method = mapping[op["operation"]]
    groups.setdefault(group, []).append((op, method))
    manifest[op["operation"]] = (
        "client."
        + group.removesuffix("Api")[:1].lower()
        + group.removesuffix("Api")[1:]
        + "."
        + method
    )
for group, operations in groups.items():
    scoped = any("{tenant_id}" in o["path"] for o, _ in operations)
    body = (
        header
        + "package org.fireflyframework.koinon.sdk.api;\nimport org.fireflyframework.koinon.sdk.*;\nimport org.fireflyframework.koinon.sdk.internal.Transport;\nimport org.fireflyframework.koinon.sdk.model.*;\nimport java.nio.file.Path;\nimport java.util.*;\nimport java.util.concurrent.CompletableFuture;\npublic final class "
        + group
        + " {\nprivate final Transport transport; private final String prefix;\n"
    )
    body += (
        "public "
        + group
        + "(Transport transport"
        + (",String tenantId" if scoped else "")
        + "){this.transport=Objects.requireNonNull(transport);this.prefix="
        + ('"/tenants/"+Transport.id(tenantId)' if scoped else '""')
        + ";}\n"
    )
    for op, method in operations:
        result = rtype(op)
        path = op["path"].removeprefix("/api/v1")
        path = path.replace("/tenants/{tenant_id}", "")
        params = []
        integer_paths = {p["name"] for p in op["parameters"] if p["location"] == "path" and "int" in p["annotation"]}
        path_expr = "prefix+"
        pieces = re.split(r"(\{\w+\})", path)
        path_expr += "+".join(
            "Transport.id(" + ("String.valueOf(" + camel(p[1:-1]) + ")" if p[1:-1] in integer_paths else camel(p[1:-1])) + ")"
            if p.startswith("{")
            else json.dumps(p)
            for p in pieces
            if p
        )
        for p in op["parameters"]:
            if p["location"] == "path" and p["name"] != "tenant_id":
                params.append(("Long" if p["name"] in integer_paths else "String", camel(p["name"])))
        request = op.get("request_schema")
        queries = [p for p in op["parameters"] if p["location"] == "query"]
        filtername = filters.get(op["operation"], "WorkspaceFilter")
        if request:
            params.append((request, "input"))
        if queries:
            params.append((filtername, "filter"))
        if op["operation"].startswith("ContentController."):
            params.append(("String", "expectedRevision"))
        if any(header.startswith("Idempotency-Key") for header in op.get("headers", [])):
            params.append(("String", "idempotencyKey"))
        params.append(("RequestOptions", "options"))
        decl = ",".join(t + " " + n for t, n in params)
        args = ",".join(n for _, n in params)
        setup = "Objects.requireNonNull(options);"
        for integer in integer_paths:
            setup += "Objects.requireNonNull(" + camel(integer) + ");"
        if any(header.startswith("Idempotency-Key") for header in op.get("headers", [])):
            setup += "options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));"
        if queries:
            setup += "options=Objects.requireNonNull(filter).applyTo(options);"
        if request:
            setup += "Objects.requireNonNull(input);"
        if op["operation"].startswith("ContentController."):
            setup += (
                "options=options.ifMatch(ApiSupport.precondition(expectedRevision));"
            )
        typ = (
            "transport.pageType(" + result[5:-1] + ".class)"
            if result.startswith("Page<")
            else "transport.type(" + result + ".class)"
        )
        binary = result == "BinaryResponse"
        stream = result.startswith("EventStream")
        encoding = op.get("encoding", "")

        def call(
            async_,
            stream=stream,
            path_expr=path_expr,
            binary=binary,
            op=op,
            encoding=encoding,
            request=request,
            typ=typ,
        ):
            suffix = "Async" if async_ else ""
            if stream:
                return "transport.stream(" + path_expr + ",options,StreamEvent.class)"
            if binary:
                return (
                    "transport.binary"
                    + suffix
                    + "("
                    + json.dumps(op["method"])
                    + ","
                    + path_expr
                    + ",options)"
                )
            if encoding == "multipart/form-data":
                fields = (
                    "ApiSupport.uploadFields(input)"
                    if request == "SourceUpload"
                    else "ApiSupport.replacementFields(input)"
                    if request == "DocumentReplacement"
                    else "Map.of()"
                )
                return (
                    "transport.multipart"
                    + suffix
                    + "("
                    + json.dumps(op["method"])
                    + ","
                    + path_expr
                    + ',input.file(),"file",input.mediaType(),'
                    + fields
                    + ",options,"
                    + typ
                    + ")"
                )
            if request == "AvatarUpload":
                return (
                    "transport.bytes"
                    + suffix
                    + "("
                    + json.dumps(op["method"])
                    + ","
                    + path_expr
                    + ",input.content(),input.mediaType().value(),options,"
                    + typ
                    + ")"
                )
            return (
                "transport.json"
                + suffix
                + "("
                + json.dumps(op["method"])
                + ","
                + path_expr
                + ","
                + ("input" if request else "null")
                + ",options,"
                + typ
                + ")"
            )

        for async_ in [False] if stream else [False, True]:
            suffix = "Async" if async_ else ""
            ret = "CompletableFuture<" + result + ">" if async_ else result
            body += (
                "public "
                + ret
                + " "
                + method
                + suffix
                + "("
                + decl
                + "){"
                + setup
                + "return "
                + call(async_)
                + ";}\n"
            )
            body += (
                "public "
                + ret
                + " "
                + method
                + suffix
                + "("
                + ",".join(t + " " + n for t, n in params[:-1])
                + "){return "
                + method
                + suffix
                + "("
                + ",".join([n for _, n in params[:-1]] + ["RequestOptions.defaults()"])
                + ");}\n"
            )
            if queries and not any(p.get("required") for p in queries):
                reduced = [(t, n) for t, n in params if n not in ["filter", "options"]]
                body += (
                    "public "
                    + ret
                    + " "
                    + method
                    + suffix
                    + "("
                    + ",".join(t + " " + n for t, n in reduced)
                    + "){return "
                    + method
                    + suffix
                    + "("
                    + ",".join(
                        n if n != "filter" else filtername + ".empty()"
                        for _, n in params[:-1]
                    )
                    + ",RequestOptions.defaults());}\n"
                )
        if binary:
            dp = params[:-1] + [
                ("Path", "target"),
                ("long", "maxBytes"),
                ("RequestOptions", "options"),
            ]
            for async_ in [False, True]:
                suffix = "Async" if async_ else ""
                ret = "CompletableFuture<FileDownload>" if async_ else "FileDownload"
                name = (
                    "downloadOriginal"
                    if method == "original"
                    else "download" + upper(method)
                )
                body += (
                    "public "
                    + ret
                    + " "
                    + name
                    + suffix
                    + "("
                    + ",".join(t + " " + n for t, n in dp)
                    + "){"
                    + setup
                    + "return transport.download"
                    + suffix
                    + '("GET",'
                    + path_expr
                    + ",target,maxBytes,options);}\n"
                )
    body += "}\n"
    emit(out / (group + ".java"), body)
emit(
    root / "src/test/resources/canonical-methods.json",
    json.dumps(manifest, indent=2) + "\n",
)
print(
    "Wrote", len(groups), "API groups and", len(manifest), "canonical method mappings"
)
