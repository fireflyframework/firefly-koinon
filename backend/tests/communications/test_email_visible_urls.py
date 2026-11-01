# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from html.parser import HTMLParser

import pytest
from test_email_templates import preview
from test_summary_rendering import activity_summary

from koinon.communications.locales import translate
from koinon.communications.settings import InstallationLinks
from koinon.communications.templates import EmailRenderer


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = [dict(attrs)["href"], ""]

    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data

    def handle_endtag(self, tag):
        if tag == "a":
            self.links.append(tuple(self.current))
            self.current = None


@pytest.mark.parametrize("locale", ["en-US", "es-ES"])
@pytest.mark.parametrize("kind", ["invitation", "welcome", "daily", "weekly", "monthly"])
async def test_every_email_link_displays_exact_destination_with_localized_action_adjacent(locale, kind):
    base = "https://knowledge.example.test"
    preferences = base + "/auth/notifications/preferences"
    action = base + (
        "/auth/invitations/email/11111111-1111-1111-1111-111111111111" if kind == "invitation" else "/library"
    )
    key = (
        "invite_action"
        if kind == "invitation"
        else "welcome_action"
        if kind == "welcome"
        else "digest_action"
    )
    label = translate(locale, key)
    value = preview(
        action_label=label,
        effective_locale=locale,
        activity_summary=activity_summary() if kind in {"daily", "weekly", "monthly"} else None,
    )
    rendered = await EmailRenderer(InstallationLinks(public_url=base)).render(
        value, action_url=action, preferences_url=preferences, locale=locale
    )
    assert Links(rendered.html).links == [(action, action), (preferences, preferences)]
    assert rendered.html.index(label) < rendered.html.index('href="' + action + '"')
    assert translate(locale, "preferences") in rendered.html
    assert label + ": " + action in rendered.text
    assert "Powered by koinon" in rendered.html and "Firefly Software Foundation" in rendered.html


async def test_visible_url_and_adjacent_action_escape_untrusted_text_without_changing_destination():
    base = "https://knowledge.example.test"
    action = base + "/library/Research&Development"
    rendered = await EmailRenderer(InstallationLinks(public_url=base)).render(
        preview(action_label='<img src=x onerror="alert(1)">'), action_url=action
    )
    assert Links(rendered.html).links == [(action, action)]
    assert "&lt;img" in rendered.html and "<img src=x" not in rendered.html
    assert "Research&amp;Development" in rendered.html


@pytest.mark.parametrize("address", ["https://other.test/library", "//knowledge.example.test/library"])
async def test_visible_destination_keeps_canonical_same_origin_validation(address):
    with pytest.raises(ValueError, match="same-origin"):
        await EmailRenderer(InstallationLinks(public_url="https://knowledge.example.test")).render(
            preview(), action_url=address
        )
