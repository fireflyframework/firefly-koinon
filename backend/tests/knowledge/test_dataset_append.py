# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_facade import context as context
from test_facade import upload


def append_service(context):
    from koinon.knowledge.dataset_append import DatasetFiles

    facade, _, domains, _, _ = context
    domains.append_dataset_file = AsyncMock(
        return_value={
            "file_id": str(uuid4()),
            "tables": [
                {
                    "table_id": str(uuid4()),
                    "name": name,
                    "snapshot_id": str(uuid4()),
                    "n_columns": 2,
                    "n_rows_estimate": 3,
                }
                for name in ("Sales", "Returns")
            ],
        }
    )
    return DatasetFiles(facade)


async def test_append_preserves_dataset_and_binds_every_new_sheet_to_its_file(context):
    facade, catalog, domains, _, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    result = await service.append(
        "issuer|admin",
        "north",
        dataset,
        filename="more.xlsx",
        content=b"sheet bytes",
        idempotency_key="append-test-key",
    )
    assert result.dataset_id == dataset
    assert len(result.table_ids) == 2
    assert result.filename == "more.xlsx"
    assert result.byte_size == len(b"sheet bytes")
    assert domains.ingest_dataset.await_count == 1
    assert domains.append_dataset_file.await_args.kwargs["dataset_id"] == "native-dataset"
    assert domains.append_dataset_file.await_args.kwargs["actor"] == "issuer|admin"
    for table_id, native in zip(
        result.table_ids, domains.append_dataset_file.return_value["tables"], strict=True
    ):
        table = await catalog.get("issuer|admin", "north", table_id)
        binding = await facade.binding("north", table_id, "structured", entry=table)
        assert table.parent_id == dataset
        assert table.status == "ready"
        assert binding.native_id == native["table_id"]
        assert binding.details_json["file_id"] == domains.append_dataset_file.return_value["file_id"]
    file = await catalog.get("issuer|admin", "north", result.file_version_id)
    assert file.kind == "index_version" and file.parent_id == dataset and file.status == "ready"
    assert file.metadata_json["operation"] == "dataset.append_file"
    assert (await catalog.get("issuer|admin", "north", dataset)).status == "ready"


async def test_append_rejects_reader_and_alias_before_native_effects(context):
    from pyfly.kernel import ConflictException

    from koinon.catalog.errors import AccessDenied

    facade, catalog, domains, _, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    with pytest.raises(AccessDenied):
        await service.append(
            "issuer|reader",
            "north",
            dataset,
            filename="a.csv",
            content=b"a\n1",
            idempotency_key="append-test-key",
        )
    binding = await facade.binding("north", dataset, "structured")
    original = await catalog.get("issuer|admin", "north", dataset)
    alias = await catalog.create(
        "issuer|admin", "north", kind="dataset", name="alias", parent_id=original.parent_id
    )
    await facade._bind(
        "issuer|admin", "north", alias, "structured", binding.native_id, binding.native_workspace_id
    )
    with pytest.raises(ConflictException) as error:
        await service.append(
            "issuer|admin",
            "north",
            dataset,
            filename="a.csv",
            content=b"a\n1",
            idempotency_key="append-test-key",
        )
    assert error.value.code == "DATASET_APPEND_ALIAS_CONFLICT"
    domains.append_dataset_file.assert_not_awaited()


async def test_failure_leaves_dataset_unavailable_and_retry_does_not_repeat_native_effects(context):
    from pyfly.kernel import ConflictException

    facade, catalog, domains, _, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    domains.append_dataset_file.side_effect = RuntimeError("second section failed")
    with pytest.raises(RuntimeError):
        await service.append(
            "issuer|admin",
            "north",
            dataset,
            filename="more.xlsx",
            content=b"sheets",
            idempotency_key="append-test-key",
        )
    assert (await catalog.get("issuer|admin", "north", dataset)).status == "error"
    with pytest.raises(ConflictException) as error:
        await facade.query("issuer|admin", "north", dataset_id=dataset, question="sum")
    assert error.value.code == "DATASET_NOT_READY"
    with pytest.raises(ConflictException):
        await facade.schema("issuer|admin", "north", dataset_id=dataset)
    with pytest.raises(ConflictException):
        await service.append(
            "issuer|admin",
            "north",
            dataset,
            filename="more.xlsx",
            content=b"sheets",
            idempotency_key="append-test-key",
        )
    assert domains.append_dataset_file.await_count == 1


