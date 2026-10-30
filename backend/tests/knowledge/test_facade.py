# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
async def context(tmp_path: Path):
    from pyfly.core import PyFlyApplication
    from test_policy_runtime_scope import snapshot

    from koinon.app import KoinonApplication
    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import MembershipRepository, TenantRepository
    from koinon.catalog.service import CatalogService
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings

    config = tmp_path / "pyfly.yaml"
    config.write_text(
        "pyfly:\n  banner:\n    mode: off\n  data:\n    relational:\n      enabled: true\n"
        f"      ddl-auto: create\n      url: sqlite+aiosqlite:///{tmp_path / 'facade.db'}\n"
    )
    app = PyFlyApplication(KoinonApplication, config_path=str(config))
    app.context.register_bean(DomainBindingRepository)
    await app.startup()
    try:
        tenants = app.context.get_bean(TenantRepository)
        members = app.context.get_bean(MembershipRepository)
        for tenant in ("north", "south"):
            await tenants.save(Tenant(id=tenant, name=tenant))
        for subject, tenant, role in (
            ("admin", "north", "admin"),
            ("reader", "north", "viewer"),
            ("analyst", "north", "analyst"),
            ("outsider", "south", "admin"),
        ):
            await members.save(
                Membership(id=subject, subject=f"issuer|{subject}", tenant_id=tenant, role=role)
            )
        catalog = app.context.get_bean(CatalogService)
        parent = None
        tree = {}
        for kind in ("workspace", "project", "collection"):
            entry = await catalog.create("issuer|admin", "north", kind=kind, name=kind, parent_id=parent)
            tree[kind] = entry
            parent = entry.id
        domains = SimpleNamespace(
            ensure_workspace=AsyncMock(return_value="native-workspace"),
            ingest_document=AsyncMock(return_value={"source_id": "native-source", "n_chunks": 2}),
            ingest_dataset=AsyncMock(
                return_value={"dataset_id": "native-dataset", "file_id": "native-file", "tables": []}
            ),
            search=AsyncMock(return_value={"hits": []}),
            query=AsyncMock(return_value={"query_id": "native-query", "execution_status": "OK"}),
            schema=AsyncMock(return_value={"tables": []}),
            lineage=AsyncMock(return_value={"nodes": [], "edges": []}),
        )
        bindings = app.context.get_bean(DomainBindingRepository)
        policies = SimpleNamespace(snapshot=AsyncMock(side_effect=lambda subject, tenant: snapshot(tenant)))
        facade = KnowledgeFacade(
            catalog, bindings, domains, KnowledgeSettings(max_upload_bytes=1024), knowledge_settings=policies
        )
        yield facade, catalog, domains, tree, app.context
    finally:
        await app.shutdown()


async def upload(context, mode="document"):
    facade, _, _, tree, _ = context
    return await facade.upload(
        "issuer|admin",
        "north",
        workspace_id=tree["workspace"].id,
        project_id=tree["project"].id,
        parent_id=tree["collection"].id,
        mode=mode,
        filename="facts.txt",
        content=b"evidence",
    )


async def test_durable_source_intent_hook_runs_before_any_native_ingestion(context):
    facade, catalog, domains, tree, _ = context
    observed = []

    async def retained(source):
        observed.append(source.id)
        assert (await catalog.get("issuer|admin", "north", source.id)).status == "pending"
        domains.ingest_document.assert_not_awaited()

    result = await facade.upload(
        "issuer|admin",
        "north",
        workspace_id=tree["workspace"].id,
        project_id=tree["project"].id,
        parent_id=tree["collection"].id,
        mode="document",
        filename="facts.txt",
        content=b"evidence",
        _on_source=retained,
    )
    assert observed == [result["source"]["id"]]


async def test_viewer_and_foreign_tenant_are_denied_before_domain_access(context):
    from koinon.catalog.errors import AccessDenied

    facade, _, domains, tree, _ = context
    for subject, tenant in (("issuer|reader", "north"), ("issuer|outsider", "south")):
        with pytest.raises(AccessDenied):
            await facade.upload(
                subject,
                tenant,
                workspace_id=tree["workspace"].id,
                project_id=tree["project"].id,
                parent_id=tree["collection"].id,
                mode="document",
                filename="facts.txt",
                content=b"evidence",
            )
    domains.ensure_workspace.assert_not_awaited()
    domains.ingest_document.assert_not_awaited()


