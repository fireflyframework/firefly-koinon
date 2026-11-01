# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Installation authority for links, verified sender choices and finite delivery bounds."""

from dataclasses import dataclass, field
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, field_validator
from pyfly.container import component
from pyfly.core import config_properties

from koinon.communications.directory import delivery_address
from koinon.communications.dtos import Input
from koinon.communications.locales import normalize_locale
from koinon.security.settings import _endpoint


class SenderChoice(Input):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    display_name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=3, max_length=320)

    @field_validator("display_name")
    @classmethod
    def plain_name(cls, value):
        if any(ord(char) < 32 or ord(char) == 127 for char in value) or not value.strip():
            raise ValueError("Use a readable sender display name")
        return value.strip()

    @field_validator("address")
    @classmethod
    def exact_address(cls, value):
        parsed = delivery_address(value)
        if parsed is None:
            raise ValueError("Use one verified sender address without headers")
        return parsed


@component(name="communications.installation_links")
@config_properties(prefix="koinon")
@dataclass
class InstallationLinks:
    public_url: str = ""

    def __post_init__(self):
        if not isinstance(self.public_url, str):
            raise ValueError("Configure an exact public origin")
        if not self.public_url:
            return
        _endpoint(self.public_url)
        value = urlsplit(self.public_url)
        if (
            value.path not in ("", "/")
            or value.query
            or "\\" in self.public_url
            or any(ord(c) < 33 for c in self.public_url)
        ):
            raise ValueError("Configure an exact public origin without a path or query")
        self.public_url = self.public_url.rstrip("/")

    def invitation_url(self, identifier: str, *, client_path="/auth/invitations/email") -> str:
        if not self.public_url:
            raise ValueError("Email invitations require koinon.public_url")
        identifier = str(UUID(identifier))
        if (
            not isinstance(client_path, str)
            or len(client_path) > 240
            or not client_path.startswith("/")
            or client_path.startswith("//")
            or any(
                char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-/"
                for char in client_path
            )
            or ".." in client_path
        ):
            raise ValueError("Use a fixed same-origin invitation client path")
        return self.public_url + client_path.rstrip("/") + "/" + identifier


@component(name="communications.settings")
@config_properties(prefix="koinon.communications")
@dataclass
class CommunicationsSettings:
    enabled: bool = False
    verified_senders: list[dict] = field(default_factory=list)
    acceptance_client_path: str = "/auth/invitations/email"
    allow_entra_guests: bool = False
    lease_seconds: int = 120
    send_timeout_seconds: int = 30
    max_attempts: int = 3
    resend_cooldown_seconds: int = 300
    max_invitation_sends: int = 5
    default_locale: str | None = None

    def __post_init__(self):
        if self.default_locale is not None:
            self.default_locale = normalize_locale(self.default_locale)
        if type(self.enabled) is not bool or type(self.allow_entra_guests) is not bool:
            raise ValueError("Communications switches require explicit booleans")
        if not isinstance(self.verified_senders, list) or len(self.verified_senders) > 20:
            raise ValueError("Configure at most twenty verified sender choices")
        senders = self.sender_options()
        if len({sender.id for sender in senders}) != len(senders):
            raise ValueError("Verified sender identifiers must be unique")
        for value, minimum, maximum in (
            (self.lease_seconds, 30, 600),
            (self.send_timeout_seconds, 1, 60),
            (self.max_attempts, 1, 10),
            (self.resend_cooldown_seconds, 60, 3600),
            (self.max_invitation_sends, 1, 10),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError("Communications processing requires bounded integer limits")
        if self.lease_seconds < self.send_timeout_seconds + 15:
            raise ValueError("Delivery lease must exceed the bounded transport deadline")
        InstallationLinks(public_url="https://validation.invalid").invitation_url(
            "00000000-0000-0000-0000-000000000000", client_path=self.acceptance_client_path
        )

    def sender_options(self) -> list[SenderChoice]:
        return [SenderChoice.model_validate(value) for value in self.verified_senders]
