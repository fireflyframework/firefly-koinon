# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Self-contained MCP Apps review resource without per-user data or external assets."""

from base64 import b64encode
from pathlib import Path


def render_review_resource() -> str:
    assets = Path(__file__).with_name("assets")
    font = Path(__file__).parent.parent / "mcp_auth/assets/manrope.woff2"
    css = (
        (assets / "review.css")
        .read_text()
        .replace("__KOINON_FONT_BASE64__", b64encode(font.read_bytes()).decode("ascii"))
    )
    font_license = font.with_name("OFL.txt").read_text()
    css = "/* Manrope font license\n" + font_license.replace("*/", "* /") + "*/\n" + css
    return (
        (assets / "review.html")
        .read_text()
        .replace("/*__KOINON_REVIEW_CSS__*/", css)
        .replace(
            "/*__KOINON_REVIEW_SCRIPT__*/",
            (assets / "review-file.js").read_text() + "\n" + (assets / "review.js").read_text(),
        )
    )
