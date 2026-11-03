# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Encrypted credentials bound to the owning user, connection and operation purpose."""

import base64
import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pyfly.agentic.security.encryption import AESEncryptionProvider
from pyfly.container import component
from pyfly.kernel import ServiceUnavailableException

from koinon.integrations.content_sources.dtos import bounded
from koinon.integrations.content_sources.settings import ContentSourceSettings


@component(name="content_sources.credentials")
class SourceCredentialVault:
    def __init__(self, settings: ContentSourceSettings):
        self.settings = settings

    def _cipher(self, tenant_id: str, owner: str, connection_id: str, purpose: str):
        context = [bounded(value) for value in (tenant_id, owner, connection_id, purpose)]
        try:
            master = base64.b64decode(self.settings.master_key, altchars=b"-_", validate=True)
            if len(master) != 32:
                raise ValueError
        except (ValueError, TypeError):
            raise ServiceUnavailableException(
                "Source credentials require a deployment encryption key.",
                code="SOURCE_SECRET_STORAGE_UNCONFIGURED",
            ) from None
        # Length-delimited JSON fields avoid collisions when canonical subjects contain '|'.
        info = json.dumps(["koinon-content-source-v1", *context], separators=(",", ":")).encode()
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(master)
        return AESEncryptionProvider(key)

    def encrypt(self, tenant_id: str, owner: str, connection_id: str, purpose: str, value: dict) -> bytes:
        payload = json.dumps(value, separators=(",", ":"))
        if len(payload.encode()) > 262144:
            raise ValueError("Source credential exceeds the envelope limit")
        return b"\x01" + self._cipher(tenant_id, owner, connection_id, purpose).encrypt(payload).encode(
            "ascii"
        )

    def decrypt(self, tenant_id: str, owner: str, connection_id: str, purpose: str, envelope: bytes) -> dict:
        try:
            if not envelope or envelope[0] != 1 or len(envelope) > 524288:
                raise ValueError
            payload = self._cipher(tenant_id, owner, connection_id, purpose).decrypt(
                envelope[1:].decode("ascii")
            )
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise ValueError
            return value
        except Exception:
            raise ServiceUnavailableException(
                "Source credential is unavailable.",
                code="SOURCE_CREDENTIAL_UNAVAILABLE",
            ) from None