async def test_parent_mismatch_and_traversal_filename_are_refused(context):
    from koinon.catalog.errors import InvalidHierarchy

    facade, _, domains, tree, _ = context
    with pytest.raises(InvalidHierarchy):
        await facade.upload(
            "issuer|admin",
            "north",
            workspace_id=tree["workspace"].id,
            project_id="wrong",
            parent_id=tree["collection"].id,
            mode="document",
            filename="facts.txt",
            content=b"x",
        )
    for filename in ("../secret", "/etc/passwd", "folder\\file.csv"):
        with pytest.raises(ValueError):
            await facade.upload(
                "issuer|admin",
                "north",
                workspace_id=tree["workspace"].id,
                project_id=tree["project"].id,
                parent_id=tree["collection"].id,
                mode="document",
                filename=filename,
                content=b"x",
            )
    domains.ingest_document.assert_not_awaited()


async def test_document_upload_persists_explicit_binding_and_trusted_actor(context):

    facade, _, domains, tree, app = context
    result = await upload(context)
    assert result["source"]["status"] == "ready"
    asset = result["assets"][0]
    assert asset["parent_id"] == result["source"]["id"]
    assert asset["workspace_id"] == tree["workspace"].id
    assert asset["project_id"] == tree["project"].id
    binding = await facade.binding("north", asset["id"], "canon")
    assert binding.native_id == "native-source"
    assert binding.native_workspace_id == "native-workspace"
    assert binding.created_by == "issuer|admin"
    assert domains.ingest_document.await_args.kwargs["actor"] == "issuer|admin"
    assert binding.id != binding.native_id


async def test_ingest_failure_is_a_durable_error_not_a_ready_asset(context):
    facade, catalog, domains, _, _ = context
    domains.ingest_document.side_effect = RuntimeError("provider unavailable")
    with pytest.raises(RuntimeError):
        await upload(context)
    sources = await catalog.list("issuer|admin", "north", kind="source")
    assert len(sources) == 1
    assert sources[0].status == "error"
    assert sources[0].metadata_json["failure_type"] == "RuntimeError"
    assert not await catalog.list("issuer|admin", "north", kind="document")


async def test_search_uses_binding_and_limits_native_sources_before_retrieval(context):
    facade, catalog, domains, tree, _ = context
    result = await upload(context)
    asset = result["assets"][0]
    await catalog.update("issuer|admin", "north", asset["id"], {"metadata": {"native_id": "forged"}})
    domains.search.return_value = {
        "hits": [{"chunk_id": "chunk-1", "source_id": "native-source", "content": "Evidence", "score": 0.9}]
    }
    response = await facade.search(
        "issuer|reader", "north", question="facts", workspace_id=tree["workspace"].id
    )
    assert domains.search.await_args.kwargs["source_ids"] == ["native-source"]
    assert response["hits"][0]["asset_id"] == asset["id"]
    assert response["hits"][0]["source_id"] == result["source"]["id"]
    domains.search.return_value = {
        "hits": [{"chunk_id": "foreign", "source_id": "foreign", "content": "secret"}]
    }
    from koinon.catalog.errors import AccessDenied

    with pytest.raises(AccessDenied):
        await facade.search("issuer|reader", "north", question="facts")


