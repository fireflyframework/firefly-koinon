# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ServiceUnavailableException
from test_directory_people import ENTRA, GOOGLE, KEYCLOAK, USER

from koinon.communications.directory import RecipientDirectory
from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.settings import IdentitySettings


@pytest.fixture
def native():
    directory = NativeCorporateDirectory(IdentitySettings(allowed_provider_hosts=["identity.test"]))
    directory.acquire = AsyncMock(return_value="test-fixture-token")
    directory._json = AsyncMock()
    return directory


async def test_fresh_read_uses_fixed_id_endpoint_and_bounded_native_transport(native):
    native._json.return_value = dict(
        id=USER, accountEnabled=True, userType="Member", mail="person@example.test"
    )
    service = RecipientDirectory(native)
    result = await service.read(ENTRA, None, USER)
    assert result.external_subject == USER
    url = native._json.call_args.args[0]
    assert url == "https://graph.microsoft.com/v1.0/users/" + USER
    assert "accountEnabled" in native._json.call_args.kwargs["params"]["$select"]
    native._json.return_value = dict(
        id="other", accountEnabled=True, userType="Member", mail="person@example.test"
    )
    with pytest.raises(ServiceUnavailableException):
        await service.read(ENTRA, None, USER)


async def test_keycloak_and_google_user_lookup_preserve_immutable_id(native):
    service = RecipientDirectory(native)
    native._json.return_value = dict(id=USER, enabled=True, emailVerified=True, email="person@example.test")
    await service.read(KEYCLOAK, None, USER)
    assert native._json.call_args.args[0] == "https://identity.test/admin/realms/people/users/" + USER
    native._json.return_value = dict(
        id=USER, customerId="customer", suspended=False, primaryEmail="person@example.test"
    )
    await service.read(GOOGLE, None, USER)
    assert native._json.call_args.args[0] == "https://admin.googleapis.com/admin/directory/v1/users/" + USER


async def test_search_limits_results_and_rejects_foreign_graph_cursor(native):
    native._json.return_value = {
        "value": [dict(id=USER, accountEnabled=True, userType="Member", mail="person@example.test")]
    }
    service = RecipientDirectory(native)
    results, cursor = await service.search(ENTRA, None, q="O'Brien", limit=20)
    assert len(results) == 1 and cursor is None
    assert "O''Brien" in native._json.call_args.kwargs["params"]["$filter"]
    assert native._json.call_args.kwargs["params"]["$top"] == 20
    native._json.reset_mock()
    for after in (
        "https://other.test/v1.0/users",
        "https://graph.microsoft.com/v1.0/groups",
        "https://user@graph.microsoft.com/v1.0/users",
    ):
        with pytest.raises(ServiceUnavailableException):
            await service.search(ENTRA, None, q="Person", limit=20, after=after)
    native._json.assert_not_called()
    with pytest.raises(ServiceUnavailableException):
        await service.search(ENTRA, None, q="Person", limit=21)


async def test_directory_error_is_redacted(native):
    native._json.side_effect = RuntimeError("private token and person@example.test")
    with pytest.raises(ServiceUnavailableException) as error:
        await RecipientDirectory(native).read(ENTRA, None, USER)
    assert "private token" not in str(error.value) and "person@example.test" not in str(error.value)
