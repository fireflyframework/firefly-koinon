# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Self-contained MCP Apps review resource without per-user data or external assets."""

from base64 import b64encode
from html import escape
from pathlib import Path

from koinon.organization_branding.dtos import BrandingValues
from koinon.organization_branding.presentation import font_asset, font_license, palette_css


def render_review_resource(branding: BrandingValues | None = None) -> str:
    values = branding or BrandingValues()
    assets = Path(__file__).with_name("assets")
    css = (assets / "review.css").read_text()
    for family, token in (("Manrope", "__KOINON_FONT_BASE64__"), ("Inter", "__KOINON_INTER_FONT_BASE64__")):
        css = css.replace(token, b64encode(font_asset(family).read_bytes()).decode("ascii"))
        css = "/* " + family + " font license\n" + font_license(family).replace("*/", "* /") + "*/\n" + css
    css += palette_css(
        values,
        {
            "--canvas": "canvas",
            "--surface": "surface",
            "--text": "text",
            "--muted": "muted",
            "--line": "line",
            "--action": "action",
            "--action-text": "action_text",
            "--accent": "accent",
        },
        dark='html[data-theme="dark"]{__PALETTE__}',
    )
    html = (assets / "review.html").read_text()
    html = html.replace(
        '<span id="product-name">koinon</span>',
        '<span id="product-name">' + escape(values.product_name) + "</span>",
    )
    if values.symbol or values.product_name != "koinon":
        start = html.index('<span class="brand-mark"')
        end = html.index('<span id="product-name">', start)
        mark = (
            '<img alt="" src="' + escape(values.symbol, quote=True) + '" />'
            if values.symbol
            else escape(values.product_name[:1].upper())
        )
        html = html[:start] + '<span class="brand-mark" aria-hidden="true">' + mark + "</span>" + html[end:]
    return html.replace("/*__KOINON_REVIEW_CSS__*/", css).replace(
        "/*__KOINON_REVIEW_SCRIPT__*/",
        (assets / "review-file.js").read_text() + "\n" + (assets / "review.js").read_text(),
    )
