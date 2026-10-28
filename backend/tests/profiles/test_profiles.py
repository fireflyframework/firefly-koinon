# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image, PngImagePlugin
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.kernel import InvalidRequestException
from starlette.requests import Request

from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.profiles.images import sanitize_avatar
from koinon.profiles.security import require_personal_permission
from koinon.profiles.service import ProfileService
from koinon.security.identity import RequestIdentity


@pytest.fixture
async def profiles(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "agentic": {"enabled": True},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'profiles.db'}",
                        }
                    },
                }
            }
        )
    )
    for package in ("koinon.catalog", "koinon.profiles"):
        scan_package(package, context.container)
    await context.start()
    try:
        for tenant in ("north", "south"):
            await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant))
        for subject, tenant, role in (
            ("issuer|admin", "north", "admin"),
            ("issuer|member", "north", "viewer"),
            ("issuer|other", "south", "admin"),
        ):
            await context.get_bean(MembershipRepository).save(
                Membership(id=subject, subject=subject, tenant_id=tenant, role=role)
            )
        yield context.get_bean(ProfileService), context
    finally:
        await context.stop()


async def test_profile_is_self_owned_and_preferences_do_not_change_machine_values(profiles):
    service, _ = profiles
    initial = await service.get("issuer|member", {"name": "Verified member", "locale": "es-MX"})
    assert initial["display_name"] == "Verified member" and initial["locale"] == "es-MX"
    updated = await service.update(
        "issuer|member",
        {
            "display_name": "Researcher",
            "time_zone": "America/Mexico_City",
            "locale": "es-MX",
            "response_language": "es",
        },
    )
    assert updated["subject"] == "issuer|member" and updated["response_language"] == "es"
    assert (await service.get("issuer|other"))["display_name"] == ""
    for body in (
        {"subject": "issuer|other"},
        {"role": "admin"},
        {"time_zone": "Invented/Zone"},
        {"locale": "<script>"},
        {"response_language": "en;ignore rules"},
    ):
        with pytest.raises(InvalidRequestException):
            await service.update("issuer|member", body)
    assert (await service.get("issuer|member"))["display_name"] == "Researcher"


def image_bytes():
    image = Image.new("RGBA", (256, 256), (20, 40, 80, 128))
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Private", "private-camera-location")
    output = BytesIO()
    image.save(output, format="PNG", pnginfo=metadata)
    return output.getvalue()


def test_avatar_is_bounded_reencoded_and_metadata_free():
    output = sanitize_avatar(image_bytes())
    with Image.open(BytesIO(output)) as image:
        assert image.format == "JPEG" and max(image.size) <= 128
        assert not image.getexif() and "Private" not in image.info
    assert b"private-camera-location" not in output
    for value in (b"<svg/>", b"x" * 2_097_153, b"not an image"):
        with pytest.raises(ValueError):
            sanitize_avatar(value)
    wide = BytesIO()
    Image.new("RGB", (4097, 1)).save(wide, format="PNG")
    with pytest.raises(ValueError):
        sanitize_avatar(wide.getvalue())


async def test_avatar_and_author_summary_never_expose_private_preferences(profiles):
    service, _ = profiles
    await service.update("issuer|member", {"display_name": "Researcher", "locale": "es-MX"})
    dto = await service.set_avatar("issuer|member", image_bytes())
    assert dto["avatar_url"] and dto["avatar_version"]
    summary = await service.author_summary("issuer|member")
    assert summary["avatar_data_url"].startswith("data:image/jpeg;base64,")
    assert "locale" not in summary and "time_zone" not in summary and "email" not in summary
    assert base64.b64decode(summary["avatar_data_url"].split(",", 1)[1]) == await service.avatar(
        "issuer|member"
    )
    await service.delete_avatar("issuer|member")
    assert (await service.get("issuer|member"))["avatar_url"] is None


async def test_directory_requires_admin_and_selected_tenant_membership(profiles):
    service, _ = profiles
    await service.update("issuer|member", {"display_name": "North member"})
    await service.update("issuer|other", {"display_name": "South member"})
    with pytest.raises(AccessDenied):
        await service.people("issuer|member", "north")
    people = await service.people("issuer|admin", "north")
    assert {row["subject"] for row in people["items"]} == {"issuer|admin", "issuer|member"}
    assert all("locale" not in row and "time_zone" not in row for row in people["items"])
    with pytest.raises(AccessDenied):
        await service.people("issuer|admin", "south")


def test_personal_access_token_requires_profile_permission(monkeypatch):
    monkeypatch.setattr(
        "koinon.profiles.security.identity_from_request",
        lambda request: RequestIdentity("issuer|member", True, "bearer"),
    )
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/profile", "headers": []})
    request.state.security_context = SimpleNamespace(
        attributes={"koinon_token": {"scopes": ["knowledge:search"]}}
    )
    with pytest.raises(AccessDenied):
        require_personal_permission(request, "profile:read")
    request.state.security_context.attributes["koinon_token"]["scopes"] = ["profile:write"]
    assert require_personal_permission(request, "profile:read").subject == "issuer|member"
    assert require_personal_permission(request, "profile:write").subject == "issuer|member"


async def test_verified_defaults_persist_and_parallel_preferences_do_not_overwrite_each_other(profiles):
    import asyncio

    service, _ = profiles
    await service.get("issuer|member", {"name": "Verified member", "locale": "es-MX"})
    assert (await service.get("issuer|member"))["display_name"] == "Verified member"
    await asyncio.gather(
        service.update("issuer|member", {"display_name": "Edited member"}),
        service.update("issuer|member", {"locale": "en-GB"}),
    )
    profile = await service.get("issuer|member")
    assert profile["display_name"] == "Edited member" and profile["locale"] == "en-GB"
    assert (await service.get("other-issuer|member"))["display_name"] == ""


def test_malformed_pat_and_wrong_directory_scope_fail_closed(monkeypatch):
    from koinon.profiles.security import require_directory_identity

    monkeypatch.setattr(
        "koinon.profiles.security.identity_from_request",
        lambda request: RequestIdentity("issuer|member", True, "bearer"),
    )
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/profile", "headers": []})
    request.state.security_context = SimpleNamespace(attributes={"koinon_token": None})
    with pytest.raises(AccessDenied):
        require_personal_permission(request, "profile:read")
    token = {"scopes": ["members:write"], "tenant_id": "north", "workspace_ids": ["workspace-a"]}
    request.state.security_context.attributes["koinon_token"] = token
    assert require_directory_identity(request, "north", "workspace-a").subject == "issuer|member"
    for tenant, workspace in [("north", None), ("north", "workspace-b"), ("south", "workspace-a")]:
        with pytest.raises(AccessDenied):
            require_directory_identity(request, tenant, workspace)


def test_animated_image_is_rejected():
    output = BytesIO()
    Image.new("RGB", (8, 8), "red").save(
        output,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (8, 8), "blue")],
        duration=100,
        loop=0,
    )
    with pytest.raises(ValueError):
        sanitize_avatar(output.getvalue())
