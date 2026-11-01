# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr
from pyfly.context import ApplicationContext
from pyfly.core import Config

from koinon.installation.authority import InstallationError, InstallationPermit
from koinon.installation.dtos import ProviderInstallation
from koinon.installation.writes import NativeInstallationWrites


async def test_operator_ports_do_not_resolve_domain_services_without_database_capability(tmp_path):
    admissions = AsyncMock()
    admissions.require.side_effect = InstallationError("INSTALLATION_OPERATOR_REQUIRED")
    dependencies = [AsyncMock() for _ in range(4)]
    writer = NativeInstallationWrites(admissions, *dependencies)
    provider = ProviderInstallation(
        key="chat",
        name="Chat",
        kind="openai",
        api="chat",
        base_url="https://api.openai.com/v1",
        model_ids=["model"],
        secret_env="INSTALL_KEY",
    )
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'ports.db'}",
                        }
                    },
                }
            }
        )
    )
    await context.start()
    try:
        with pytest.raises(InstallationError, match="INSTALLATION_OPERATOR_REQUIRED"):
            await writer.provider(
                InstallationPermit("run", "tenant", 1, "owner"), provider, SecretStr("not-a-real-key")
            )
    finally:
        await context.stop()
    for dependency in dependencies:
        dependency.get.assert_not_called()
