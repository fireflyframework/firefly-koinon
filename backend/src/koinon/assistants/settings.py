# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pyfly.agentic.security.encryption import AESEncryptionProvider
from pyfly.container import component
from pyfly.core import config_properties
from pyfly.kernel import ServiceUnavailableException


@component(name="assistants.settings")
@config_properties(prefix="koinon.assistants")
@dataclass
class AssistantSettings:
    master_key: str = field(default="", repr=False)
    allowed_provider_hosts: list[str] = field(default_factory=list)
    run_timeout_seconds: int = 180
    lease_seconds: int = 60
    max_history_messages: int = 40
    max_history_tokens: int = 8192
    max_context_tokens: int = 32768
    tool_result_tokens: int = 4096


@component(name="assistants.secrets")
class ProviderSecrets:
    def __init__(self, settings: AssistantSettings):
        self.settings = settings

    def _cipher(self, tenant_id: str, provider_id: str, version: int = 2) -> AESEncryptionProvider:
        try:
            key = base64.b64decode(self.settings.master_key, altchars=b"-_", validate=True)
            if len(key) != 32:
                raise ValueError("Invalid key length")
        except (ValueError, TypeError) as exc:
            raise ServiceUnavailableException(
                "Provider secret storage requires an external 32-byte master key",
                code="SECRET_STORAGE_UNCONFIGURED",
            ) from exc
        # Existing credentials retain their original key derivation domain after a package rename.
        domain = "lattice-provider-v1" if version == 1 else "koinon-provider-v2"
        scope = f"{domain}|{tenant_id}|{provider_id}".encode()
        bound_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=scope).derive(key)
        return AESEncryptionProvider(bound_key)

    def encrypt(self, tenant_id: str, provider_id: str, secret: str) -> bytes:
        return b"\x02" + self._cipher(tenant_id, provider_id).encrypt(secret).encode("ascii")

    def decrypt(self, tenant_id: str, provider_id: str, ciphertext: bytes) -> str:
        if len(ciphertext) < 30 or ciphertext[0] not in (1, 2):
            raise ValueError("Unsupported encrypted credential format")
        return self._cipher(tenant_id, provider_id, ciphertext[0]).decrypt(ciphertext[1:].decode("ascii"))
