# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/organization_branding/dtos.py
SHA256: 54ffd3be27cf18ba7ae452572d63242e72711ffc088e7d3cebbf0f2aae108c79

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import Field

from koinon_sdk._base import InputModel, ResponseModel

MAX_DATA_URL_LENGTH = 349550
MAX_BRANDING_JSON_BYTES = 1572864


class BrandingPalette(ResponseModel):
    surface: str = Field(pattern="^#[0-9A-Fa-f]{6}$")
    canvas: str = Field(pattern="^#[0-9A-Fa-f]{6}$")
    text: str = Field(pattern="^#[0-9A-Fa-f]{6}$")
    muted: str = Field(pattern="^#[0-9A-Fa-f]{6}$")
    line: str = Field(pattern="^#[0-9A-Fa-f]{6}$")
    action: str = Field(pattern="^#[0-9A-Fa-f]{6}$")
    action_text: str = Field(pattern="^#[0-9A-Fa-f]{6}$")
    accent: str = Field(pattern="^#[0-9A-Fa-f]{6}$")


class BrandingPalettes(ResponseModel):
    light: BrandingPalette = Field(
        default_factory=lambda: BrandingPalette(
            surface="#ffffff",
            canvas="#f3f1eb",
            text="#272820",
            muted="#62645b",
            line="#d8d4ca",
            action="#ffb34a",
            action_text="#10110f",
            accent="#855414",
        )
    )
    dark: BrandingPalette = Field(
        default_factory=lambda: BrandingPalette(
            surface="#1d1f1a",
            canvas="#10110f",
            text="#f3f1eb",
            muted="#bfb8ab",
            line="#474a42",
            action="#ffb34a",
            action_text="#10110f",
            accent="#ffb34a",
        )
    )


class BrandingInputValues(ResponseModel):
    product_name: str = Field(default="koinon", min_length=1, max_length=64, strict=True)
    assistant_name: str = Field(default="koinon", min_length=1, max_length=64, strict=True)
    logo_light: str | None = Field(default=None, max_length=MAX_DATA_URL_LENGTH, strict=True)
    logo_dark: str | None = Field(default=None, max_length=MAX_DATA_URL_LENGTH, strict=True)
    symbol: str | None = Field(default=None, max_length=MAX_DATA_URL_LENGTH, strict=True)
    favicon: str | None = Field(default=None, max_length=MAX_DATA_URL_LENGTH, strict=True)
    palette: BrandingPalettes = Field(default_factory=BrandingPalettes)
    font_family: Literal["Manrope"] = "Manrope"


class BrandingValues(BrandingInputValues):
    pass


class OrganizationBranding(ResponseModel):
    tenant_id: str
    schema_version: Literal[1] = 1
    revision: int = Field(ge=0, le=2147483647, strict=True)
    origin: Literal["deployment", "organization"]
    branding: BrandingValues


class OrganizationBrandingInput(InputModel):
    expected_revision: int = Field(ge=0, le=2147483646, strict=True)
    branding: BrandingInputValues


class BrandingResetInput(InputModel):
    expected_revision: int = Field(ge=0, le=2147483646, strict=True)
