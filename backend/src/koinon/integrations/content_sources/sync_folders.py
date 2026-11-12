# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Publish remote hierarchy as canonical collections with retained source provenance."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from pyfly.container import service
from pyfly.kernel import ConflictException
from sqlalchemy import Text, cast, func, select

from koinon.catalog.entities import CatalogEntry
from koinon.catalog.hierarchy_service import CatalogHierarchyService
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.source_publication import (
    SourcePublicationWriter,
    SourceWriteOperation,
)
from koinon.integrations.content_sources.sync_entities import (
    SourceFolderBinding,
    SourceFolderPublication,
    SourceMappingPolicy,
    SourceSyncObservation,
    SourceSyncRun,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_runs import SourceRunLease
from koinon.knowledge.bulk.ports import SourceIntakeAdmission
from koinon.security.authority import primary_authority


def folder_hash(name, parent, workspace, project, kind):
    return hashlib.sha256(
        json.dumps(
            ["koinon.folder-fields.v1", name, parent, workspace, project, kind], ensure_ascii=False
        ).encode()
    ).hexdigest()


def stored_folder_hash():
    return func.encode(
        func.sha256(
            func.convert_to(
                cast(
                    func.jsonb_build_array(
                        "koinon.folder-fields.v1",
                        CatalogEntry.name,
                        CatalogEntry.parent_id,
                        CatalogEntry.workspace_id,
                        CatalogEntry.project_id,
                        CatalogEntry.kind,
                    ),
                    Text,
                ),
                "UTF8",
            )
        ),
        "hex",
    )


def conflict():
    return ConflictException("Source hierarchy or local folder changed", code="SOURCE_FOLDER_CONFLICT")


@service(name="content_sources.folders")
class SourceFolders:
    def __init__(self, writer: SourcePublicationWriter):
        self.writer = writer

    async def publish(self, admission: SourceIntakeAdmission, execution: SourceRunLease) -> str:
        if not admission.items or not isinstance(execution, SourceRunLease):
            raise conflict()
        async with (
            self.writer.prepare(admission, execution=execution),
            primary_authority(read_only=False, fresh=True),
            self.writer.fence(admission),
        ):
            session = self.writer.intake._require_session()
            pin = admission.items[0]
            mapping = await session.get(SourceMapping, admission.mapping_id)
            origin = await session.get(SourceObject, pin.object_id)
            run = await session.get(SourceSyncRun, admission.run_id)
            policy = await session.get(SourceMappingPolicy, run.policy_id)
            observation = await session.get(SourceSyncObservation, pin.observation_id)
            work = await session.get(SourceSyncWork, pin.work_id)
            request = MappingReviewInput.model_validate(policy.policy_json["request"])
            event = observation.event_json
            item, ancestry = event.get("item", {}), event.get("ancestry", [])
            name = item.get("name")
            if (
                request.hierarchy != "preserve"
                or item.get("kind") != "folder"
                or not isinstance(name, str)
                or not name.strip()
                or len(name.strip()) > 255
                or not ancestry
                or item.get("parents") != [ancestry[-1]]
                or origin.remote_kind != "folder"
                or work.attempt_id is not None
            ):
                raise conflict()
            parent = mapping.parent_id
            if ancestry[-1] != mapping.root_id:
                parent_binding = await session.get(
                    SourceFolderBinding,
                    (
                        admission.tenant_id,
                        admission.mapping_id,
                        ancestry[-1],
                    ),
                )
                if parent_binding is None:
                    raise conflict()
                parent = parent_binding.local_folder_id
            if parent != admission.destination[2]:
                raise conflict()
            binding = await session.get(
                SourceFolderBinding,
                (
                    admission.tenant_id,
                    admission.mapping_id,
                    origin.item_id,
                ),
            )
            previous = await session.scalar(
                select(SourceFolderPublication)
                .where(
                    SourceFolderPublication.tenant_id == admission.tenant_id,
                    SourceFolderPublication.mapping_id == admission.mapping_id,
                    SourceFolderPublication.object_id == origin.id,
                )
                .order_by(SourceFolderPublication.canonical_revision.desc())
                .limit(1)
            )
            catalog = self.writer.authority.catalog
            if previous is None:
                if binding is not None or origin.published_local_revision is not None:
                    raise conflict()
                target, kind = str(uuid4()), "collection"
                changes = dict(kind=kind, name=name.strip(), description="", metadata={})
                operation = SourceWriteOperation("create", target, parent, changes)
                operations = (operation,)
            else:
                if binding is None or binding.local_folder_id != previous.local_folder_id:
                    raise conflict()
                target = binding.local_folder_id
                local = (
                    await session.execute(
                        select(
                            CatalogEntry.mutation_revision,
                            CatalogEntry.parent_id,
                            CatalogEntry.kind,
                            CatalogEntry.status,
                            stored_folder_hash(),
                        ).where(CatalogEntry.id == target, CatalogEntry.tenant_id == admission.tenant_id)
                    )
                ).one_or_none()
                if (
                    local is None
                    or local[0] != previous.canonical_revision
                    or local[4] != previous.canonical_sha256
                    or local[3] != "ready"
                    or origin.published_local_revision != str(previous.canonical_revision)
                    or origin.published_sha256 != previous.canonical_sha256
                ):
                    raise conflict()
                if previous.observation_id == observation.id:
                    return target
                kind = local[2]
                changes = {"name": name.strip()}
                moving = local[1] != parent
                operation = SourceWriteOperation("update", target, parent, changes, local[0] + int(moving))
                operations = (
                    (
                        SourceWriteOperation("move", target, local[1], {"parent_id": parent}, local[0]),
                        operation,
                    )
                    if moving
                    else (operation,)
                )
            async with self.writer.open(admission, operations) as permit:
                if previous is None:
                    node = await catalog.create(
                        admission.owner,
                        admission.tenant_id,
                        parent_id=parent,
                        **changes,
                        _source_create_id=target,
                        _source_write=permit,
                    )
                else:
                    if moving:
                        await CatalogHierarchyService(catalog).move(
                            admission.owner,
                            admission.tenant_id,
                            target,
                            parent_id=parent,
                            expected_parent_id=local[1],
                            _source_parent_id=local[1],
                            _source_write=permit,
                        )
                    node = await catalog.update(
                        admission.owner,
                        admission.tenant_id,
                        target,
                        changes,
                        _source_parent_id=parent,
                        _source_write=permit,
                    )
                digest = folder_hash(name.strip(), parent, *admission.destination[:2], kind)
                publication = SourceFolderPublication(
                    id=str(uuid4()),
                    tenant_id=admission.tenant_id,
                    mapping_id=mapping.id,
                    object_id=origin.id,
                    observation_id=observation.id,
                    work_id=work.id,
                    local_folder_id=target,
                    local_parent_id=parent,
                    canonical_revision=node.mutation_revision,
                    canonical_sha256=digest,
                    previous_publication_id=previous.id if previous else None,
                )
                await catalog._audit(
                    admission.owner,
                    admission.tenant_id,
                    "source.folder.published",
                    target,
                    {
                        "publication_id": publication.id,
                        "object_id": origin.id,
                        "observation_id": observation.id,
                        "work_id": work.id,
                        "canonical_revision": node.mutation_revision,
                        "canonical_sha256": digest,
                    },
                )
                session.add(publication)
                await session.flush()
                if binding is None:
                    binding = SourceFolderBinding(
                        tenant_id=admission.tenant_id,
                        mapping_id=mapping.id,
                        remote_folder_id=origin.item_id,
                        local_folder_id=target,
                        local_parent_id=parent,
                        remote_parent_id=ancestry[-1],
                        ancestry_json=ancestry,
                        revision=1,
                    )
                    session.add(binding)
                else:
                    binding.local_parent_id, binding.remote_parent_id = parent, ancestry[-1]
                    binding.ancestry_json, binding.revision = ancestry, binding.revision + 1
                    binding.updated_at = datetime.now(UTC)
                origin.state, origin.published_local_revision = "imported", str(node.mutation_revision)
                origin.published_sha256, origin.published_native_version_id = digest, None
                origin.remote_name, origin.remote_parent_id = item["name"], ancestry[-1]
                origin.remote_ancestry_json = ancestry
                work.status, work.error_code = "imported", None
                await session.flush()
            return target
