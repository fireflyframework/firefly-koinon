# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from koinon.organization_branding.images import MAX_DATA_URL_LENGTH, image_data_url, sanitize_image

MAX_BRANDING_JSON_BYTES = 1572864


def contrast(first: str, second: str) -> float:
    def luminance(color):
        channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


class BrandingPalette(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    surface: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    canvas: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    text: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    muted: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    line: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    action: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    action_text: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    accent: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("*")
    @classmethod
    def canonical_color(cls, value: str) -> str:
        return value.lower()

    @model_validator(mode="after")
    def readable(self) -> Self:
        for foreground, background, minimum in (
            ("text", "surface", 4.5),
            ("muted", "surface", 4.5),
            ("action_text", "action", 4.5),
            ("accent", "surface", 4.5),
            ("text", "canvas", 4.5),
            ("muted", "canvas", 4.5),
            ("accent", "canvas", 4.5),
        ):
            if contrast(getattr(self, foreground), getattr(self, background)) < minimum:
                raise ValueError(f"{foreground}/{background} contrast must be at least {minimum}:1")
        return self


class BrandingPalettes(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
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


class BrandingInputValues(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    product_name: str = Field(default="koinon", min_length=1, max_length=64, strict=True)
    assistant_name: str = Field(default="koinon", min_length=1, max_length=64, strict=True)
    logo_light: str | None = Field(default=None, max_length=MAX_DATA_URL_LENGTH, strict=True)
    logo_dark: str | None = Field(default=None, max_length=MAX_DATA_URL_LENGTH, strict=True)
    symbol: str | None = Field(default=None, max_length=MAX_DATA_URL_LENGTH, strict=True)
    favicon: str | None = Field(default=None, max_length=MAX_DATA_URL_LENGTH, strict=True)
    palette: BrandingPalettes = Field(default_factory=BrandingPalettes)
    font_family: Literal["Manrope"] = "Manrope"

    @field_validator("product_name", "assistant_name")
    @classmethod
    def printable_name(cls, value: str) -> str:
        if not value.isprintable() or not value.strip():
            raise ValueError("Names must contain printable text")
        return value

    @field_validator("logo_light", "logo_dark", "symbol", "favicon")
    @classmethod
    def image_shape(cls, value: str | None) -> str | None:
        return image_data_url(value)

    @model_validator(mode="after")
    def bounded_json(self) -> Self:
        if len(encode_branding(self).encode("ascii")) > MAX_BRANDING_JSON_BYTES:
            raise ValueError("Branding configuration exceeds the supported size")
        return self


class BrandingValues(BrandingInputValues):
    @field_validator("logo_light", "logo_dark", "symbol", "favicon")
    @classmethod
    def raster_image(cls, value: str | None) -> str | None:
        return sanitize_image(value)


def encode_branding(value: BrandingInputValues) -> str:
    return json.dumps(value.model_dump(mode="json"), ensure_ascii=True, separators=(",", ":"))


class OrganizationBranding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str
    schema_version: Literal[1] = 1
    revision: int = Field(ge=0, le=2147483647, strict=True)
    origin: Literal["deployment", "organization"]
    branding: BrandingValues


class OrganizationBrandingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_revision: int = Field(ge=0, le=2147483646, strict=True)
    branding: BrandingInputValues


class BrandingResetInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_revision: int = Field(ge=0, le=2147483646, strict=True)
