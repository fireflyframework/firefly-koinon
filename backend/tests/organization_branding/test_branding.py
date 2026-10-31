# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import base64
import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from pydantic import ValidationError
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.kernel import ConflictException

from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import AuditRepository, MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService
from koinon.organization_branding.dtos import BrandingValues, OrganizationBrandingInput
from koinon.organization_branding.service import OrganizationBrandingService


def raster(format="PNG", size=(12, 8)):
    output = BytesIO()
    Image.new("RGB", size, "white").save(output, format=format)
    return f"data:image/{format.lower()};base64," + base64.b64encode(output.getvalue()).decode()


def test_defaults_and_safe_assets():
    value = BrandingValues()
    assert value.product_name == "koinon" and value.font_family == "Manrope"
    assert value.palette.light.action == "#ffb34a"
    assert value.palette.light.accent == "#855414"
    assert value.palette.dark.canvas == "#10110f"
    normalized = BrandingValues(logo_light=raster("JPEG"))
    assert normalized.logo_light.startswith("data:image/png;base64,")
    with pytest.raises(ValidationError):
        value.product_name = "changed"


def test_inter_is_a_supported_bounded_installation_font():
    value = BrandingValues(font_family="Inter")
    assert value.font_family == "Inter"
    assert (
        OrganizationBrandingService(
            None,
            None,
            Config(
                {
                    "koinon": {"branding": {"font_family": "Inter"}},
                }
            ),
        ).defaults.font_family
        == "Inter"
    )
    for name in ("Inter, serif", "Inter; background: red", "https://example.test/font.woff2"):
        with pytest.raises(ValidationError):
            BrandingValues(font_family=name)


def test_accent_used_for_normal_text_links_requires_four_point_five_on_both_backgrounds():
    values = BrandingValues().model_dump(mode="json")
    values["palette"]["light"]["accent"] = "#777777"
    with pytest.raises(ValidationError, match="accent/.*4.5"):
        BrandingValues.model_validate(values)


def test_default_palette_matches_canonical_tokens_and_deployment_configuration_is_validated():
    tokens = json.loads((Path(__file__).resolve().parents[3] / "brand/tokens.json").read_text())
    value = BrandingValues()
    assert value.font_family == tokens["typography"]["family"]
    for theme in ("light", "dark"):
        colors = getattr(value.palette, theme).model_dump()
        accent = colors.pop("accent")
        colors["actionText"] = colors.pop("action_text")
        assert colors == tokens["themes"][theme]
        assert accent == tokens["palette"]["gold" if theme == "light" else "amber"]
    with pytest.raises(ValidationError):
        OrganizationBrandingService(None, None, Config({"koinon": {"branding": {"font_family": "Arial"}}}))


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
def test_assets_are_decoded_into_metadata_free_png(format):
    source = raster(format)
    value = BrandingValues(logo_dark=source, symbol=source, favicon=source)
    for encoded in (value.logo_dark, value.symbol, value.favicon):
        with Image.open(BytesIO(base64.b64decode(encoded.split(",", 1)[1]))) as image:
            assert image.format == "PNG" and image.size == (12, 8)
            assert image.info == {}
    output = BytesIO()
    metadata = PngInfo()
    metadata.add_text("Comment", "Do not retain this metadata")
    Image.new("RGB", (10, 10)).save(output, "PNG", pnginfo=metadata)
    result = BrandingValues(
        logo_light="data:image/png;base64," + base64.b64encode(output.getvalue()).decode()
    )
    with Image.open(BytesIO(base64.b64decode(result.logo_light.split(",", 1)[1]))) as image:
        assert "Comment" not in image.info


def test_mismatched_animated_and_oversized_assets_are_rejected():
    with pytest.raises(ValidationError):
        BrandingValues(logo_light=raster("PNG").replace("image/png", "image/jpeg"))
    with pytest.raises(ValidationError):
        BrandingValues(logo_light="data:image/png;base64," + "A" * 349532)
    output = BytesIO()
    first, second = (Image.new("RGB", (12, 8), color) for color in ("white", "black"))
    first.save(output, "PNG", save_all=True, append_images=[second], duration=100)
    with pytest.raises(ValidationError):
        BrandingValues(logo_light="data:image/png;base64," + base64.b64encode(output.getvalue()).decode())


@pytest.mark.parametrize(
    "change",
    [
        {"product_name": ""},
        {"product_name": "a\nname"},
        {"assistant_name": "x" * 65},
        {"font_family": "Arial"},
        {"logo_light": "https://example.com/logo.png"},
        {"symbol": "data:image/svg+xml;base64,PHN2Zy8+"},
        {"favicon": "data:image/png;base64,broken"},
    ],
)
def test_unsafe_brand_values_are_rejected(change):
    with pytest.raises(ValidationError):
        BrandingValues.model_validate(change)