async def test_second_append_cannot_enter_while_first_is_in_progress(context):
    from pyfly.kernel import ConflictException

    _, _, domains, _, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    result = domains.append_dataset_file.return_value

    async def during(**kwargs):
        with pytest.raises(ConflictException) as error:
            await service.append(
                "issuer|admin",
                "north",
                dataset,
                filename="other.csv",
                content=b"x\n2",
                idempotency_key="append-test-key",
            )
        assert error.value.code == "IDEMPOTENCY_CONFLICT"
        return result

    domains.append_dataset_file.side_effect = during
    await service.append(
        "issuer|admin", "north", dataset, filename="a.csv", content=b"x\n1", idempotency_key="append-test-key"
    )
    assert domains.append_dataset_file.await_count == 1


async def test_revocation_during_ingestion_prevents_canonical_publication(context):
    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.repositories import MembershipRepository

    _, catalog, domains, _, app = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    result = domains.append_dataset_file.return_value

    async def revoke(**kwargs):
        repo = app.get_bean(MembershipRepository)
        member = await repo.find_by_id("admin")
        member.active = False
        await repo.save(member)
        return result

    domains.append_dataset_file.side_effect = revoke
    with pytest.raises(AccessDenied):
        await service.append(
            "issuer|admin",
            "north",
            dataset,
            filename="a.csv",
            content=b"x\n1",
            idempotency_key="append-test-key",
        )
    assert not await catalog.list("issuer|reader", "north", kind="table", parent_id=dataset)
    domains.query.assert_not_awaited()


async def test_partial_projection_rolls_back_and_preserves_the_previous_table(context, monkeypatch):
    facade, catalog, domains, _, _ = context
    previous = {"table_id": str(uuid4()), "name": "First", "snapshot_id": str(uuid4())}
    domains.ingest_dataset.return_value["tables"] = [previous]
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    before = (await catalog.list("issuer|admin", "north", kind="table", parent_id=dataset))[0]
    service = append_service(context)
    bind = facade._bind
    created = []

    async def fail_second(subject, tenant, entry, *args, **kwargs):
        if entry.kind == "table":
            created.append(entry.id)
            if len(created) == 2:
                raise RuntimeError("projection unavailable")
        return await bind(subject, tenant, entry, *args, **kwargs)

    monkeypatch.setattr(facade, "_bind", fail_second)
    with pytest.raises(RuntimeError):
        await service.append(
            "issuer|admin",
            "north",
            dataset,
            filename="more.xlsx",
            content=b"sheets",
            idempotency_key="append-test-key",
        )
    tables = await catalog.list("issuer|admin", "north", kind="table", parent_id=dataset)
    assert [table.id for table in tables] == [before.id]
    retained = await facade.binding("north", before.id, "structured")
    assert retained.native_id == previous["table_id"]
    assert retained.details_json["snapshot_id"] == previous["snapshot_id"]
    for identifier in created:
        assert not await facade.bindings.find_all(tenant_id="north", catalog_id=identifier)


async def test_colliding_native_table_identity_is_refused_without_rebinding(context):
    from pyfly.kernel import ConflictException

    facade, catalog, domains, _, _ = context
    previous = {"table_id": str(uuid4()), "name": "First", "snapshot_id": str(uuid4())}
    domains.ingest_dataset.return_value["tables"] = [previous]
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    domains.append_dataset_file.return_value["tables"][1]["table_id"] = previous["table_id"]
    with pytest.raises(ConflictException) as error:
        await service.append(
            "issuer|admin",
            "north",
            dataset,
            filename="more.xlsx",
            content=b"sheets",
            idempotency_key="append-test-key",
        )
    assert error.value.code == "DATASET_APPEND_CONFLICT"
    assert len(await catalog.list("issuer|admin", "north", kind="table", parent_id=dataset)) == 1


