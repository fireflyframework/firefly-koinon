# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest

from koinon.app import create_application
from koinon.catalog.repositories import AuditRepository, MembershipRepository

spec = importlib.util.spec_from_file_location(
    "deployment_bootstrap", Path(__file__).resolve().parents[1] / "bootstrap.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.asyncio
async def test_native_bootstrap_refuses_existing_tenant_and_noncanonical_subject(
    tmp_path,
):
    issuer = "https://identity.example/realm"
    application = create_application(
        {
            "koinon": {
                "security": {
                    "issuer": issuer,
                    "jwks_uri": issuer + "/certs",
                    "client_id": "browser",
                    "api_audience": "api",
                    "authorization_uri": issuer + "/auth",
                    "token_uri": issuer + "/token",
                    "redirect_uri": "https://api.example/login/oauth2/code/koinon",
                },
                "legacy": {"enabled": False},
                "knowledge": {"enabled": False},
            },
            "pyfly": {
                "session": {"store": "memory", "concurrency": {"registry": "memory"}},
                "data": {
                    "relational": {
                        "enabled": True,
                        "url": f"sqlite+aiosqlite:///{tmp_path / 'bootstrap.db'}",
                        "ddl-auto": "create",
                    }
                },
            },
        }
    )
    context = application.state.context
    await context.start()
    try:
        with pytest.raises(ValueError):
            await module.bootstrap(
                context, issuer, "north", "North", "email@example.test"
            )
        result = await module.bootstrap(
            context, issuer, "north", "North", issuer + "|verified-sub"
        )
        assert result["tenant_id"] == "north"
        with pytest.raises(ValueError):
            await module.bootstrap(
                context, issuer, "north", "Replace", issuer + "|another-sub"
            )
        members = await context.get_bean(MembershipRepository).find_all(
            tenant_id="north"
        )
        assert (
            len(members) == 1
            and members[0].subject == issuer + "|verified-sub"
            and members[0].role == "admin"
        )
        audits = await context.get_bean(AuditRepository).find_all(tenant_id="north")
        assert len(audits) == 1 and audits[0].action == "tenant.bootstrap"
    finally:
        await context.stop()


def test_operator_modes_are_explicit_and_mutually_exclusive(tmp_path):
    base = ["--tenant-id", "new-org", "--name", "New organization"]
    with pytest.raises(SystemExit):
        module.arguments(base)
    with pytest.raises(SystemExit):
        module.arguments(
            [*base, "--subject", "issuer|sub", "--identity-grants-file", "grants.json"]
        )
    assert (
        module.arguments([*base, "--subject", "issuer|sub"]).identity_grants_file
        is None
    )
    assert (
        module.arguments([*base, "--identity-grants-file", "grants.json"]).subject
        is None
    )
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * 65537)
    with pytest.raises(ValueError, match="64 KiB"):
        module.load_identity_grants(oversized)
