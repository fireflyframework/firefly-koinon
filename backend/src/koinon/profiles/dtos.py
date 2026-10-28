# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, ConfigDict, Field


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    locale: str | None = Field(default=None, min_length=2, max_length=64)
    time_zone: str | None = Field(default=None, min_length=1, max_length=64)
    response_language: str | None = Field(default=None, min_length=2, max_length=64)


class ProfileOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    subject: str
    display_name: str
    locale: str
    time_zone: str
    response_language: str
    avatar_url: str | None = None
    avatar_version: str | None = None


class PersonOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    profile_id: str | None = None
    subject: str
    display_name: str
    avatar_url: str | None = None
    avatar_version: str | None = None
