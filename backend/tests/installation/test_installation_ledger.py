# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.sqlalchemy import Base
from sqlalchemy import create_engine, func, select
from test_installation_manifest import example

from koinon.catalog.entities import Tenant
from koinon.communications.entities import InstallationRecord
from koinon.installation.authority import InstallationAdmissions, InstallationError
from koinon.installation.dtos import InstallationPlan
from koinon.installation.entities import InstallationRun
from koinon.installation.repositories import InstallationRepository


async def test_unprivileged_lane_cannot_admit_or_even_create_installation_identity(tmp_path):
    path = tmp_path / "installer.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(
        engine, tables=[Tenant.__table__, InstallationRecord.__table__, InstallationRun.__table__]
    )
    engine.dispose()
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{path}",
                        }
                    },
                }
            }
        )
    )
    for bean in (InstallationRepository, InstallationAdmissions):
        context.register_bean(bean)
    await context.start()
    try:
        with pytest.raises(InstallationError, match="INSTALLATION_OPERATOR_REQUIRED"):
            await context.get_bean(InstallationAdmissions).admit(
                InstallationPlan.model_validate(example()), resume=False
            )
    finally:
        await context.stop()
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(InstallationRecord)) == 0
        assert connection.scalar(select(func.count()).select_from(InstallationRun)) == 0
    engine.dispose()
