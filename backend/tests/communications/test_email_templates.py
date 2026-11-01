# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
from datetime import datetime
from io import BytesIO

import pytest
from PIL import Image

from koinon.communications.dtos import CommunicationUsageSummary, EmailPreview
from koinon.communications.settings import InstallationLinks
from koinon.communications.templates import EmailRenderer
from koinon.organization_branding.dtos import BrandingValues


def preview(**changes):
    values = dict(
        subject="Your invitation",
        sender_name="Knowledge team",
        recipient_display_name="Person",
        recipient_email="person@example.test",
        heading="Join the team",
        paragraphs=[
            "An administrator invited you to a viewer role assignment.",
            "<script>alert('private')</script> & readable text",
        ],
        action_label="Review invitation",
        footer="Review the intended access before accepting.",
        product_name="Example",
        accent_color="#855414",
        branding=BrandingValues(product_name="Example", font_family="Inter"),
    )
    values.update(changes)
    return EmailPreview(**values)


async def test_actual_html_and_text_share_content_and_escape_data_without_tracking():
    renderer = EmailRenderer(InstallationLinks(public_url="https://brain.test"))
    result = await renderer.render(
        preview(), action_url="https://brain.test/auth/invitations/email/11111111-1111-1111-1111-111111111111"
    )
    assert "&lt;script&gt;" in result.html and "<script>" not in result.html
    assert "<script>alert('private')</script> & readable text" in result.text
    assert "Join the team" in result.html and "Join the team" in result.text
    assert "Inter,Arial,sans-serif" in result.html
    assert "max-width:600px" in result.html and "padding:24px" in result.html
    assert "https://brain.test/auth/invitations/email/" in result.html
    assert "<script" not in result.html and "@font-face" not in result.html
    assert not result.images
    assert "Powered by koinon" in result.html and "Powered by koinon" in result.text
    assert "Firefly Software Foundation" in result.html and "Firefly Software Foundation" in result.text


async def test_trusted_logo_is_inline_cid_and_unsafe_links_headers_or_palette_fail_closed():
    data = BytesIO()
    Image.new("RGB", (240, 80), (10, 30, 50)).save(data, format="PNG")
    logo = "data:image/png;base64," + base64.b64encode(data.getvalue()).decode()
    brand = BrandingValues(product_name="Example", logo_light=logo)
    renderer = EmailRenderer(InstallationLinks(public_url="https://brain.test"))
    result = await renderer.render(
        preview(branding=brand), action_url="https://brain.test/auth/notifications/preferences"
    )
    assert 'src="cid:brand-logo"' in result.html and len(result.images) == 1
    assert result.images[0].content_id == "brand-logo" and result.images[0].data
    assert "data:image" not in result.html and "http://" not in result.html
    with pytest.raises(ValueError):
        await renderer.render(
            preview(subject="Invite\r\nBcc:other@example.test"),
            action_url="https://brain.test/auth/notifications/preferences",
        )
    for address in (
        "https://other.test/accept",
        "javascript:alert(1)",
        "https://user:password@brain.test/accept",
    ):
        with pytest.raises(ValueError):
            await renderer.render(preview(), action_url=address)
    unsafe = brand.model_dump()
    unsafe["palette"]["light"]["action"] = "red; background:url(https://tracker.test)"
    with pytest.warns(UserWarning, match="Pydantic serializer warnings"), pytest.raises(ValueError):
        await renderer.render(
            preview(branding=BrandingValues.model_construct(**unsafe)),
            action_url="https://brain.test/auth/notifications/preferences",
        )


async def test_usage_uses_selected_assistant_name_and_human_calendar_without_claiming_mcp_broken():
    usage = CommunicationUsageSummary(
        window_start=datetime.fromisoformat("2026-10-24T07:00:00Z"),
        window_end=datetime.fromisoformat("2026-10-31T08:00:00Z"),
        time_zone="Europe/Madrid",
        assistant_runs=28,
        completed_runs=26,
        failed_runs=2,
    )
    brand = BrandingValues(product_name="Example", assistant_name="Research assistant")
    result = await EmailRenderer(InstallationLinks(public_url="https://brain.test")).render(
        preview(branding=brand),
        action_url="https://brain.test/auth/notifications/preferences",
        usage=usage,
        locale="es-ES",
    )
    assert "Solicitudes a Research assistant" in result.html
    assert "Del 24 al 31 de octubre de 2026" in result.html and "Europe/Madrid" in result.html
    assert "MCP todavía no se incluye" in result.html and "no está disponible" not in result.html
