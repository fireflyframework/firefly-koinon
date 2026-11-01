# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Purpose-separated native envelopes; recipient references never contain credentials."""

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Literal

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import BaseModel, ConfigDict, Field
from pyfly.agentic.security.encryption import AESEncryptionProvider
from pyfly.container import component
from pyfly.kernel import InvalidRequestException, ServiceUnavailableException

from koinon.corporate_identity.settings import IdentitySettings

Purpose = Literal["recipient", "delivery", "directory_cursor"]
_MAX_ENVELOPE = 2097152


@component(name="communications.cipher")
class CommunicationsCipher:
    def __init__(self, settings: IdentitySettings):
        self.settings = settings

    def _cipher(self, tenant_id: str, purpose: Purpose):
        try:
            if purpose not in {"recipient", "delivery", "directory_cursor"} or not 1 <= len(tenant_id) <= 64:
                raise ValueError()
            master = base64.b64decode(self.settings.master_key, altchars=b"-_", validate=True)
            if len(master) != 32:
                raise ValueError()
            context = json.dumps(["koinon-communications", 1, purpose, tenant_id], separators=(",", ":"))
            key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=context.encode()).derive(master)
            return AESEncryptionProvider(key)
        except Exception:
            raise self.unavailable() from None

    @staticmethod
    def unavailable():
        return ServiceUnavailableException(
            "Communications encrypted state is unavailable", code="COMMUNICATIONS_ENCRYPTION_UNAVAILABLE"
        )

    def seal(self, tenant_id: str, purpose: Purpose, value: dict) -> str:
        content = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if len(content) > _MAX_ENVELOPE // 2:
            raise self.unavailable()
        return "c1." + self._cipher(tenant_id, purpose).encrypt(content)

    def open(self, tenant_id: str, purpose: Purpose, envelope: str) -> dict:
        try:
            if (
                not isinstance(envelope, str)
                or not envelope.startswith("c1.")
                or len(envelope) > _MAX_ENVELOPE
            ):
                raise ValueError()
            content = self._cipher(tenant_id, purpose).decrypt(envelope[3:])
            if len(content) > _MAX_ENVELOPE // 2:
                raise ValueError()
            value = json.loads(content)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except Exception:
            raise self.unavailable() from None


class RecipientBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    actor: str = Field(min_length=1, max_length=512, repr=False)
    tenant_id: str = Field(min_length=1, max_length=64)
    provider_id: str = Field(min_length=1, max_length=64)
    provider_revision: int = Field(ge=1)
    external_subject: str = Field(min_length=1, max_length=512, repr=False)
    issued_at: datetime
    expires_at: datetime


@component(name="communications.recipient_references")
class RecipientReferences:
    def __init__(self, cipher: CommunicationsCipher):
        self.cipher = cipher

    def issue(
        self,
        *,
        actor: str,
        tenant_id: str,
        provider_id: str,
        provider_revision: int,
        external_subject: str,
        now: datetime | None = None,
    ) -> str:
        now = now or datetime.now(UTC)
        if now.utcoffset() is None:
            raise ValueError("Recipient references require an aware clock")
        binding = RecipientBinding(
            actor=actor,
            tenant_id=tenant_id,
            provider_id=provider_id,
            provider_revision=provider_revision,
            external_subject=external_subject,
            issued_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        return self.cipher.seal(tenant_id, "recipient", binding.model_dump(mode="json"))

    def open(
        self, value: str, *, actor: str, tenant_id: str, now: datetime | None = None
    ) -> RecipientBinding:
        try:
            if not isinstance(value, str) or len(value) > 4096:
                raise ValueError()
            binding = RecipientBinding.model_validate(self.cipher.open(tenant_id, "recipient", value))
            now = now or datetime.now(UTC)
            if (
                binding.actor != actor
                or binding.tenant_id != tenant_id
                or now.utcoffset() is None
                or binding.issued_at.utcoffset() is None
                or binding.expires_at.utcoffset() is None
                or binding.issued_at > now + timedelta(seconds=30)
                or binding.expires_at <= now
                or not timedelta(0) < binding.expires_at - binding.issued_at <= timedelta(minutes=5)
            ):
                raise ValueError()
            return binding
        except Exception:
            raise InvalidRequestException(
                "Choose a fresh recipient from this organization's directory",
                code="RECIPIENT_REFERENCE_UNAVAILABLE",
            ) from None
