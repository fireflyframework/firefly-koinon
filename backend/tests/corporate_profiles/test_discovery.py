# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config

from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.repositories import CorporateProviderRepository
from koinon.corporate_identity.settings import IdentityCredentialStore, IdentitySettings
from koinon.corporate_profiles.controllers import CorporateProfilesController
from koinon.corporate_profiles.refresh import CorporateProfileRefresher
from koinon.corporate_profiles.service import CorporateProfileService
from koinon.corporate_profiles.settings import CorporateProfileSettings
from koinon.corporate_profiles.worker import CorporateProfileWorker
from koinon.organization_people.service import OrganizationPeopleService
from koinon.profiles.service import ProfileService


async def test_native_module_discovery_wires_projector_and_worker_without_provider_requests(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'discovery.db'}",
                        }
                    },
                }
            }
        )
    )
    for package in (
        "koinon.catalog",
        "koinon.profiles",
        "koinon.organization_people",
        "koinon.corporate_profiles",
    ):
        scan_package(package, context.container)
    context.container.register(CorporateProviderRepository)
    context.container.register_instance(
        CorporateProfileSettings, CorporateProfileSettings(worker_enabled=False)
    )
    context.container.register_instance(IdentityCredentialStore, IdentityCredentialStore(IdentitySettings()))
    native = SimpleNamespace(acquire=AsyncMock(), http=SimpleNamespace(request_bounded=AsyncMock()))
    context.container.register_instance(NativeCorporateDirectory, native)
    await context.start()
    try:
        service = context.get_bean(CorporateProfileService)
        assert context.get_bean(OrganizationPeopleService).presentation is service.projector
        assert context.get_bean(ProfileService).presentation is service.projector
        assert context.get_bean(CorporateProfilesController).profiles is service
        assert context.get_bean(CorporateProfileRefresher).people is service.people
        await context.get_bean(CorporateProfileWorker).tick()
        native.acquire.assert_not_awaited()
        native.http.request_bounded.assert_not_awaited()
    finally:
        await context.stop()
