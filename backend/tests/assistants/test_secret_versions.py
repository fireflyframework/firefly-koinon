# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pyfly.agentic.security.encryption import AESEncryptionProvider

from koinon.assistants.settings import AssistantSettings, ProviderSecrets


def test_existing_provider_credentials_survive_package_rename():
    master = b"a" * 32
    historical_key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"lattice-provider-v1|north|provider"
    ).derive(master)
    stored = b"\x01" + AESEncryptionProvider(historical_key).encrypt("fictional-key").encode("ascii")
    secrets = ProviderSecrets(AssistantSettings(master_key=base64.urlsafe_b64encode(master).decode()))
    assert secrets.decrypt("north", "provider", stored) == "fictional-key"
    for tenant, provider in [("south", "provider"), ("north", "other")]:
        with pytest.raises(ValueError):
            secrets.decrypt(tenant, provider, stored)


def test_new_credentials_use_versioned_koinon_key_domain():
    master = b"a" * 32
    secrets = ProviderSecrets(AssistantSettings(master_key=base64.urlsafe_b64encode(master).decode()))
    stored = secrets.encrypt("north", "provider", "fictional-key")
    assert stored[0] == 2
    assert secrets.decrypt("north", "provider", stored) == "fictional-key"
    for invalid in [b"", b"\x03" + stored[1:]]:
        with pytest.raises(ValueError, match="Unsupported encrypted credential format"):
            secrets.decrypt("north", "provider", invalid)