@pytest.mark.parametrize("answer", [False, True])
async def test_direct_search_exposes_the_observed_immutable_source_reference(context, answer):
    from hashlib import sha256

    from koinon.knowledge.capture_dtos import DocumentRead

    facade, _, domains, tree, _ = context
    uploaded = await upload(context)

    async def search(**arguments):
        capture = arguments["_capture"]
        capture.documents["projection"] = DocumentRead(
            "native-workspace", "native-source", "projection", sha256(b"Exact immutable text").hexdigest(),
            "Exact immutable text", None, "Recorded section", "version", "ingestion", "part",
            sha256(b"Exact immutable text").hexdigest(), 7,
        )
        return {"hits": [{"chunk_id": "projection", "source_id": "native-source",
                          "content": "Exact immutable text", "score": 0.9,
                          "metadata": {"source_version_id": "forged-version", "source_part_id": "forged"}}],
                "answer": "Recorded answer", "citations": []}

    domains.search.side_effect = search
    response = await facade.search("issuer|reader", "north", question="facts", answer=answer,
                                   workspace_id=tree["workspace"].id)
    found = response["hits"][0]
    assert found["id"] == "projection" and found["text"] == "Exact immutable text"
    reference = found["source_reference"]
    assert reference["asset_id"] == uploaded["assets"][0]["id"]
    assert reference["source_id"] == uploaded["source"]["id"]
    assert (reference["source_version_id"], reference["extraction_id"], reference["source_part_id"]) == (
        "version", "ingestion", "part",
    )
    assert reference["chunk_id"] is None and reference["recorded_page"] == 7
    assert reference["quote"] == "Exact immutable text" and reference["availability"] == "unverified"


@pytest.mark.parametrize("tamper", ["workspace", "source", "id", "text"])
async def test_direct_search_rejects_hits_that_differ_from_their_observed_receipt(context, tamper):
    from hashlib import sha256

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.capture_dtos import DocumentRead

    facade, _, domains, _, _ = context
    await upload(context)

    async def search(**arguments):
        arguments["_capture"].documents["projection"] = DocumentRead(
            "wrong-space" if tamper == "workspace" else "native-workspace",
            "wrong-source" if tamper == "source" else "native-source",
            "projection", sha256(b"Exact text").hexdigest(), "Exact text", None, None,
            "version", "ingestion", "part", sha256(b"Exact text").hexdigest(), None,
        )
        return {"hits": [{"chunk_id": "wrong-id" if tamper == "id" else "projection",
                          "source_id": "native-source",
                          "content": "Unobserved text" if tamper == "text" else "Exact text"}]}

    domains.search.side_effect = search
    with pytest.raises(AccessDenied):
        await facade.search("issuer|reader", "north", question="facts")


async def test_dataset_query_requires_role_and_uses_durable_native_identity(context):
    from koinon.catalog.errors import AccessDenied

    facade, _, domains, _, _ = context
    result = await upload(context, "dataset")
    dataset_id = result["assets"][0]["id"]
    with pytest.raises(AccessDenied):
        await facade.query("issuer|reader", "north", dataset_id=dataset_id, question="total")
    domains.query.assert_not_awaited()
    answer = await facade.query("issuer|analyst", "north", dataset_id=dataset_id, question="total")
    assert answer["execution_status"] == "OK"
    assert domains.query.await_args.kwargs["dataset_id"] == "native-dataset"
    assert domains.query.await_args.kwargs["dataset_allowlist"] == {"native-dataset"}
    assert domains.query.await_args.kwargs["actor"] == "issuer|analyst"


async def test_schema_lineage_and_binding_scope_cannot_cross_tenants(context):
    from koinon.catalog.errors import AccessDenied

    facade, _, domains, _, _ = context
    result = await upload(context, "dataset")
    asset_id = result["assets"][0]["id"]
    with pytest.raises(AccessDenied):
        await facade.schema("issuer|outsider", "south", asset_id)
    domains.schema.assert_not_awaited()
    lineage = await facade.lineage("issuer|reader", "north", asset_id)
    assert asset_id in {node["id"] for node in lineage["nodes"]}
    assert any(edge["target"] == asset_id for edge in lineage["edges"])


async def test_schema_uses_catalog_table_ids_and_refuses_unbound_tables(context):
    from koinon.catalog.errors import AccessDenied

    facade, catalog, domains, _, _ = context
    domains.ingest_dataset.return_value = {
        "dataset_id": "native-dataset",
        "file_id": "native-file",
        "tables": [{"table_id": "native-table", "name": "Facts", "snapshot_id": "v1"}],
    }
    result = await upload(context, "dataset")
    asset = result["assets"][0]
    table = (await catalog.list("issuer|reader", "north", kind="table", parent_id=asset["id"]))[0]
    domains.schema.return_value = {"tables": [{"id": "native-table", "name": "Facts", "columns": []}]}
    schema = await facade.schema("issuer|reader", "north", asset["id"])
    assert schema["tables"][0]["id"] == table.id
    domains.schema.return_value = {"tables": [{"id": "foreign-table", "name": "Secret", "columns": []}]}
    with pytest.raises(AccessDenied):
        await facade.schema("issuer|reader", "north", asset["id"])


