# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import re
from importlib.resources import files

from koinon.mcp.review_resource import render_review_resource
from koinon.organization_branding.dtos import BrandingValues


def test_headless_review_uses_bounded_installation_identity_and_packaged_fonts():
    branding = BrandingValues(product_name='North "Knowledge" <script>', font_family="Inter")
    html = render_review_resource(branding)
    assert "North &quot;Knowledge&quot; &lt;script&gt;" in html
    assert '<span id="product-name">koinon</span>' not in html
    assert "--interface-font:Inter" in html
    inter = files("koinon.organization_branding").joinpath("assets/inter.woff2").read_bytes()
    assert base64.b64encode(inter).decode("ascii") in html
    assert files("koinon.organization_branding").joinpath("assets/Inter-OFL.txt").read_text() in html
    assert "__KOINON_INTER_FONT_BASE64__" not in html


def test_review_resource_preserves_the_local_font_and_its_license():
    html = render_review_resource()
    assets = files("koinon.mcp_auth").joinpath("assets")
    encoded = re.search(r"data:font/woff2;base64,([A-Za-z0-9+/=]+)", html)
    assert encoded is not None
    assert base64.b64decode(encoded.group(1), validate=True) == assets.joinpath("manrope.woff2").read_bytes()
    assert assets.joinpath("OFL.txt").read_text() in html
    assert "/*__KOINON_REVIEW_" not in html
    assert "__KOINON_FONT_BASE64__" not in html
