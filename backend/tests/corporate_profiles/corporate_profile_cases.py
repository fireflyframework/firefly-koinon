# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.security.context import SecurityContext

from koinon.corporate_identity.entities import CorporateProvider
from koinon.corporate_identity.repositories import CorporateProviderRepository

A = "https://issuer|admin"
B = "https://issuer|member"
C = "https://issuer|colleague"
H = "https://issuer|hidden"
W = "https://issuer|workspace-admin"
S = "https://issuer|south-admin"


async def provider(d, tenant="north", identifier="provider"):
    row = CorporateProvider(
        id=identifier,
        tenant_id=tenant,
        kind="keycloak",
        name="Corporate directory",
        canonical_issuer="https://issuer",
        source_key=identifier,
        status="active",
        settings_json={"kind": "keycloak", "issuer": "https://issuer", "client_id": "browser"},
        created_by=A,
        updated_by=A,
    )
    await d.context.get_bean(CorporateProviderRepository).save(row)
    return row


def claims(subject="member", **values):
    return SecurityContext(user_id=subject, attributes={"iss": "https://issuer", "sub": subject, **values})