async def test_lineage_includes_retained_document_fragments(context):
    facade, _, domains, _, _ = context
    result = await upload(context)
    asset = result["assets"][0]
    domains.lineage.return_value = {
        "nodes": [{"id": "canon:chunk:1", "label": "Chunk 1", "kind": "chunk"}],
        "edges": [{"source": "$asset", "target": "canon:chunk:1", "label": "extracted"}],
    }
    lineage = await facade.lineage("issuer|reader", "north", asset["id"])
    assert any(
        edge["source"] == asset["id"] and edge["target"] == "canon:chunk:1" for edge in lineage["edges"]
    )


async def test_dataset_lineage_uses_canonical_table_id_and_rejects_unbound_native_table(context):
    from koinon.catalog.errors import AccessDenied

    facade, catalog, domains, _, _ = context
    domains.ingest_dataset.return_value = {
        "dataset_id": "native-dataset",
        "file_id": "native-file",
        "tables": [{"table_id": "native-table", "name": "Facts", "snapshot_id": "v1"}],
    }
    result = await upload(context, "dataset")
    asset = result["assets"][0]
    table = (await catalog.list("issuer|reader", "north", kind="table", parent_id=asset["id"]))[0]
    domains.lineage.return_value = {
        "nodes": [
            {
                "id": "structured:table:native-table",
                "native_id": "native-table",
                "label": "Facts",
                "kind": "table",
            }
        ],
        "edges": [{"source": "$asset", "target": "structured:table:native-table", "label": "materialized"}],
    }
    lineage = await facade.lineage("issuer|reader", "north", asset["id"])
    assert table.id in {node["id"] for node in lineage["nodes"]}
    assert any(edge["source"] == asset["id"] and edge["target"] == table.id for edge in lineage["edges"])
    domains.lineage.return_value["nodes"][0]["native_id"] = "foreign-table"
    with pytest.raises(AccessDenied):
        await facade.lineage("issuer|reader", "north", asset["id"])


async def test_binding_failure_does_not_leave_a_ready_asset(context, monkeypatch):
    facade, catalog, _, _, _ = context
    original = facade._bind

    async def fail_asset(subject, tenant_id, entry, *args, **kwargs):
        if entry.kind == "document":
            raise RuntimeError("binding storage failed")
        return await original(subject, tenant_id, entry, *args, **kwargs)

    monkeypatch.setattr(facade, "_bind", fail_asset)
    with pytest.raises(RuntimeError, match="binding storage failed"):
        await upload(context)
    assets = await catalog.list("issuer|admin", "north", kind="document")
    assert assets and all(asset.status == "error" for asset in assets)


@pytest.mark.parametrize("operation", ["query", "schema", "lineage"])
@pytest.mark.parametrize("field", ["workspace_id", "native_workspace_id"])
async def test_binding_scope_mismatch_is_denied_before_native_dataset_access(context, operation, field):
    from koinon.catalog.errors import AccessDenied

    facade, _, domains, _, _ = context
    result = await upload(context, "dataset")
    asset_id = result["assets"][0]["id"]
    binding = await facade.binding("north", asset_id, "structured")
    setattr(binding, field, "another-workspace")
    await facade.bindings.save(binding)
    with pytest.raises(AccessDenied):
        if operation == "query":
            await facade.query("issuer|analyst", "north", dataset_id=asset_id, question="total")
        else:
            await getattr(facade, operation)("issuer|reader", "north", asset_id)
    getattr(domains, operation).assert_not_awaited()


