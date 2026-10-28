# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import json
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import SecretStr, TypeAdapter
from pyfly.agentic.security.encryption import AESEncryptionProvider
from pyfly.container import component
from pyfly.core import config_properties
from pyfly.kernel import ServiceUnavailableException

from koinon.corporate_identity.dtos import ProviderCredential


@component(name="identity.settings")
@config_properties(prefix="koinon.identity")
@dataclass
class IdentitySettings:
    master_key: str = field(default="", repr=False)
    allowed_provider_hosts: list[str] = field(default_factory=list)
    allowed_provider_origins: list[str] = field(default_factory=list)
    snapshot_ttl_seconds: int = 60
    broker_admin_client_id: str = ""
    broker_admin_secret: str = field(default="", repr=False)

    def __post_init__(self):
        if not 1 <= self.snapshot_ttl_seconds <= 300:
            raise ValueError("Corporate group observations expire within five minutes")


@component(name="identity.credentials")
class IdentityCredentialStore:
    def __init__(self, settings: IdentitySettings):
        self.settings = settings

    def _cipher(self, tenant_id: str, provider_id: str):
        try:
            master = base64.b64decode(self.settings.master_key, altchars=b"-_", validate=True)
            if len(master) != 32:
                raise ValueError("Invalid key size")
        except (ValueError, TypeError) as exc:
            raise ServiceUnavailableException(
                "Corporate credentials require a deployment encryption key.",
                code="IDENTITY_SECRET_STORAGE_UNCONFIGURED",
            ) from exc
        key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=f"koinon-corporate-identity-v1|{tenant_id}|{provider_id}".encode(),
        ).derive(master)
        return AESEncryptionProvider(key)

    def encrypt(self, tenant_id: str, provider_id: str, credential: ProviderCredential) -> bytes:
        def reveal(value):
            if isinstance(value, SecretStr):
                return value.get_secret_value()
            raise TypeError("Unsupported credential value")

        content = json.dumps(credential.model_dump(exclude_none=True), default=reveal, separators=(",", ":"))
        return b"\x01" + self._cipher(tenant_id, provider_id).encrypt(content).encode("ascii")

    def decrypt(self, tenant_id: str, provider_id: str, ciphertext: bytes) -> ProviderCredential:
        try:
            if not ciphertext or ciphertext[0] != 1:
                raise ValueError("Unknown credential envelope")
            content = self._cipher(tenant_id, provider_id).decrypt(ciphertext[1:].decode("ascii"))
            return TypeAdapter(ProviderCredential).validate_json(content)
        except Exception:
            raise ServiceUnavailableException(
                "Corporate credential is unavailable.", code="IDENTITY_CREDENTIAL_UNAVAILABLE"
            ) from None
