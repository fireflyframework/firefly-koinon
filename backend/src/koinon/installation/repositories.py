# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, select, text

from koinon.installation.entities import InstallationRun


@repository(name="installation.runs")
class InstallationRepository(Repository[InstallationRun, str]):
    async def operator_capable(self) -> bool:
        session = self._require_session()
        if session.get_bind().dialect.name != "postgresql":
            return False
        return bool(
            await session.scalar(
                text(
                    "SELECT has_table_privilege(current_user,'public.koinon_installation_runs','INSERT') "
                    "AND has_table_privilege(current_user,'public.koinon_installation_runs','UPDATE')"
                )
            )
        )

    async def clock(self) -> datetime:
        session = self._require_session()
        expression = (
            func.clock_timestamp()
            if session.get_bind().dialect.name == "postgresql"
            else func.current_timestamp()
        )
        value = await session.scalar(select(expression))
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise RuntimeError("Installation requires the primary database clock")
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
