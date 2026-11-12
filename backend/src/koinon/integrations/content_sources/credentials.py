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

    @staticmethod
    def _limits(purpose: str) -> tuple[int, int]:
        envelope = {
            "validation-request": 2097152,
            "validation-root": 1048576,
            "validation-checkpoint": 1048576,
            "validation-walk": 8388608,
            "validation-entry": 16384,
        }.get(purpose)
        if envelope is None:
            return 262144, 524288
        # The installed cipher encodes salt(16), nonce(12), ciphertext and tag(16)
        # as base64; our envelope prepends one version byte.
        return ((envelope - 1) // 4) * 3 - 44, envelope

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
        plain_limit, envelope_limit = self._limits(purpose)
        if len(payload.encode()) > plain_limit:
            raise ValueError("Source credential exceeds the envelope limit")
        envelope = b"\x01" + self._cipher(tenant_id, owner, connection_id, purpose).encrypt(payload).encode(
            "ascii"
        )
        if len(envelope) > envelope_limit:
            raise ValueError("Source credential exceeds the envelope limit")
        return envelope

    def decrypt(self, tenant_id: str, owner: str, connection_id: str, purpose: str, envelope: bytes) -> dict:
        try:
            plain_limit, envelope_limit = self._limits(purpose)
            if not envelope or envelope[0] != 1 or len(envelope) > envelope_limit:
                raise ValueError
            payload = self._cipher(tenant_id, owner, connection_id, purpose).decrypt(
                envelope[1:].decode("ascii")
            )
            if len(payload.encode()) > plain_limit:
                raise ValueError
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise ValueError
            return value
        except Exception:
            raise ServiceUnavailableException(
                "Source credential is unavailable.",
                code="SOURCE_CREDENTIAL_UNAVAILABLE",
            ) from None