async def test_table_replacement_cannot_clear_an_active_append_publication_claim(context):
    from pyfly.kernel import ConflictException
    from test_content import updates

    _, catalog, domains, _, _ = context
    domains.ingest_dataset.return_value["tables"] = [
        {"table_id": str(uuid4()), "name": "First", "snapshot_id": "snapshot-old"}
    ]
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    table = (await catalog.list("issuer|admin", "north", kind="table", parent_id=dataset))[0]
    content = updates(context)
    service = append_service(context)
    result = domains.append_dataset_file.return_value

    async def during(**kwargs):
        with pytest.raises(ConflictException) as error:
            await content.table(
                "issuer|admin",
                "north",
                dataset,
                table.id,
                filename="changed.csv",
                content=b"x\n3",
                expected_snapshot_id="snapshot-old",
            )
        assert error.value.code == "DATASET_NOT_READY"
        return result

    domains.append_dataset_file.side_effect = during
    await service.append(
        "issuer|admin",
        "north",
        dataset,
        filename="more.csv",
        content=b"x\n2",
        idempotency_key="append-test-key",
    )
    domains.reupload_table.assert_not_awaited()


async def test_public_metadata_edits_cannot_erase_failed_append_authority_state(context):
    from pyfly.kernel import ConflictException
    from test_content import updates

    facade, catalog, domains, _, _ = context
    domains.ingest_dataset.return_value["tables"] = [
        {"table_id": str(uuid4()), "name": "First", "snapshot_id": "snapshot-old"}
    ]
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    table = (await catalog.list("issuer|admin", "north", kind="table", parent_id=dataset))[0]
    content = updates(context)
    service = append_service(context)
    domains.append_dataset_file.side_effect = RuntimeError("partial native commit")
    with pytest.raises(RuntimeError):
        await service.append(
            "issuer|admin",
            "north",
            dataset,
            filename="more.csv",
            content=b"x\n2",
            idempotency_key="append-test-key",
        )
    await catalog.update("issuer|admin", "north", dataset, {"metadata": {"note": "edited"}})
    with pytest.raises(ConflictException) as error:
        await content.table(
            "issuer|admin",
            "north",
            dataset,
            table.id,
            filename="changed.csv",
            content=b"x\n3",
            expected_snapshot_id="snapshot-old",
        )
    assert error.value.code == "DATASET_NOT_READY"
    domains.reupload_table.assert_not_awaited()
    with pytest.raises(ConflictException):
        await facade.query("issuer|admin", "north", dataset_id=dataset, question="sum")


async def test_private_intake_state_cannot_be_forged_or_returned_in_catalog_json(context):
    from koinon.catalog.errors import InvalidHierarchy
    from koinon.catalog.mappers import entry_dto

    _, catalog, _, tree, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    for operation in (
        lambda: catalog.update("issuer|admin", "north", dataset, {"metadata": {"_koinon_intake": None}}),
        lambda: catalog.create(
            "issuer|admin",
            "north",
            kind="source",
            name="forged",
            parent_id=tree["collection"].id,
            metadata={"_koinon_intake": {"version_id": "forged"}},
        ),
    ):
        with pytest.raises(InvalidHierarchy) as error:
            await operation()
        assert error.value.code == "RESERVED_METADATA"
    entry = await catalog.get("issuer|admin", "north", dataset)
    entry.metadata_json = {**entry.metadata_json, "_koinon_intake": {"version_id": "internal"}}
    assert "_koinon_intake" not in entry_dto(entry)["metadata"]


async def test_changed_file_version_inputs_prevent_publication_of_a_false_receipt(context):
    from pyfly.kernel import ConflictException

    _, catalog, domains, _, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    result = domains.append_dataset_file.return_value

    async def edit_during_ingest(**kwargs):
        version = (await catalog.list("issuer|admin", "north", kind="index_version", parent_id=dataset))[0]
        await catalog.update(
            "issuer|admin",
            "north",
            version.id,
            {
                "name": "edited.csv",
                "metadata": {
                    **{key: value for key, value in version.metadata_json.items() if key != "_koinon_intake"},
                    "sha256": "a" * 64,
                    "bytes": 1,
                },
            },
        )
        return result

    domains.append_dataset_file.side_effect = edit_during_ingest
    with pytest.raises(ConflictException) as error:
        await service.append(
            "issuer|admin",
            "north",
            dataset,
            filename="actual.csv",
            content=b"x\n2",
            idempotency_key="append-test-key",
        )
    assert error.value.code == "DATASET_APPEND_CONFLICT"
    assert not await catalog.list("issuer|admin", "north", kind="table", parent_id=dataset)


