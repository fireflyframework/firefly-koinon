# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Cleanup remains a worker capability when account and synchronization APIs are disabled."""

import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config
from test_connection_lifecycle import lifecycle as lifecycle
from test_mapping_review import review as review
from test_source_migration_postgres import source_database as source_database
from test_validation_postgres import validation_service as validation_service

from koinon.integrations.content_sources.configuration import register_source_accounts
from koinon.integrations.content_sources.credentials import SourceCredentialVault
from koinon.integrations.content_sources.lifecycle import SourceConnectionService
from koinon.integrations.content_sources.mapping_validation_entities import SourceMappingValidation
from koinon.integrations.content_sources.mapping_validation_repository import (
    SourceMappingValidationRepository,
)
from koinon.integrations.content_sources.validation_maintenance import SourceValidationMaintenance
from koinon.security.authority import primary_authority
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


def test_disabled_worker_resolves_cleanup_without_provider_credentials():
    values = {"koinon": {"process": {"role": "worker"}, "content_sources": {"enabled": False}}}
    context = ApplicationContext(Config(values))
    context.container.register_instance(WorkAdmission, WorkAdmission(WorkAdmissionSettings()))
    register_source_accounts(context, values, controllers=False)
    cleanup = context.get_bean(SourceValidationMaintenance)
    assert isinstance(cleanup.records, SourceMappingValidationRepository)
    assert not context.container.contains_type(SourceCredentialVault)
    assert not context.container.contains_type(SourceConnectionService)


def test_api_process_does_not_activate_validation_cleanup():
    values = {"koinon": {"process": {"role": "api"}}}
    context = ApplicationContext(Config(values))
    register_source_accounts(context, values, controllers=True)
    assert not context.container.contains_type(SourceValidationMaintenance)


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_abandoned_preparation_cleanup_releases_only_transient_payload_without_remote_io(
    validation_service,
):
    service, body, provider = validation_service
    result = await service.begin_validation("issuer|alice", "tenant", "browser-a", body)
    abandoned = await service.abandon_validation(
        "issuer|alice", "tenant", "browser-a", result.validation_id, result.revision
    )
    assert abandoned.state == "cleaning"
    service.settings.enabled = service.settings.synchronization_enabled = False
    before = dict(provider)
    cleanup = SourceValidationMaintenance(service.records, service.admission)
    assert not await cleanup.cleanup()
    async with primary_authority():
        row = await service.records._require_session().get(SourceMappingValidation, result.validation_id)
        assert row.state == "abandoned" and row.payload_released_at is not None
        assert row.request_ciphertext is row.root_proof_ciphertext is None
        assert row.reserved_bytes < 8192 and row.expires_at == result.expires_at
    assert provider == before
