# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64

import pytest
from pyfly.kernel import ServiceUnavailableException

from koinon.corporate_identity.dtos import EntraCredential
from koinon.corporate_identity.settings import IdentityCredentialStore, IdentitySettings


def test_native_encrypted_credentials_are_bound_to_tenant_provider_and_purpose():
    key = base64.b64encode(bytes(range(32))).decode()
    settings = IdentitySettings(master_key=key)
    assert key not in repr(settings)
    store = IdentityCredentialStore(settings)
    credential = EntraCredential(kind="entra", secret="synthetic-secret-no-cloud-use")
    encrypted = store.encrypt("north", "provider", credential)
    assert b"synthetic-secret-no-cloud-use" not in encrypted
    assert (
        store.decrypt("north", "provider", encrypted).secret.get_secret_value()
        == "synthetic-secret-no-cloud-use"
    )
    for tenant, provider in (("south", "provider"), ("north", "other")):
        with pytest.raises(ServiceUnavailableException):
            store.decrypt(tenant, provider, encrypted)
    with pytest.raises(ServiceUnavailableException):
        IdentityCredentialStore(IdentitySettings()).encrypt("north", "provider", credential)


def test_invalid_decrypted_payload_never_leaks_secret_in_an_exception_chain():
    import traceback

    store = IdentityCredentialStore(IdentitySettings(master_key=base64.b64encode(bytes(range(32))).decode()))
    content = '{"kind":"unsupported","secret":"synthetic-must-not-log"}'
    encrypted = b"\x01" + store._cipher("north", "provider").encrypt(content).encode("ascii")
    with pytest.raises(ServiceUnavailableException) as caught:
        store.decrypt("north", "provider", encrypted)
    assert "synthetic-must-not-log" not in "".join(traceback.format_exception(caught.value))
