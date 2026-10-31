# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import re
from importlib.resources import files

from koinon.mcp.review_resource import render_review_resource


def test_review_resource_preserves_the_local_font_and_its_license():
    html = render_review_resource()
    assets = files("koinon.mcp_auth").joinpath("assets")
    encoded = re.search(r"data:font/woff2;base64,([A-Za-z0-9+/=]+)", html)
    assert encoded is not None
    assert base64.b64decode(encoded.group(1), validate=True) == assets.joinpath("manrope.woff2").read_bytes()
    assert assets.joinpath("OFL.txt").read_text() in html
    assert "/*__KOINON_REVIEW_" not in html
    assert "__KOINON_FONT_BASE64__" not in html
