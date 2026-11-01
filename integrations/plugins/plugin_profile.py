# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Public deployment facts only; credential and registration actions are not inputs."""

import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OAUTH_SCOPES = frozenset(
    {
        "catalog:read",
        "catalog:write",
        "knowledge:search",
        "query:execute",
        "ingest:write",
        "chat:use",
        "activity:read",
        "evidence:read",
    }
)


def secure_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
        valid = (
            value == value.strip()
            and len(value) <= 2048
            and parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and "\\" not in value
            and not any(ord(char) < 33 or ord(char) == 127 for char in value)
            and (port is None or 1 <= port <= 65535)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(
            "Provide one credential-free absolute HTTPS endpoint without query or fragment"
        )
    return value


class DeploymentProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, hide_input_in_errors=True
    )
    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=48)
    server_url: str = Field(repr=False)
    public_client_id: str = Field(min_length=1, max_length=128, repr=False)
    callback_port: int = Field(ge=1, le=65535)
    scopes: tuple[str, ...] = ("catalog:read",)
    application_id: str | None = Field(default=None, repr=False)

    @field_validator("server_url")
    @classmethod
    def endpoint(cls, value):
        return secure_url(value)

    @field_validator("public_client_id")
    @classmethod
    def client_id(cls, value):
        if re.fullmatch(r"[A-Za-z0-9._:-]+", value) is None:
            raise ValueError("Use the exact registered public OAuth client identifier")
        return value

    @field_validator("scopes", mode="before")
    @classmethod
    def json_scopes(cls, value):
        return tuple(value) if isinstance(value, list) else value

    @field_validator("application_id")
    @classmethod
    def existing_app(cls, value):
        if (
            value is not None
            and re.fullmatch(r"(?:plugin_)?asdk_app_[A-Za-z0-9_-]{1,128}", value)
            is None
        ):
            raise ValueError(
                "Use an existing registered application technical identifier"
            )
        return value

    @model_validator(mode="after")
    def explicit_scopes(self):
        if (
            not 1 <= len(self.scopes) <= len(OAUTH_SCOPES)
            or len(set(self.scopes)) != len(self.scopes)
            or not set(self.scopes) <= OAUTH_SCOPES
            or "catalog:read" not in self.scopes
        ):
            raise ValueError(
                "Select unique supported OAuth scopes including catalog:read"
            )
        return self
