# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Server-rendered consent; all identity and destination values remain inert text."""

from dataclasses import dataclass
from html import escape
from urllib.parse import quote

from koinon.organization_branding.dtos import BrandingValues


@dataclass(frozen=True, slots=True)
class ConsentViewer:
    name: str
    account: str
    avatar_version: str | None = None


PERMISSIONS = {
    "catalog:read": ("Browse your knowledge", "View files, folders and recorded source details."),
    "catalog:write": (
        "Prepare knowledge changes",
        "Propose changes within this space for your separate review.",
    ),
    "ingest:write": (
        "Maintain approved knowledge",
        "Apply only the exact content you approve in the in-chat review.",
    ),
    "knowledge:search": ("Search documents", "Find relevant passages in documents you can access."),
    "query:execute": ("Query datasets", "Run read-only queries and view their results and sources."),
    "chat:use": ("Use knowledge agents", "Ask configured agents questions and inspect your answer audits."),
    "evidence:read": ("Inspect answer sources", "Read the evidence recorded for an answer."),
}


def consent_page(
    request_id, client, scopes, choices, csrf, viewer: ConsentViewer | None = None, branding=None
):
    branding = branding or BrandingValues()
    product = escape(branding.product_name)
    logo = (
        '<picture><source media="(prefers-color-scheme: dark)" srcset="/oauth2/mcp/logo-dark">'
        f'<img src="/oauth2/mcp/logo" alt="{product}" width="248" height="48"></picture>'
        if branding.logo_light or branding.logo_dark or branding.product_name == "koinon"
        else f"<strong>{product}</strong>"
    )
    icon = '<link rel="icon" href="/oauth2/mcp/icon">' if branding.favicon or branding.symbol else ""
    permissions = "".join(
        f'<li><span class="permission-mark" aria-hidden="true">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">'
        '<path d="m5 12 4 4L19 6"/></svg></span>'
        f"<div><strong>{escape(PERMISSIONS[scope][0])}</strong>"
        f"<p>{escape(PERMISSIONS[scope][1])}</p></div></li>"
        for scope in scopes
    )
    codes = "".join(f"<li><code>{escape(scope)}</code></li>" for scope in scopes)
    options = "".join(
        f'<option value="{escape(choice["tenant_id"])}|{escape(choice["workspace_id"])}">'
        f"{escape(choice['tenant_name'])} / {escape(choice['name'])}</option>"
        for choice in choices
    )
    identity = ""
    if viewer is not None:
        initials = "".join(word[0] for word in viewer.name.split()[:2]).upper() or "?"
        image = (
            f'<img src="/oauth2/mcp/avatar?v={quote(viewer.avatar_version, safe="")}" '
            'alt="" width="40" height="40">'
            if viewer.avatar_version
            else ""
        )
        identity = (
            '<section class="identity" aria-label="Signed-in account">'
            f'<span class="avatar" aria-hidden="true"><span>{escape(initials)}</span>{image}</span>'
            '<div class="identity-copy"><span class="supporting">Signed in as</span>'
            f'<strong>{escape(viewer.name)}</strong><span class="account">{escape(viewer.account)}</span>'
            "</div></section>"
        )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark"><title>Connect to {product}</title>
<link rel="stylesheet" href="/oauth2/mcp/style">{icon}</head>
<body><main class="connection">
<header class="brand">{logo}</header>
<section class="consent" aria-labelledby="connection-title">
<div class="introduction"><h1 id="connection-title">Connect to {product}</h1>
<p><strong>{escape(client["name"])}</strong> is requesting access to your organization’s knowledge.</p></div>
{identity}
<form method="post" action="/oauth2/mcp/authorize">
<input type="hidden" name="request_id" value="{escape(request_id)}">
<input type="hidden" name="_csrf" value="{escape(csrf)}">
<div class="access-grid"><section class="destination" aria-labelledby="destination-title">
<h2 id="destination-title">Choose a space</h2>
<p class="section-description" id="context-help">
Access stays within this space and your current permissions.</p>
<label for="context">Organization and space</label>
<select required id="context" name="context" aria-describedby="context-help">{options}</select>
<p class="destination-note">
Connecting again replaces this application’s current access to the selected space.</p>
</section><section class="permissions" aria-labelledby="permissions-title">
<h2 id="permissions-title">Allow this application to</h2>
<ul class="permission-list">{permissions}</ul>
<details><summary>Technical permissions</summary><ul class="scope-list">{codes}</ul></details>
</section></div>
<div class="decision"><p>Manage or revoke access in Authorized applications.</p>
<div class="actions"><button class="secondary" name="decision" value="deny">Cancel</button>
<button class="primary" name="decision" value="allow">Connect</button></div></div>
</form></section>
<p class="trust-note">Only continue if you started this connection and trust the application.</p>
<footer>© 2026 Firefly Software Foundation<span>Apache-2.0</span></footer>
</main></body></html>'''