def test_contrast_and_asset_dimensions():
    value = BrandingValues().model_dump()
    for field in ("text", "muted", "accent"):
        bad = BrandingValues().model_dump()
        bad["palette"]["light"][field] = "#ffffff"
        with pytest.raises(ValidationError):
            BrandingValues.model_validate(bad)
    value["palette"]["dark"]["action_text"] = "#ffb34a"
    with pytest.raises(ValidationError):
        BrandingValues.model_validate(value)
    with pytest.raises(ValidationError):
        BrandingValues(symbol=raster(size=(2049, 1)))


@pytest.mark.parametrize("foreground", ["text", "muted", "accent"])
def test_canvas_contrast_is_required_for_each_label_color(foreground):
    values = BrandingValues().model_dump()
    values["palette"]["light"]["canvas"] = values["palette"]["light"][foreground]
    with pytest.raises(ValidationError):
        BrandingValues.model_validate(values)


@pytest.fixture
async def branding(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'branding.db'}",
                        }
                    },
                },
                "koinon": {"branding": {"product_name": "Deployment Koinon"}},
            }
        )
    )
    for package in ("koinon.catalog", "koinon.organization_branding"):
        scan_package(package, context.container)
    await context.start()
    try:
        for tenant in ("north", "south"):
            await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant))
        for subject, tenant, role, workspace in (
            ("admin", "north", "admin", None),
            ("viewer", "north", "viewer", None),
            ("operator", "north", "operator", None),
            ("outside", "south", "admin", None),
        ):
            await context.get_bean(MembershipRepository).save(
                Membership(
                    id=subject,
                    subject=subject,
                    tenant_id=tenant,
                    role=role,
                    workspace_id=workspace,
                )
            )
        workspace = await context.get_bean(CatalogService).create(
            "admin", "north", kind="workspace", name="Scoped"
        )
        await context.get_bean(MembershipRepository).save(
            Membership(
                id="scoped",
                subject="scoped",
                tenant_id="north",
                role="admin",
                workspace_id=workspace.id,
            )
        )
        yield context.get_bean(OrganizationBrandingService), context
    finally:
        await context.stop()


def update(revision=0, name="Organization Koinon"):
    return OrganizationBrandingInput(expected_revision=revision, branding=BrandingValues(product_name=name))


async def test_permissions_isolation_and_monotonic_reset(branding):
    service, context = branding
    initial = await service.get("viewer", "north")
    assert (initial.revision, initial.origin, initial.branding.product_name) == (
        0,
        "deployment",
        "Deployment Koinon",
    )
    for subject in ("viewer", "operator", "scoped", "outside"):
        with pytest.raises(AccessDenied):
            await service.update(subject, "north", update())
    with pytest.raises(AccessDenied):
        await service.get("outside", "north")
    assert (await service.get("scoped", "north")).revision == 0
    saved = await service.update("admin", "north", update())
    assert (saved.revision, saved.origin) == (1, "organization")
    assert (await service.get("outside", "south")).revision == 0
    reset = await service.reset("admin", "north", 1)
    assert (reset.revision, reset.origin, reset.branding.product_name) == (
        2,
        "deployment",
        "Deployment Koinon",
    )
    with pytest.raises(ConflictException):
        await service.update("admin", "north", update(1))
    assert (await service.update("admin", "north", update(2))).revision == 3
    audits = await context.get_bean(AuditRepository).find_all(tenant_id="north")
    assert [row.action for row in audits if row.action.startswith("organization_branding.")] == [
        "organization_branding.updated",
        "organization_branding.reset",
        "organization_branding.updated",
    ]
    assert all("data:image" not in str(row.details) for row in audits)


async def test_atomic_cas_and_audit_rollback(branding, monkeypatch):
    service, _ = branding
    results = await asyncio.gather(
        service.update("admin", "north", update(name="One")),
        service.update("admin", "north", update(name="Two")),
        return_exceptions=True,
    )
    assert sum(isinstance(value, ConflictException) for value in results) == 1
    saved = await service.get("viewer", "north")

    async def fail(*args, **kwargs):
        raise RuntimeError("Controlled audit failure")

    monkeypatch.setattr(service.catalog, "_audit", fail)
    with pytest.raises(RuntimeError, match="Controlled audit failure"):
        await service.reset("admin", "north", 1)
    assert await service.get("viewer", "north") == saved


async def test_reset_before_override_and_later_updates_never_restore_revision_zero(branding):
    service, _ = branding
    assert (await service.reset("admin", "north", 0)).revision == 1
    assert (await service.reset("admin", "north", 1)).revision == 2
    with pytest.raises(ConflictException):
        await service.update("admin", "north", update())
    saved = await service.update("admin", "north", update(2))
    assert saved.revision == 3
    assert saved.branding.product_name == "Organization Koinon"
