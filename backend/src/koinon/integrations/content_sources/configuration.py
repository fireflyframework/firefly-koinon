# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Register account and browsing services without activating synchronization."""

from pyfly.context import ApplicationContext
from pyfly.core import Config

from koinon.catalog.ports import SourceCatalogPolicy
from koinon.integrations.content_sources.account_operation_maintenance import SourceAccountMaintenance
from koinon.integrations.content_sources.account_operation_repository import SourceAccountOperationRepository
from koinon.integrations.content_sources.browse import PersonalSourceBrowser
from koinon.integrations.content_sources.controllers import (
    ContentConnectionsController,
    SourceCapabilitiesController,
)
from koinon.integrations.content_sources.credentials import SourceCredentialVault
from koinon.integrations.content_sources.lifecycle import SourceConnectionService
from koinon.integrations.content_sources.mapping_validation_repository import (
    SourceMappingValidationRepository,
)
from koinon.integrations.content_sources.presentation import SourcePresentation
from koinon.integrations.content_sources.process_readiness import register_source_process
from koinon.integrations.content_sources.read_authority import SourceReadAuthority
from koinon.integrations.content_sources.read_cursors import SourceBrowseCursors
from koinon.integrations.content_sources.read_native import SourceReadNative
from koinon.integrations.content_sources.read_repository import SourceReadRepository
from koinon.integrations.content_sources.read_service import SourceReader
from koinon.integrations.content_sources.reader_access import PersonalSourceAccess
from koinon.integrations.content_sources.reader_selection_controller import SourceReaderSelectionController
from koinon.integrations.content_sources.reader_selection_repository import SourceReaderSelectionRepository
from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections
from koinon.integrations.content_sources.registrations import SourceRegistrations
from koinon.integrations.content_sources.repositories import (
    SourceChallengeRepository,
    SourceConnectionRepository,
)
from koinon.integrations.content_sources.sessions import SourceBrowserSessions
from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.sync_intake import SourceSyncIntake
from koinon.integrations.content_sources.validation_maintenance import SourceValidationMaintenance
from koinon.knowledge.bulk.ports import SourceIntakeGuard, SourcePublicationFence
from koinon.web.projection import register_controller
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


def register_source_accounts(context: ApplicationContext, config: dict, *, controllers: bool) -> None:
    if not context.container.contains_type(WorkAdmissionSettings):
        context.container.register_instance(WorkAdmissionSettings, Config(config).bind(WorkAdmissionSettings))
    if not context.container.contains_type(WorkAdmission):
        context.register_bean(WorkAdmission)
    # Retained imports keep their source fences when account management is disabled.
    for cls in (
        SourceReadRepository,
        SourceReadAuthority,
        SourceReaderSelectionRepository,
        SourceReaderSelections,
        SourceReadNative,
        SourceBrowseCursors,
        SourceReader,
        SourceSyncIntake,
        SourceMappingValidationRepository,
    ):
        context.register_bean(cls)
    if Config(config).get("koinon.process.role") == "worker":
        context.register_bean(SourceAccountOperationRepository)
        context.register_bean(SourceAccountMaintenance)
        context.register_bean(SourceValidationMaintenance)
    context.container.bind(SourceCatalogPolicy, SourceReader)
    context.container.bind(SourceIntakeGuard, SourceSyncIntake)
    context.container.bind(SourcePublicationFence, SourceSyncIntake)
    settings = Config(config).bind(ContentSourceSettings)
    context.container.register_instance(ContentSourceSettings, settings)
    context.register_bean(SourcePresentation)
    if controllers:
        register_controller(context, SourceCapabilitiesController)
    if not settings.enabled:
        return
    settings.transport_options()
    registrations = SourceRegistrations(settings)
    for provider in settings.providers:
        registrations.get(provider)
    # Reject invalid encryption before making any account endpoint available.
    SourceCredentialVault(settings)._cipher("validation", "validation", "validation", "validation")
    for cls in (
        SourceRegistrations,
        SourceCredentialVault,
        SourceConnectionRepository,
        SourceChallengeRepository,
        SourceBrowserSessions,
        SourceConnectionService,
        PersonalSourceBrowser,
        PersonalSourceAccess,
    ):
        context.register_bean(cls)
    if controllers:
        register_controller(context, ContentConnectionsController)
        register_controller(context, SourceReaderSelectionController)


def register_source_synchronization(context: ApplicationContext, *, controllers: bool) -> None:
    """Compose the qualified source layer; deployment activation is a separate gate."""
    from koinon.integrations.content_sources.account_operations import SourceAccountOperations
    from koinon.integrations.content_sources.mapping_api import SourceMappingController
    from koinon.integrations.content_sources.mapping_policies import SourcePolicies, SourcePolicyRepository
    from koinon.integrations.content_sources.mapping_preview import SourceMappingPreview
    from koinon.integrations.content_sources.mapping_repository import SourceMappingRepository
    from koinon.integrations.content_sources.mapping_review import SourceMappingReviews
    from koinon.integrations.content_sources.mapping_service import SourceMappings
    from koinon.integrations.content_sources.mapping_validation import SourceMappingValidations
    from koinon.integrations.content_sources.mapping_validation_api import SourceMappingValidationController
    from koinon.integrations.content_sources.source_publication import SourcePublicationWriter
    from koinon.integrations.content_sources.sync_controls import SourceControlRepository
    from koinon.integrations.content_sources.sync_files import SourceFiles
    from koinon.integrations.content_sources.sync_folders import SourceFolders
    from koinon.integrations.content_sources.sync_heartbeat import SourceSyncHeartbeat
    from koinon.integrations.content_sources.sync_replacement import SourceReplacements
    from koinon.integrations.content_sources.sync_runs import SourceRunRepository
    from koinon.integrations.content_sources.sync_worker import SourceSyncWorker
    from koinon.knowledge.bulk.authority import BulkAuthority
    from koinon.knowledge.bulk.ports import SourceIntakeWriter
    from koinon.knowledge.bulk.repositories import BulkRepository

    context.get_bean(ContentSourceSettings).synchronization_options()
    if context.get_bean(ContentSourceSettings).synchronization_enabled:
        register_source_process(context)
    for dependency in (BulkRepository, BulkAuthority):
        if not context.container.contains_type(dependency):
            context.register_bean(dependency)

    for cls in (
        SourceMappingRepository,
        SourcePolicyRepository,
        SourceMappingReviews,
        SourceMappingPreview,
        SourcePolicies,
        SourceControlRepository,
        SourceMappings,
        SourcePublicationWriter,
        SourceMappingValidations,
        SourceAccountOperations,
    ):
        context.register_bean(cls)
    context.container.bind(SourceIntakeWriter, SourcePublicationWriter)
    if (
        context.config.get("koinon.process.role") == "worker"
        and context.get_bean(ContentSourceSettings).synchronization_enabled
    ):
        for cls in (
            SourceFolders,
            SourceFiles,
            SourceReplacements,
            SourceRunRepository,
            SourceSyncHeartbeat,
            SourceSyncWorker,
        ):
            context.register_bean(cls)
    if controllers:
        register_controller(context, SourceMappingController)
        register_controller(context, SourceMappingValidationController)
