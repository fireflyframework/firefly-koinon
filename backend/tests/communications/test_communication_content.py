# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from test_email_invitations import ACTOR, draft
from test_email_invitations import email_context as email_context

from koinon.communications.content import CommunicationContent
from koinon.communications.settings import CommunicationsSettings
from koinon.profiles.entities import Profile
from koinon.profiles.repositories import ProfileRepository
from koinon.profiles.service import profile_id


@pytest.mark.parametrize(
    "locale,action,role",
    [("es-ES", "Revisar invitación", "lector"), ("en-US", "Review invitation", "viewer")],
)
async def test_actual_invitation_preview_subject_body_roles_actions_and_text_share_effective_locale(
    email_context, locale, action, role
):
    context, _ = email_context
    context.get_bean(CommunicationsSettings).default_locale = locale
    await context.get_bean(ProfileRepository).save(
        Profile(id=profile_id(ACTOR), subject=ACTOR, display_name="Andrés", locale="en-US")
    )
    value = await context.get_bean(CommunicationContent).preview_invitation(
        ACTOR, "north", await draft(context)
    )
    assert value.action_label == action and role in " ".join(value.paragraphs)
    assert "Andrés" in " ".join(value.paragraphs)
    assert value.effective_locale == locale and value.locale_origin == "installation"
    assert "north" in value.subject and value.organization_name == "north"
    assert value.rendered_html and value.rendered_text
    assert action in value.rendered_html and action in value.rendered_text
    assert "Powered by koinon" in value.rendered_html and "Firefly Software Foundation" in value.rendered_text


@pytest.mark.parametrize("locale", ["en-US", "es-ES"])
@pytest.mark.parametrize(
    "kind,subtype",
    [
        ("welcome", None),
        ("access_granted", None),
        ("role_changed", None),
        ("access_removed", None),
        ("security", "token_created"),
        ("security", "token_revoked"),
        ("security", "application_granted"),
        ("security", "application_revoked"),
        ("security", "client_registered"),
        ("security", "client_revoked"),
        ("security", "client_secret_rotated"),
    ],
)
async def test_all_notice_content_uses_same_localized_subject_html_and_plain_values(
    email_context, locale, kind, subtype
):
    from types import SimpleNamespace

    from koinon.communications.directory import DirectoryPerson
    from koinon.communications.templates import EmailRenderer

    context, _ = email_context
    context.get_bean(CommunicationsSettings).default_locale = locale
    person = DirectoryPerson("person", "Person", "person@example.test", "verified_directory")
    event = SimpleNamespace(
        tenant_id="north",
        owner_subject="https://issuer.test|person",
        kind=kind,
        event_json=dict(
            organization_name="North",
            workspace_name="Research",
            actor_name="Trusted administrator",
            label="Automation <label>",
            subtype=subtype,
            scopes=["catalog:read"],
        ),
    )
    preview = await context.get_bean(CommunicationContent).notice(event, person)
    rendered = await context.get_bean(EmailRenderer).render(
        preview, action_url="https://brain.test/auth/notifications", locale=preview.effective_locale
    )
    assert "North" in preview.subject and "Research" in preview.subject
    assert preview.heading in rendered.html and preview.heading in rendered.text
    assert "Automation &lt;label&gt;" in rendered.html and "Automation <label>" in rendered.text
    assert "Powered by koinon" in rendered.html and "Firefly Software Foundation" in rendered.text


@pytest.mark.parametrize(
    "locale,heading,subject_fragment",
    [
        ("en-US", "Organization activity summary", "organization"),
        ("es-ES", "Resumen de actividad de la organización", "de la organización"),
    ],
)
async def test_administrative_digest_identifies_organization_audience_and_keeps_personal_copy_separate(
    email_context, locale, heading, subject_fragment
):
    from types import SimpleNamespace

    from test_summary_rendering import activity_summary

    from koinon.communications.directory import DirectoryPerson

    context, _ = email_context
    context.get_bean(CommunicationsSettings).default_locale = locale
    person = DirectoryPerson("person", "Person", "person@example.test", "verified_directory")
    event = SimpleNamespace(
        tenant_id="north",
        owner_subject="https://issuer.test|person",
        event_json=dict(organization_name="North", cadence="monthly"),
    )
    content = context.get_bean(CommunicationContent)
    admin = await content.digest(event, person, activity_summary(audience="organization_administrators"))
    personal = await content.digest(event, person, activity_summary())
    assert admin.heading == heading and subject_fragment in admin.subject and "North" in admin.subject
    assert admin.subject != personal.subject and admin.heading != personal.heading
    assert admin.activity_summary.audience == "organization_administrators"
