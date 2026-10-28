# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import binascii
from html import escape
from pathlib import Path
from urllib.parse import unquote_plus

from pyfly.kernel import UnauthorizedException
from pyfly.security.context import SecurityContext
from pyfly.web.adapters.starlette.form_binding import parse_form
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

from koinon.catalog.errors import AccessDenied
from koinon.mcp_auth.service import McpOAuthService, OAuthError
from koinon.security.identity import identity_from_request

HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


class OAuthProtocolBoundary:
    """Keep discovery and token exchange stateless across native browser middleware."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        stateless = path in {
            "/.well-known/oauth-protected-resource/mcp",
            "/.well-known/oauth-authorization-server/oauth2/mcp",
            "/oauth2/mcp/token",
        }
        if scope.get("method") == "POST" and path in {"/oauth2/mcp/token", "/oauth2/mcp/authorize"}:
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] != "http.request":
                    return
                body.extend(message.get("body", b""))
                if len(body) > 16384:
                    return await JSONResponse({"error": "invalid_request"}, status_code=413, headers=HEADERS)(
                        scope, receive, send
                    )
                if not message.get("more_body"):
                    break
            original_receive = receive
            sent = False

            async def bounded_receive():
                nonlocal sent
                if sent:
                    return await original_receive()
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            receive = bounded_receive

        async def stateless_send(message):
            if stateless and message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [
                        (key, value)
                        for key, value in message.get("headers", [])
                        if key.lower() != b"set-cookie"
                    ],
                }
            await send(message)

        return await self.app(scope, receive, stateless_send)


def unique_values(values):
    if len(values.multi_items()) > 16:
        raise OAuthError()
    result = {}
    for key, value in values.multi_items():
        if key in result or not isinstance(value, str) or len(value) > 4096:
            raise OAuthError()
        result[key] = value
    return result


def browser_subject(request):
    if request.headers.get("authorization"):
        raise OAuthError()
    session = getattr(request.state, "session", None)
    context = session.get_attribute("SECURITY_CONTEXT") if session else None
    if not isinstance(context, SecurityContext) or not context.is_authenticated:
        raise UnauthorizedException("Sign in to authorize an MCP connection", code="AUTH_REQUIRED")
    identity = identity_from_request(request)
    if identity.subject != f"{context.attributes.get('iss')}|{context.attributes.get('sub')}":
        raise OAuthError("access_denied", 403)
    if context.attributes.get("koinon_token_id"):
        raise OAuthError("access_denied", 403)
    return identity.subject


def consent_page(request_id, client, scopes, choices, csrf):
    descriptions = {
        "catalog:read": "Browse knowledge and source details",
        "knowledge:search": "Search documents",
        "query:execute": "Run read-only dataset queries",
        "chat:use": "Ask configured agents questions",
        "evidence:read": "Inspect answer sources",
    }
    scope_list = "".join(
        f"<li>{escape(descriptions[scope])} <small><code>{escape(scope)}</code></small></li>"
        for scope in scopes
    )
    options = "".join(
        f'<option value="{escape(choice["tenant_id"])}|{escape(choice["workspace_id"])}">'
        f"{escape(choice['tenant_name'])} / {escape(choice['name'])}</option>"
        for choice in choices
    )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Connect to koinon</title>
<style>@font-face{{font-family:Manrope;src:url(/oauth2/mcp/font) format('woff2');font-display:swap}}
*{{box-sizing:border-box}}
body{{margin:0;background:#f3f1eb;color:#272820;font:16px/1.6 Manrope,Arial,sans-serif}}
main{{max-width:680px;margin:8vh auto;padding:32px}}header img{{width:min(100%,280px);height:auto}}
h1{{font-size:32px;line-height:1.2;letter-spacing:-.04em}}p{{overflow-wrap:anywhere}}
form{{background:white;border:1px solid #d8d4ca;border-radius:16px;padding:24px;margin-top:24px}}
select,button{{font:inherit;min-height:48px;border:1px solid #62645b;border-radius:8px;padding:10px 16px}}
label{{display:block;font-weight:600;margin:20px 0 8px}}select{{width:100%;background:white}}
button{{cursor:pointer;background:#ffb34a;color:#10110f;margin:24px 12px 0 0;font-weight:600}}
button.secondary{{background:white}}:focus-visible{{outline:3px solid #855414;outline-offset:4px}}
code{{overflow-wrap:anywhere}}footer{{margin-top:32px;font-size:13px;color:#62645b}}
@media(max-width:480px){{main{{margin:16px auto;padding:20px}}form{{padding:18px}}h1{{font-size:28px}}}}
</style></head><body><main><header>
<img src="/oauth2/mcp/logo" alt="firefly koinon" width="280" height="36"></header>
<h1>Connect {escape(client["name"])}</h1>
<p>This application will act with your current permissions in the space you select.</p>
<p>Only approve a connection you started. You can revoke it from your API tokens page.</p>
<form method="post" action="/oauth2/mcp/authorize">
<input type="hidden" name="request_id" value="{escape(request_id)}">
<input type="hidden" name="_csrf" value="{escape(csrf)}">
<label for="context">Organization and space</label>
<select required id="context" name="context">{options}</select>
<p>Requested permissions:</p><ul>{scope_list}</ul>
<button name="decision" value="allow">Allow connection</button>
<button class="secondary" name="decision" value="deny">Cancel</button></form>
<footer>© 2026 Firefly Software Foundation · Apache-2.0</footer></main></body></html>'''


def install_oauth(app, context):
    app.add_middleware(OAuthProtocolBoundary)

    def service():
        return context.get_bean(McpOAuthService)

    async def respond(handler):
        try:
            return await handler()
        except OAuthError as exc:
            return JSONResponse({"error": exc.error}, status_code=exc.status, headers=HEADERS)
        except AccessDenied:
            return JSONResponse({"error": "access_denied"}, status_code=403, headers=HEADERS)

    async def protected_resource(request):
        async def handle():
            return JSONResponse(service().resource_metadata(), headers=HEADERS)

        return await respond(handle)

    async def metadata(request):
        async def handle():
            return JSONResponse(service().metadata(), headers=HEADERS)

        return await respond(handle)

    async def authorize(request):
        async def handle():
            oauth = service()
            oauth.require_enabled()
            if len(request.scope.get("query_string", b"")) > 8192:
                raise OAuthError()
            try:
                subject = browser_subject(request)
            except UnauthorizedException:
                if request.method != "GET":
                    raise OAuthError("access_denied", 403) from None
                params = unique_values(request.query_params)
                oauth.validate_request(params)
                # Native login consumes this saved local return URI after session rotation.
                request.state.session.set_attribute(
                    "oauth2_redirect_uri", request.url.path + "?" + str(request.url.query)
                )
                return RedirectResponse("/oauth2/authorization/koinon", status_code=302, headers=HEADERS)
            if request.method == "GET":
                params = unique_values(request.query_params)
                request_id, client, scopes, choices = await oauth.begin(subject, params)
                html = consent_page(
                    request_id, client, scopes, choices, getattr(request.state, "csrf_token", "")
                )
                headers = {
                    **HEADERS,
                    "Content-Security-Policy": (
                        "default-src 'none'; style-src 'unsafe-inline'; font-src 'self'; img-src 'self'; "
                        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
                    ),
                }
                return HTMLResponse(html, headers=headers)
            form = unique_values(await parse_form(request))
            if set(form) - {"request_id", "decision", "context", "tenant_id", "workspace_id", "_csrf"}:
                raise OAuthError()
            tenant, workspace = form.get("tenant_id", ""), form.get("workspace_id", "")
            if form.get("context"):
                if tenant or workspace or form["context"].count("|") != 1:
                    raise OAuthError()
                tenant, workspace = form["context"].split("|")
            target = await oauth.consent(
                subject, form.get("request_id", ""), form.get("decision", ""), tenant, workspace
            )
            return RedirectResponse(target, status_code=302, headers=HEADERS)

        return await respond(handle)

    async def token(request):
        async def handle():
            service().require_enabled()
            if request.cookies or request.query_params:
                raise OAuthError()
            form = unique_values(await parse_form(request))
            secret = form.pop("client_secret", "")
            authorization = request.headers.get("authorization")
            if authorization:
                if not authorization.startswith("Basic ") or secret:
                    raise OAuthError("invalid_client", 401)
                try:
                    decoded = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
                    identifier, separator, basic_secret = decoded.partition(":")
                    if not separator or (
                        form.get("client_id") and form["client_id"] != unquote_plus(identifier)
                    ):
                        raise ValueError()
                    form["client_id"], secret = unquote_plus(identifier), unquote_plus(basic_secret)
                except (ValueError, UnicodeError, binascii.Error):
                    raise OAuthError("invalid_client", 401) from None
            return JSONResponse(await service().exchange(form, client_secret=secret), headers=HEADERS)

        return await respond(handle)

    async def font(request):
        service().require_enabled()
        return FileResponse(Path(__file__).parent / "assets" / "manrope.woff2", media_type="font/woff2")

    async def logo(request):
        service().require_enabled()
        return FileResponse(Path(__file__).parent / "assets" / "logo.svg", media_type="image/svg+xml")

    for path, endpoint, methods in (
        ("/.well-known/oauth-protected-resource/mcp", protected_resource, ["GET"]),
        ("/.well-known/oauth-authorization-server/oauth2/mcp", metadata, ["GET"]),
        ("/oauth2/mcp/authorize", authorize, ["GET", "POST"]),
        ("/oauth2/mcp/token", token, ["POST"]),
        ("/oauth2/mcp/font", font, ["GET"]),
        ("/oauth2/mcp/logo", logo, ["GET"]),
    ):
        app.router.routes.append(Route(path, endpoint, methods=methods))
