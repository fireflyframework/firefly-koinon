# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from pyfly.kernel import UnauthorizedException
from pyfly.security.context import SecurityContext
from starlette.requests import Request

from koinon.catalog.errors import AccessDenied
from koinon.communications.http import browser_owner, page_html
from koinon.organization_branding.dtos import BrandingValues


def request(attributes, *, authorization=False, session=True):
    context = SecurityContext(user_id="person", attributes=attributes)
    value = Request(
        {
            "type": "http",
            "path": "/auth/notifications",
            "headers": [(b"authorization", b"Bearer credential")] if authorization else [],
        }
    )
    value.state.security_context = context
    value.state.session = SimpleNamespace(get_attribute=lambda name: context) if session else None
    return value


def test_headless_pages_require_matching_native_browser_session_and_reject_bearer_tokens():
    attributes = {"iss": "https://issuer.test", "sub": "person"}
    assert browser_owner(request(attributes)) == "https://issuer.test|person"
    with pytest.raises(AccessDenied):
        browser_owner(request(attributes, authorization=True))
    with pytest.raises(UnauthorizedException):
        browser_owner(request(attributes, session=False))
    with pytest.raises(AccessDenied):
        browser_owner(request({**attributes, "koinon_token": {"scopes": ["notifications:write"]}}))


def test_actual_native_page_is_escaped_branded_and_uses_packaged_font_without_frontend():
    html, headers = page_html(
        BrandingValues(product_name="Research <Brain>", font_family="Inter"),
        "en-US",
        "Invitation",
        "<p>Trusted markup</p>",
    )
    assert "Research &lt;Brain&gt;" in html and "Research <Brain>" not in html
    assert "/auth/communications/fonts/Inter.woff2" in html
    assert "Powered by koinon" in html and "Firefly Software Foundation" in html
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert "form-action 'self'" in headers["Content-Security-Policy"]
