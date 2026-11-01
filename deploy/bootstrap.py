# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Create a new tenant and its first canonical administrator through native Data."""

import argparse
import asyncio
import re
from pathlib import Path
from uuid import uuid4


async def bootstrap(
    context, issuer: str, tenant_id: str, name: str, subject: str
) -> dict[str, str]:
    from pyfly.data.transaction import TransactionTemplate
    from pyfly.data.transaction.registry import TransactionManagerRegistry

    from koinon.catalog.entities import AuditEvent, Membership, Tenant
    from koinon.catalog.repositories import (
        AuditRepository,
        MembershipRepository,
        TenantRepository,
    )

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", tenant_id):
        raise ValueError(
            "Supply a new tenant identifier of at most 64 URL-safe characters"
        )
    if not name.strip() or len(name) > 160:
        raise ValueError("Supply a tenant name of at most 160 characters")
    if (
        not subject.startswith(issuer + "|")
        or not subject[len(issuer) + 1 :]
        or len(subject) > 512
    ):
        raise ValueError(
            "Subject must be the exact configured issuer followed by | and the verified sub claim"
        )
    tenants = context.get_bean(TenantRepository)
    members = context.get_bean(MembershipRepository)
    audits = context.get_bean(AuditRepository)
    manager = context.get_bean(TransactionManagerRegistry).get("primary")
    member_id = str(uuid4())
    async with TransactionTemplate(manager).transaction():
        if await tenants.find_by_id(tenant_id) is not None:
            raise ValueError(
                "Tenant already exists; use its authorized membership administration workflow"
            )
        await tenants.save(Tenant(id=tenant_id, name=name))
        await members.save(
            Membership(id=member_id, subject=subject, tenant_id=tenant_id, role="admin")
        )
        from koinon.communications.settings import CommunicationsSettings
        from koinon.communications.welcome import WelcomeAdmissions

        if (
            context.container.contains_type(CommunicationsSettings)
            and context.get_bean(CommunicationsSettings).enabled
        ):
            await context.get_bean(WelcomeAdmissions).admit(subject, tenant_id)
        await audits.save(
            AuditEvent(
                id=str(uuid4()),
                tenant_id=tenant_id,
                subject="system:bootstrap",
                action="tenant.bootstrap",
                resource_id=member_id,
                details={"initial_administrator": subject},
            )
        )
    return {"tenant_id": tenant_id, "membership_id": member_id}


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--name", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--subject",
        help="Exact canonical subject obtained from verified application SSO",
    )
    mode.add_argument(
        "--identity-grants-file",
        type=Path,
        help="Reviewed pending direct-Entra grant file; requires an operator database role",
    )
    return parser.parse_args(argv)


def load_identity_grants(path: Path):
    from koinon.bootstrap.dtos import BootstrapSeedInput

    if not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("Supply a reviewed bootstrap grant file of at most 64 KiB")
    with path.open("rb") as stream:
        value = stream.read(65537)
    if len(value) > 65536:
        raise ValueError("Supply a reviewed bootstrap grant file of at most 64 KiB")
    return BootstrapSeedInput.model_validate_json(value)


async def main():
    args = arguments()
    from koinon.main import app
    from koinon.security.settings import OidcSettings

    context = app.state.context
    await context.start()
    try:
        issuer = context.get_bean(OidcSettings).issuer
        if args.identity_grants_file is not None:
            from koinon.bootstrap.service import BootstrapGrants

            count = await context.get_bean(BootstrapGrants).seed(
                args.tenant_id,
                args.name,
                load_identity_grants(args.identity_grants_file),
            )
            print(
                "Created new tenant with pending verified-login grants:",
                args.tenant_id,
                count,
            )
        else:
            result = await bootstrap(
                context, issuer, args.tenant_id, args.name, args.subject
            )
            print("Created new tenant and initial administrator:", result["tenant_id"])
    finally:
        await context.stop()


if __name__ == "__main__":
    asyncio.run(main())
