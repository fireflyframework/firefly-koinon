# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native operator orchestration checkpoints each committed step independently."""

import asyncio
from contextlib import suppress
from types import SimpleNamespace

from pydantic import SecretStr
from pyfly.container import service

from koinon.assistants.connections import ConnectionResolver
from koinon.assistants.probe import ProviderProbe
from koinon.installation.authority import InstallationAdmissions, InstallationError
from koinon.installation.dtos import InstallationPlan
from koinon.installation.indexes import NativeInstallationIndexes
from koinon.installation.qualification import NativeInstallationQualification
from koinon.installation.writes import NativeInstallationWrites, fingerprint


@service(name="installation.provisioner")
class InstallationProvisioner:
    def __init__(
        self,
        admissions: InstallationAdmissions,
        writes: NativeInstallationWrites,
        indexes: NativeInstallationIndexes,
        probe: ProviderProbe,
        qualification: NativeInstallationQualification,
        compiler: ConnectionResolver,
    ):
        self.admissions, self.writes, self.indexes = admissions, writes, indexes
        self.probe, self.qualification, self.compiler = probe, qualification, compiler

    def validate(self, plan: InstallationPlan):
        providers = {value.key: value for value in plan.providers}
        for provider in plan.providers:
            self.compiler.address(provider.kind, provider.base_url)
        for selection in [*plan.connections, plan.agent]:
            provider = providers[selection.provider_key]
            self.compiler.spec(
                SimpleNamespace(kind=provider.kind, api=provider.api, base_url=provider.base_url),
                selection.model_id,
                selection.model_options.model_dump(mode="json", exclude_none=True),
            )

    async def apply(
        self, plan: InstallationPlan, secrets: dict[str, SecretStr | None], *, resume: bool = False
    ):
        self.validate(plan)
        permit = await self.admissions.admit(plan, resume=resume)
        if permit.completed:
            return await self.admissions.receipt(permit)
        try:
            for provider in plan.providers:
                await self.admissions.renew(permit)
                await self.writes.provider(permit, provider, secrets.get(provider.key))
                receipt = await self.admissions.receipt(permit)
                if "discovery:" + provider.key in receipt["checkpoints"]:
                    continue
                snapshot = await self.writes.probe_snapshot(permit, provider.key)
                checks = await self.probe.check(
                    snapshot.kind,
                    snapshot.base_url,
                    snapshot.model_ids,
                    snapshot.secret.get_secret_value() if snapshot.secret else None,
                    api=snapshot.api,
                )
                if not all(
                    any(check.get("id") == key and check.get("status") == "passed" for check in checks)
                    for key in ("connection", "models")
                ):
                    raise InstallationError("INSTALLATION_PROVIDER_DISCOVERY_FAILED")
                await self.writes.save_discovery(permit, provider.key, snapshot, checks)
            for selection in [*plan.connections, plan.agent]:
                await self.admissions.renew(permit)
                tools = selection is plan.agent and bool(plan.agent.tools)
                options = selection.model_options.model_dump(mode="json", exclude_none=True)
                key = "qualified:" + fingerprint(
                    {
                        "provider_key": selection.provider_key,
                        "model_id": selection.model_id,
                        "options": options,
                        "tools": tools,
                    }
                )
                receipt = await self.admissions.receipt(permit)
                if key in receipt["checkpoints"]:
                    continue
                snapshot = await self.writes.probe_snapshot(permit, selection.provider_key)
                try:
                    await self.qualification.qualify(
                        snapshot, selection.model_id, selection.model_options, require_tools=tools
                    )
                except Exception:
                    raise InstallationError("INSTALLATION_PROVIDER_QUALIFICATION_FAILED") from None
                await self.writes.qualified(
                    permit,
                    selection.provider_key,
                    snapshot,
                    selection.model_id,
                    selection.model_options,
                    require_tools=tools,
                )
            nodes = {value.key: value for value in plan.catalog}
            for key in plan.catalog_order():
                await self.admissions.renew(permit)
                await self.writes.catalog_node(permit, nodes[key])
            for index in plan.indexes:
                for operation in (
                    self.indexes.intent,
                    self.indexes.create,
                    self.indexes.ready,
                    self.indexes.activate,
                ):
                    await self.admissions.renew(permit)
                    await operation(permit, index)
            for connection in plan.connections:
                await self.admissions.renew(permit)
                await self.writes.connection(permit, connection)
            await self.admissions.renew(permit)
            await self.writes.agent(permit, plan.agent)
            if plan.agent.set_default_if_empty:
                await self.writes.default_agent(permit, plan.agent.key)
            await self.admissions.finish(permit)
            return await self.admissions.receipt(permit)
        except BaseException:
            # A lost lease must never be reacquired implicitly after an external outcome.
            with suppress(Exception):
                await asyncio.shield(self.admissions.fail(permit))
            raise