async def test_completed_key_replays_exact_receipt_without_native_work_after_metadata_edit(context):
    _, catalog, domains, _, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    first = await service.append(
        "issuer|admin",
        "north",
        dataset,
        filename="more.csv",
        content=b"x\n2",
        idempotency_key="stable-request",
    )
    await catalog.update("issuer|admin", "north", first.file_version_id, {"metadata": {"note": "edited"}})
    second = await service.append(
        "issuer|admin",
        "north",
        dataset,
        filename="more.csv",
        content=b"x\n2",
        idempotency_key="stable-request",
    )
    assert second.model_dump() == first.model_dump()
    assert domains.append_dataset_file.await_count == 1


async def test_same_key_different_content_conflicts_and_receipt_cannot_be_deleted(context):
    from pyfly.kernel import ConflictException

    _, catalog, domains, _, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    first = await service.append(
        "issuer|admin",
        "north",
        dataset,
        filename="more.csv",
        content=b"x\n2",
        idempotency_key="stable-request",
    )
    with pytest.raises(ConflictException) as error:
        await service.append(
            "issuer|admin",
            "north",
            dataset,
            filename="more.csv",
            content=b"x\n3",
            idempotency_key="stable-request",
        )
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    with pytest.raises(ConflictException) as error:
        await catalog.delete("issuer|admin", "north", first.file_version_id)
    assert error.value.code == "INTAKE_RECEIPT_IMMUTABLE"
    assert domains.append_dataset_file.await_count == 1


async def test_replay_requires_current_write_permissions(context):
    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.repositories import MembershipRepository

    _, _, domains, _, app = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    await service.append(
        "issuer|admin",
        "north",
        dataset,
        filename="more.csv",
        content=b"x\n2",
        idempotency_key="stable-request",
    )
    repo = app.get_bean(MembershipRepository)
    member = await repo.find_by_id("admin")
    member.role = "viewer"
    await repo.save(member)
    with pytest.raises(AccessDenied):
        await service.append(
            "issuer|admin",
            "north",
            dataset,
            filename="more.csv",
            content=b"x\n2",
            idempotency_key="stable-request",
        )
    assert domains.append_dataset_file.await_count == 1


async def test_exact_same_key_cannot_repeat_native_work_while_request_is_in_progress(context):
    from pyfly.kernel import ConflictException

    _, _, domains, _, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    result = domains.append_dataset_file.return_value

    async def repeat(**kwargs):
        with pytest.raises(ConflictException) as error:
            await service.append(
                "issuer|admin",
                "north",
                dataset,
                filename="more.csv",
                content=b"x\n2",
                idempotency_key="stable-request",
            )
        assert error.value.code == "DATASET_NOT_READY"
        return result

    domains.append_dataset_file.side_effect = repeat
    await service.append(
        "issuer|admin",
        "north",
        dataset,
        filename="more.csv",
        content=b"x\n2",
        idempotency_key="stable-request",
    )
    assert domains.append_dataset_file.await_count == 1


@pytest.mark.parametrize(
    "filename,key", [(" more.csv", "key"), ("more.csv ", "key"), ("more.csv", ""), ("more.csv", "bad\r\nkey")]
)
async def test_noncanonical_filename_and_invalid_keys_are_rejected_before_native_effects(
    context, filename, key
):
    from pyfly.kernel import InvalidRequestException

    _, _, domains, _, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    service = append_service(context)
    with pytest.raises(InvalidRequestException):
        await service.append(
            "issuer|admin", "north", dataset, filename=filename, content=b"x\n2", idempotency_key=key
        )
    domains.append_dataset_file.assert_not_awaited()
