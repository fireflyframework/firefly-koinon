# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import ValidationError


def test_index_preconditions_are_required_nullable_and_identity_credentials_are_private():
    from koinon_sdk.identity import (
        GoogleCredential,
        IdentityProviderInput,
        KeycloakCredential,
        KeycloakSettings,
    )
    from koinon_sdk.indexes import IndexCreateInput

    values = {"workspace_id": "w", "domain": "documents", "provider_id": "p", "model_id": "nomic"}
    with pytest.raises(ValidationError):
        IndexCreateInput(**values)
    index = IndexCreateInput(**values, expected_active_id=None, expected_connection_revision=None)
    assert index.model_dump(mode="json", exclude_unset=True)["expected_active_id"] is None
    secret = "never-print-selected-secret"
    provider = IdentityProviderInput(
        kind="keycloak",
        name="Company",
        settings=KeycloakSettings(kind="keycloak", issuer="https://identity.test/realm", client_id="app"),
        credential=KeycloakCredential(kind="keycloak", secret=secret),
    )
    assert secret not in repr(provider) and secret not in repr(provider.credential)
    google = GoogleCredential(
        kind="google_workspace",
        service_account_email="service@example.test",
        private_key="private-test-key",
        delegated_admin="admin@example.test",
    )
    assert google.secret is None and "private-test-key" not in repr(google)
