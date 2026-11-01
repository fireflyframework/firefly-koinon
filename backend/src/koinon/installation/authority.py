# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A primary database capability, never a synthetic user or HTTP permission."""

from dataclasses import dataclass, field
from datetime import timedelta
from hashlib import sha256
from json import dumps
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional

from koinon.communications.welcome import installation_identity
from koinon.installation.dtos import InstallationPlan
from koinon.installation.entities import InstallationRun
from koinon.installation.repositories import InstallationRepository

ACTOR = "system:installation"


class InstallationError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class InstallationPermit:
    run_id: str
    tenant_id: str
    generation: int
    owner: str = field(repr=False)
    completed: bool = False


@service(name="installation.admissions")
class InstallationAdmissions:
    def __init__(self, runs: InstallationRepository):
        self.runs = runs

    async def _operator(self):
        if not await self.runs.operator_capable():
            raise InstallationError("INSTALLATION_OPERATOR_REQUIRED")

    @transactional(read_from_primary=True)
    async def admit(self, plan: InstallationPlan, *, resume: bool) -> InstallationPermit:
        await self._operator()
        now = await self.runs.clock()
        identity = await installation_identity(self.runs._require_session(), now)
        identifier = sha256(
            dumps([identity.installation_id, plan.tenant_id, plan.plan_key]).encode()
        ).hexdigest()
        row = await self.runs.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row is not None:
            if row.plan_sha256 != plan.fingerprint():
                raise InstallationError("INSTALLATION_PLAN_CONFLICT")
            if row.status == "completed":
                return InstallationPermit(row.id, row.tenant_id, row.generation, "", completed=True)
            now = await self.runs.clock()
            if row.status == "running" and row.lease_until is not None and row.lease_until > now:
                raise InstallationError("INSTALLATION_IN_PROGRESS")
            if not resume:
                raise InstallationError("INSTALLATION_RESUME_REQUIRED")
            row.generation += 1
        else:
            if resume:
                raise InstallationError("INSTALLATION_NOT_STARTED")
            row = InstallationRun(
                id=identifier,
                installation_id=identity.installation_id,
                tenant_id=plan.tenant_id,
                plan_key=plan.plan_key,
                plan_sha256=plan.fingerprint(),
                status="running",
                generation=1,
                checkpoints={},
                created_at=now,
                updated_at=now,
            )
        owner = str(uuid4())
        row.owner_sha256 = sha256(owner.encode()).hexdigest()
        row.lease_until, row.status, row.updated_at = now + timedelta(seconds=120), "running", now
        await self.runs.save(row)
        return InstallationPermit(row.id, row.tenant_id, row.generation, owner)

    async def require(self, permit: InstallationPermit) -> InstallationRun:
        await self._operator()
        row = await self.runs.find_by_id(permit.run_id, lock=LockMode.PESSIMISTIC_WRITE)
        now = await self.runs.clock()
        if (
            row is None
            or permit.completed
            or row.tenant_id != permit.tenant_id
            or row.status != "running"
            or row.generation != permit.generation
            or row.owner_sha256 != sha256(permit.owner.encode()).hexdigest()
            or row.lease_until is None
            or row.lease_until <= now
        ):
            raise InstallationError("INSTALLATION_LEASE_LOST")
        return row

    @transactional(read_from_primary=True)
    async def renew(self, permit: InstallationPermit):
        row = await self.require(permit)
        now = await self.runs.clock()
        row.lease_until, row.updated_at = now + timedelta(seconds=120), now
        await self.runs.save(row)

    async def checkpoint(self, permit: InstallationPermit, key: str, value: dict):
        row = await self.require(permit)
        previous = row.checkpoints.get(key)
        if previous is not None and previous != value:
            raise InstallationError("INSTALLATION_CHECKPOINT_CONFLICT")
        row.checkpoints = {**row.checkpoints, key: value}
        row.updated_at = await self.runs.clock()
        await self.runs.save(row)

    @transactional(read_from_primary=True)
    async def fail(self, permit: InstallationPermit):
        row = await self.require(permit)
        row.status, row.lease_until, row.updated_at = "partial", None, await self.runs.clock()
        await self.runs.save(row)

    @transactional(read_from_primary=True)
    async def finish(self, permit: InstallationPermit):
        row = await self.require(permit)
        now = await self.runs.clock()
        row.status, row.owner_sha256, row.lease_until = "completed", None, None
        row.updated_at = now
        await self.runs.save(row)

    @transactional(read_only=True, read_from_primary=True)
    async def receipt(self, permit: InstallationPermit) -> dict:
        await self._operator()
        row = await self.runs.find_by_id(permit.run_id)
        if row is None or row.tenant_id != permit.tenant_id:
            raise InstallationError("INSTALLATION_NOT_STARTED")
        return {
            "run_id": row.id,
            "tenant_id": row.tenant_id,
            "plan_key": row.plan_key,
            "plan_sha256": row.plan_sha256,
            "status": row.status,
            "generation": row.generation,
            "checkpoints": row.checkpoints,
        }
