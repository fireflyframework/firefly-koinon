# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Packaged headless presentation assets and validated palette declarations."""

from pathlib import Path

from koinon.organization_branding.dtos import BrandingValues


def font_asset(family: str) -> Path:
    if family == "Inter":
        return Path(__file__).parent / "assets/inter.woff2"
    if family == "Manrope":
        return Path(__file__).parent.parent / "mcp_auth/assets/manrope.woff2"
    raise ValueError("Choose a bundled interface font")


def font_license(family: str) -> str:
    return font_asset(family).with_name("Inter-OFL.txt" if family == "Inter" else "OFL.txt").read_text()


def palette_css(branding: BrandingValues, mapping: dict[str, str], *, dark: str) -> str:
    values = BrandingValues.model_validate(branding.model_dump(mode="json"))

    def declarations(theme):
        palette = getattr(values.palette, theme)
        return ";".join(f"{variable}:{getattr(palette, field)}" for variable, field in mapping.items())

    light = ":root{" + declarations("light") + ";--interface-font:" + values.font_family + "}"
    return light + dark.replace("__PALETTE__", declarations("dark"))
