# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Recognize only the pristine 26.11.1 intent whose managed default was not checkpointed."""

from hashlib import sha256
from json import dumps

from koinon.installation.authority import ACTOR, InstallationError
from koinon.installation.writes import NativeInstallationWrites, fingerprint, resource_id
from koinon.knowledge.connections.service import embedding_fingerprint
from koinon.knowledge.indexes.adapters import index_id


def legacy_intent(permit, value, run, *, reconciled=False):
    key = "index-intent:" + value.key
    allowed = {key, "index-intent-reconciled:" + value.key} if reconciled else {key}
    if (
        permit.generation <= 1
        or run.generation != permit.generation
        or {key for key in run.checkpoints if key.startswith("index-")} != allowed
        or any(key.startswith(("connection:", "agent:")) or key == "default_agent" for key in run.checkpoints)
    ):
        raise InstallationError("INSTALLATION_MANUAL_CHANGE")
    workspace = resource_id(permit, "catalog:" + value.workspace_key)
    provider = resource_id(permit, "provider:" + value.provider_key)
    if (
        NativeInstallationWrites.reference(run, "catalog", value.workspace_key) != workspace
        or NativeInstallationWrites.reference(run, "provider", value.provider_key) != provider
    ):
        raise InstallationError("INSTALLATION_MANUAL_CHANGE")
    native = ("es-" if value.domain == "documents" else "fs-") + resource_id(
        permit, "index:" + value.key
    ).replace("-", "")
    identifier = index_id(permit.tenant_id, workspace, value.domain, native)
    original = run.checkpoints[key]
    if original != {
        "status": "done",
        "resource_id": identifier,
        "dimensions": value.dimensions,
        "revision": None,
        "row_status": "queued",
    }:
        raise InstallationError("INSTALLATION_MANUAL_CHANGE")
    return workspace, provider, native, identifier, original


def pristine_descriptor(permit, value, run, row, provider, workspace, native, identifier):
    revision = run.checkpoints["provider:" + value.provider_key]["revision"]
    if type(revision) is not int or provider.revision != revision or revision != 1:
        raise InstallationError("INSTALLATION_MANUAL_CHANGE")
    width = 1536 if value.domain == "structured" else value.dimensions
    expected = {
        "id": identifier,
        "tenant_id": permit.tenant_id,
        "workspace_id": workspace,
        "native_workspace_id": workspace,
        "domain": value.domain,
        "native_id": native,
        "provider_id": provider.id,
        "provider_kind": provider.kind,
        "provider_revision": revision,
        "model_id": value.model_id,
        "dimensions": value.dimensions,
        "storage_dimensions": width,
        "embedding_fingerprint": embedding_fingerprint(provider, value.model_id, value.dimensions, width),
        "status": "queued",
        "revision": 1,
        "build_slot": sha256(dumps([permit.tenant_id, value.domain, workspace]).encode()).hexdigest(),
        "active_slot": None,
        "job_id": None,
        "cursor": {},
        "transition": {},
        "previous_binding": None,
        "access_token_id": None,
        "batch_size": 32,
        "chunk_count": 0,
        "vector_count": 0,
        "indexed": False,
        "qualification": "probe_passed",
        "error_code": None,
        "error": None,
        "created_by": ACTOR,
        "updated_by": ACTOR,
        "ready_at": None,
        "activated_at": None,
        "retired_at": None,
    }
    if row is None or any(getattr(row, key) != value for key, value in expected.items()):
        raise InstallationError("INSTALLATION_MANUAL_CHANGE")
    return fingerprint(expected)


def validate_reconciled(permit, value, run, row, provider):
    workspace, _, native, identifier, original = legacy_intent(permit, value, run, reconciled=True)
    descriptor = pristine_descriptor(permit, value, run, row, provider, workspace, native, identifier)
    receipt = run.checkpoints["index-intent-reconciled:" + value.key]
    generation = receipt.get("generation")
    if (
        type(generation) is not int
        or type(receipt.get("revision")) is not int
        or not 2 <= generation <= permit.generation
        or receipt
        != {
            "status": "done",
            "resource_id": identifier,
            "dimensions": value.dimensions,
            "revision": 1,
            "row_status": "queued",
            "generation": generation,
            "source_checkpoint_sha256": fingerprint(original),
            "descriptor_sha256": descriptor,
            "reason": "repository_defaults_26_11_1",
        }
    ):
        raise InstallationError("INSTALLATION_MANUAL_CHANGE")
