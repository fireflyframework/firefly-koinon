# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import traceback

import pytest
from pyfly.kernel import ServiceUnavailableException


def test_source_credentials_are_bound_to_owner_tenant_connection_and_purpose():
    from koinon.integrations.content_sources.credentials import SourceCredentialVault
    from koinon.integrations.content_sources.settings import ContentSourceSettings

    vault = SourceCredentialVault(
        ContentSourceSettings(master_key=base64.b64encode(bytes(range(32))).decode())
    )
    protected = {"refresh_token": "synthetic-refresh", "access_token": "synthetic-access"}
    envelope = vault.encrypt("tenant-a", "issuer|reader", "connection-a", "grant", protected)
    assert b"synthetic" not in envelope
    assert vault.decrypt("tenant-a", "issuer|reader", "connection-a", "grant", envelope) == protected
    for tenant, owner, connection, purpose in (
        ("tenant-b", "issuer|reader", "connection-a", "grant"),
        ("tenant-a", "issuer|importer", "connection-a", "grant"),
        ("tenant-a", "issuer|reader", "connection-b", "grant"),
        ("tenant-a", "issuer|reader", "connection-a", "authorization"),
    ):
        with pytest.raises(ServiceUnavailableException, match="Source credential is unavailable") as error:
            vault.decrypt(tenant, owner, connection, purpose, envelope)
        assert "synthetic" not in "".join(traceback.format_exception(error.value))


def test_ambiguous_delimiter_fields_cannot_share_a_credential_key():
    from koinon.integrations.content_sources.credentials import SourceCredentialVault
    from koinon.integrations.content_sources.settings import ContentSourceSettings

    vault = SourceCredentialVault(
        ContentSourceSettings(master_key=base64.b64encode(bytes(range(32))).decode())
    )
    envelope = vault.encrypt("a|b", "c", "connection", "grant", {"token": "synthetic"})
    with pytest.raises(ServiceUnavailableException, match="Source credential is unavailable"):
        vault.decrypt("a", "b|c", "connection", "grant", envelope)


def test_missing_vault_key_fails_closed_without_creating_ephemeral_credentials():
    from koinon.integrations.content_sources.credentials import SourceCredentialVault
    from koinon.integrations.content_sources.settings import ContentSourceSettings

    with pytest.raises(ServiceUnavailableException, match="deployment encryption key"):
        SourceCredentialVault(ContentSourceSettings()).encrypt("tenant", "reader", "connection", "grant", {})