async def test_search_asset_ids_restrict_sources_before_retrieval_and_empty_never_broadens(context):
    facade, _, domains, _, _ = context
    first = (await upload(context))["assets"][0]
    domains.ingest_document.return_value = {"source_id": "native-second", "n_chunks": 1}
    await upload(context)
    await facade.search("issuer|reader", "north", question="facts", asset_ids=[first["id"]], answer=True)
    assert domains.search.await_args.kwargs["source_ids"] == ["native-source"]
    domains.search.reset_mock()
    empty = await facade.search("issuer|reader", "north", question="facts", asset_ids=[], answer=True)
    policy = await facade.knowledge_settings.snapshot("issuer|reader", "north")
    assert empty.pop("knowledge_settings_snapshot") == policy.model_dump(mode="json")
    assert empty == {
        "hits": [],
        "answer": "",
        "citations": [],
    }
    domains.search.assert_not_awaited()
    await facade.search("issuer|reader", "north", question="facts", asset_ids=None)
    assert domains.search.await_args.kwargs["source_ids"] == ["native-second", "native-source"]


async def test_search_rejects_mixed_unknown_or_mismatched_asset_ids_before_domain_invocation(context):
    from koinon.catalog.errors import AccessDenied, InvalidHierarchy

    facade, catalog, domains, tree, _ = context
    first = (await upload(context))["assets"][0]
    with pytest.raises(AccessDenied):
        await facade.search("issuer|reader", "north", question="facts", asset_ids=[first["id"], "unknown"])
    other_project = await catalog.create(
        "issuer|admin", "north", kind="project", name="Other", parent_id=tree["workspace"].id
    )
    other_collection = await catalog.create(
        "issuer|admin", "north", kind="collection", name="Other", parent_id=other_project.id
    )
    domains.ingest_document.return_value = {"source_id": "native-other", "n_chunks": 1}
    other = await facade.upload(
        "issuer|admin",
        "north",
        workspace_id=tree["workspace"].id,
        project_id=other_project.id,
        parent_id=other_collection.id,
        mode="document",
        filename="other.md",
        content=b"Other",
    )
    with pytest.raises(InvalidHierarchy):
        await facade.search(
            "issuer|reader",
            "north",
            question="facts",
            project_id=tree["project"].id,
            asset_ids=[first["id"], other["assets"][0]["id"]],
        )
    domains.search.assert_not_awaited()


async def test_document_search_rejects_dataset_selection_before_domain_invocation(context):
    from koinon.catalog.errors import InvalidHierarchy

    facade, _, domains, _, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]
    with pytest.raises(InvalidHierarchy):
        await facade.search("issuer|analyst", "north", question="facts", asset_ids=[dataset["id"]])
    domains.search.assert_not_awaited()


@pytest.mark.parametrize("operation", ["query", "schema", "lineage", "search"])
async def test_archived_ancestor_denies_exact_asset_access_before_native_invocation(context, operation):
    from koinon.catalog.errors import AccessDenied

    facade, catalog, domains, tree, _ = context
    asset = (await upload(context, "document" if operation == "search" else "dataset"))["assets"][0]
    await catalog.archive("issuer|admin", "north", tree["collection"].id)
    with pytest.raises(AccessDenied, match="archived"):
        if operation == "query":
            await facade.query("issuer|analyst", "north", dataset_id=asset["id"], question="total")
        elif operation == "search":
            await facade.search("issuer|reader", "north", question="facts", asset_ids=[asset["id"]])
        else:
            await getattr(facade, operation)("issuer|reader", "north", asset["id"])
    getattr(domains, operation).assert_not_awaited()


async def test_model_receipt_rechecks_current_query_membership_instead_of_prior_admission(context):
    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.repositories import MembershipRepository

    facade, _, domains, _, native_context = context
    result = await upload(context, mode="dataset")
    dataset = result["assets"][0]["id"]
    stages = []

    async def query(**arguments):
        receipt = arguments["_capture"]
        await receipt.authorize()
        stages.append("grounding")
        members = native_context.get_bean(MembershipRepository)
        member = await members.find_by_id("analyst")
        member.role = "viewer"
        await members.save(member)
        await receipt.authorize()
        stages.append("generation")
        return {}

    domains.query = AsyncMock(side_effect=query)
    with pytest.raises(AccessDenied):
        await facade.query("issuer|analyst", "north", dataset_id=dataset, question="Count")
    assert stages == ["grounding"]
