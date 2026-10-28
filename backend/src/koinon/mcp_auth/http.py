# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import binascii
from pathlib import Path
from urllib.parse import unquote_plus

from pyfly.kernel import UnauthorizedException
from pyfly.security.context import SecurityContext
from pyfly.web.adapters.starlette.form_binding import parse_form
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from koinon.catalog.errors import AccessDenied
from koinon.mcp_auth.presentation import ConsentViewer, consent_page
from koinon.mcp_auth.service import McpOAuthService, OAuthError
from koinon.profiles.service import ProfileService
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
                profile = await context.get_bean(ProfileService).get(subject)
                claims = request.state.session.get_attribute("SECURITY_CONTEXT").attributes
                account = claims.get("email") if claims.get("email_verified") is True else None
                account = account or claims.get("preferred_username") or claims.get("sub")
                account = account if isinstance(account, str) and account.strip() else "Signed-in account"
                name = profile["display_name"] or claims.get("name") or account
                name = name if isinstance(name, str) and name.strip() else account
                viewer = ConsentViewer(name, account, profile.get("avatar_version"))
                html = consent_page(
                    request_id, client, scopes, choices, getattr(request.state, "csrf_token", ""), viewer
                )
                headers = {
                    **HEADERS,
                    "Content-Security-Policy": (
                        "default-src 'none'; style-src 'self'; font-src 'self'; img-src 'self'; "
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

    async def logo_dark(request):
        service().require_enabled()
        return FileResponse(Path(__file__).parent / "assets" / "logo-dark.svg", media_type="image/svg+xml")

    async def style(request):
        service().require_enabled()
        return FileResponse(Path(__file__).parent / "assets" / "consent.css", media_type="text/css")

    async def avatar(request):
        async def handle():
            service().require_enabled()
            try:
                subject = browser_subject(request)
            except UnauthorizedException:
                return JSONResponse({"error": "access_denied"}, status_code=401, headers=HEADERS)
            from pyfly.kernel import ResourceNotFoundException

            try:
                image = await context.get_bean(ProfileService).avatar(subject)
            except ResourceNotFoundException:
                return Response(status_code=404, headers=HEADERS)
            return Response(image, media_type="image/jpeg", headers=HEADERS)

        return await respond(handle)

    for path, endpoint, methods in (
        ("/.well-known/oauth-protected-resource/mcp", protected_resource, ["GET"]),
        ("/.well-known/oauth-authorization-server/oauth2/mcp", metadata, ["GET"]),
        ("/oauth2/mcp/authorize", authorize, ["GET", "POST"]),
        ("/oauth2/mcp/token", token, ["POST"]),
        ("/oauth2/mcp/font", font, ["GET"]),
        ("/oauth2/mcp/logo", logo, ["GET"]),
        ("/oauth2/mcp/logo-dark", logo_dark, ["GET"]),
        ("/oauth2/mcp/style", style, ["GET"]),
        ("/oauth2/mcp/avatar", avatar, ["GET"]),
    ):
        app.router.routes.append(Route(path, endpoint, methods=methods))
