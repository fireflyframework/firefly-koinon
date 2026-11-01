# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bundled, session-only acceptance and preference pages work without Angular or MCP."""

from datetime import UTC, datetime
from html import escape
from secrets import compare_digest, token_urlsafe
from uuid import UUID

from pyfly.kernel import InvalidRequestException, UnauthorizedException
from pyfly.security.context import SecurityContext
from pyfly.web.adapters.starlette.form_binding import parse_form
from starlette.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

from koinon.catalog.errors import AccessDenied
from koinon.communications.content import CommunicationContent, _expiry
from koinon.communications.dtos import NotificationPreferencesInput
from koinon.communications.inbox import NotificationService
from koinon.communications.invitations import EmailInvitationService
from koinon.communications.locale_service import CommunicationLocales
from koinon.communications.locales import translate
from koinon.organization_branding.dtos import BrandingValues
from koinon.organization_branding.presentation import font_asset
from koinon.organization_branding.service import OrganizationBrandingService
from koinon.security.identity import identity_from_request

HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def browser_owner(request):
    if request.headers.get("authorization"):
        raise AccessDenied("Use the native browser session", code="INTERACTIVE_IDENTITY_REQUIRED")
    session = getattr(request.state, "session", None)
    context = session.get_attribute("SECURITY_CONTEXT") if session else None
    if not isinstance(context, SecurityContext) or not context.is_authenticated:
        raise UnauthorizedException("Sign in with your corporate account", code="AUTH_REQUIRED")
    identity = identity_from_request(request)
    if identity.subject != f"{context.attributes.get('iss')}|{context.attributes.get('sub')}" or any(
        name in context.attributes for name in ("koinon_token", "koinon_token_id")
    ):
        raise AccessDenied("Use the native browser session", code="INTERACTIVE_IDENTITY_REQUIRED")
    return identity.subject


def page_html(branding, locale, heading, trusted_body):
    brand = BrandingValues.model_validate(branding.model_dump())
    palette = brand.palette.light
    nonce = token_urlsafe(24)
    logo = (
        f'<img class="logo" src="{escape(brand.logo_light, quote=True)}" '
        f'alt="{escape(brand.product_name, quote=True)}">'
        if brand.logo_light
        else f'<p class="brand">{escape(brand.product_name)}</p>'
    )
    css = (
        "@font-face{font-family:Interface;src:url('/auth/communications/fonts/"
        f"{brand.font_family}.woff2') format('woff2');font-display:swap}}"
        "*{box-sizing:border-box}body{margin:0;padding:24px 12px;"
        f"background:{palette.canvas};color:{palette.text};font-family:Interface,Arial,sans-serif}}"
        "main{max-width:600px;margin:24px auto;padding:24px;"
        f"background:{palette.surface};border:1px solid {palette.line};border-radius:12px}}"
        ".logo{max-width:180px;max-height:56px;object-fit:contain;object-position:left;margin-bottom:24px}"
        "h1{font-size:26px;line-height:1.25}p,label{line-height:1.6}"
        f"a{{color:{palette.accent}}}button{{font:inherit;padding:12px 18px;border:0;border-radius:8px;"
        f"background:{palette.action};color:{palette.action_text};cursor:pointer}}"
        f"button.secondary{{background:{palette.canvas};color:{palette.text};"
        f"border:1px solid {palette.line};margin-left:8px}}label{{display:block;margin:12px 0}}"
        "input,select{display:block;max-width:100%;font:inherit;padding:8px;"
        f"border:1px solid {palette.line};border-radius:6px}}footer{{margin-top:24px;padding-top:16px;"
        f"border-top:1px solid {palette.line};font-size:12px;color:{palette.muted}}}"
    )
    html = (
        f'<!doctype html><html lang="{escape(locale)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(heading)} | {escape(brand.product_name)}</title>"
        f'<style nonce="{nonce}">{css}</style></head><body><main>{logo}'
        f"<h1>{escape(heading)}</h1>{trusted_body}<footer><p>Powered by koinon<br>"
        f"© {datetime.now(UTC).year} Firefly Software Foundation</p></footer></main></body></html>"
    )
    return html, {
        **HEADERS,
        "Content-Security-Policy": (
            f"default-src 'none'; style-src 'nonce-{nonce}'; font-src 'self'; img-src data:; "
            "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
        ),
    }


class CommunicationsBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path", "").startswith(
                ("/auth/invitations/email/", "/auth/notifications/preferences")
            )
        ):
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] != "http.request":
                    return
                body.extend(message.get("body", b""))
                if len(body) > 4096:
                    return await Response(status_code=413, headers=HEADERS)(scope, receive, send)
                if not message.get("more_body"):
                    break
            original, sent = receive, False

            async def bounded_receive():
                nonlocal sent
                if sent:
                    return await original()
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            receive = bounded_receive
        await self.app(scope, receive, send)


async def _form(request, allowed) -> dict[str, str]:
    values = await parse_form(request)
    pairs = values.multi_items()
    if (
        len(pairs) > 12
        or len({key for key, _ in pairs}) != len(pairs)
        or set(values) - allowed
        or any(not isinstance(value, str) or len(value) > 512 for _, value in pairs)
    ):
        raise InvalidRequestException("Use the supplied form", code="INVALID_COMMUNICATION_FORM")
    data = {key: value for key, value in pairs if isinstance(value, str)}
    token = getattr(request.state, "csrf_token", "")
    supplied = data.get("_csrf", "")
    if not token or not supplied or not compare_digest(token, supplied):
        raise AccessDenied("Reload the form before submitting", code="CSRF_INVALID")
    return data


def install_communications(app, context):
    app.add_middleware(CommunicationsBoundary)

    def defaults():
        return context.get_bean(OrganizationBrandingService).defaults

    def response(brand, locale, heading, body, status=200):
        html, headers = page_html(brand, locale, heading, body)
        return HTMLResponse(html, status_code=status, headers=headers)

    def sign_in(request):
        session = getattr(request.state, "session", None)
        if session is None or request.method != "GET":
            raise UnauthorizedException("Sign in with your corporate account", code="AUTH_REQUIRED")
        session.set_attribute("oauth2_redirect_uri", request.url.path)
        return RedirectResponse("/oauth2/authorization/koinon", status_code=302, headers=HEADERS)

    async def invitation(request):
        identifier = str(UUID(str(request.path_params["invitation_id"])))
        try:
            owner = browser_owner(request)
        except UnauthorizedException:
            return sign_in(request)
        service = context.get_bean(EmailInvitationService)
        claims = request.state.session.get_attribute("SECURITY_CONTEXT").attributes
        if request.method == "POST":
            form = await _form(request, {"_csrf", "decision"})
            if form.get("decision") not in {"accept", "decline"}:
                raise InvalidRequestException("Choose accept or decline", code="INVALID_INVITATION_DECISION")
            operation = service.accept if form["decision"] == "accept" else service.decline
            await operation(owner, identifier, claims)
            return RedirectResponse("/auth/invitations/email/" + identifier, status_code=303, headers=HEADERS)
        review = await service.review(owner, identifier, claims)
        locale, _ = await context.get_bean(CommunicationLocales).resolve(
            owner=owner, tenant_id=review.tenant_id
        )
        brand = await context.get_bean(CommunicationContent)._brand(review.tenant_id)
        scope = review.workspace_name or review.organization_name
        body = (
            "<p>"
            + escape(
                translate(locale, "invite_scope", scope=scope, role=translate(locale, "role_" + review.role))
            )
            + "</p><p>"
            + escape(translate(locale, "invite_expiry", expiry=_expiry(review.expires_at, "UTC", locale)))
            + "</p>"
        )
        if review.can_accept:
            body += (
                "<p>"
                + escape(translate(locale, "invite_sign_in"))
                + '</p><form method="post"><input type="hidden" name="_csrf" value="'
                + escape(getattr(request.state, "csrf_token", ""), quote=True)
                + '"><button name="decision" value="accept">'
                + escape(translate(locale, "accept"))
                + '</button><button class="secondary" name="decision" value="decline">'
                + escape(translate(locale, "decline"))
                + "</button></form>"
            )
        else:
            body += "<p>" + escape(translate(locale, "invitation_closed")) + "</p>"
        return response(brand, locale, translate(locale, "invite_heading"), body)

    async def preferences(request):
        try:
            owner = browser_owner(request)
        except UnauthorizedException:
            return sign_in(request)
        service = context.get_bean(NotificationService)
        current = await service.preferences(owner)
        if request.method == "POST":
            form = await _form(
                request,
                {
                    "_csrf",
                    "expected_revision",
                    "digest",
                    "local_time",
                    "weekday",
                    "day_of_month",
                    "notification_locale",
                },
            )
            body = NotificationPreferencesInput.model_validate(
                dict(
                    expected_revision=int(form.get("expected_revision", "-1")),
                    rules=[
                        rule.model_dump(exclude={"required", "email_available"}) for rule in current.rules
                    ],
                    digest=form.get("digest", "off"),
                    schedule=dict(
                        local_time=form.get("local_time", "09:00"),
                        weekday=int(form.get("weekday", "0")),
                        day_of_month=int(form.get("day_of_month", "1")),
                    ),
                    notification_locale=form.get("notification_locale") or current.notification_locale,
                )
            )
            await service.update_preferences(owner, body)
            return RedirectResponse("/auth/notifications/preferences", status_code=303, headers=HEADERS)
        locale = current.effective_locale
        spanish = locale.startswith("es")
        options = "".join(
            '<option value="'
            + cadence
            + '"'
            + (" selected" if cadence == current.digest else "")
            + ">"
            + escape(
                ("Desactivado" if spanish else "Off") if cadence == "off" else translate(locale, cadence)
            )
            + "</option>"
            for cadence in current.allowed_digests
        )
        body = (
            "<p>"
            + escape(current.time_zone)
            + '</p><form method="post"><input type="hidden" name="_csrf" value="'
            + escape(getattr(request.state, "csrf_token", ""), quote=True)
            + '"><input type="hidden" name="expected_revision" value="'
            + str(current.revision)
            + '"><label>'
            + ("Frecuencia" if spanish else "Frequency")
            + '<select name="digest">'
            + options
            + "</select></label><label>"
            + ("Hora local" if spanish else "Local time")
            + '<input name="local_time" type="time" value="'
            + current.schedule.local_time
            + '"></label><label>'
            + ("Día de la semana (lunes = 0)" if spanish else "Weekday (Monday = 0)")
            + '<input name="weekday" type="number" min="0" max="6" value="'
            + str(current.schedule.weekday)
            + '"></label><label>'
            + ("Día del mes" if spanish else "Day of month")
            + '<input name="day_of_month" type="number" min="1" max="31" value="'
            + str(current.schedule.day_of_month)
            + '"></label><button>'
            + escape(translate(locale, "save"))
            + "</button></form>"
        )
        return response(defaults(), locale, translate(locale, "preferences"), body)

    async def inbox(request):
        try:
            owner = browser_owner(request)
        except UnauthorizedException:
            return sign_in(request)
        page = await context.get_bean(NotificationService).page(owner, page=1, page_size=25)
        locale, _ = await context.get_bean(CommunicationLocales).resolve(owner=owner)
        body = "".join(
            "<article><h2>"
            + escape(row.title)
            + "</h2><p>"
            + escape(row.body)
            + "</p><p>"
            + escape(row.organization_name)
            + "</p></article>"
            for row in page.items
        )
        return response(defaults(), locale, translate(locale, "inbox"), body)

    async def setup(request):
        try:
            owner = browser_owner(request)
        except UnauthorizedException:
            return sign_in(request)
        from koinon.catalog.service import CatalogService

        members = await context.get_bean(CatalogService).memberships(owner)
        organizations = sorted(
            {row.tenant_id for row in members if row.role == "admin" and row.workspace_id is None}
        )
        if not organizations:
            raise AccessDenied("Current organization administrator access is required", code="ACCESS_DENIED")
        tenant = organizations[0] if len(organizations) == 1 else None
        locale, _ = await context.get_bean(CommunicationLocales).resolve(owner=owner, tenant_id=tenant)
        brand = await context.get_bean(CommunicationContent)._brand(tenant) if tenant else defaults()
        spanish = locale.startswith("es")
        links = [
            ("Primer inicio y SSO" if spanish else "First start and SSO", "operations/first-start/"),
            (
                "Identidad corporativa y marca" if spanish else "Corporate identity and branding",
                "operations/identity-appearance/",
            ),
            ("Almacenamiento" if spanish else "Storage", "operations/storage-configuration/"),
            ("Modelos y agentes" if spanish else "Models and agents", "reference/api/models-agents/"),
            ("Permisos" if spanish else "Permissions", "guides/api-permissions/"),
            ("Conexiones MCP" if spanish else "MCP connections", "operations/mcp-authentication/"),
        ]
        intro = (
            "Inicia sesión con SSO y configura la identidad, el almacenamiento, "
            "los modelos y los permisos de tu organización."
            if spanish
            else (
                "Sign in with SSO, then configure your organization's identity, "
                "storage, models and permissions."
            )
        )
        body = (
            "<p>"
            + escape(intro)
            + "</p><ul>"
            + "".join(
                '<li><a href="https://fireflyframework.github.io/firefly-koinon/'
                + path
                + '">'
                + escape(label)
                + "</a></li>"
                for label, path in links
            )
            + "</ul>"
        )
        return response(brand, locale, translate(locale, "welcome_heading", product=brand.product_name), body)

    async def font(request):
        family = request.path_params["family"]
        if family not in {"Inter", "Manrope"}:
            return Response(status_code=404, headers=HEADERS)
        return FileResponse(
            font_asset(family),
            media_type="font/woff2",
            headers={"Cache-Control": "public,max-age=86400", "X-Content-Type-Options": "nosniff"},
        )

    app.router.routes.extend(
        [
            Route("/auth/invitations/email/{invitation_id:uuid}", invitation, methods=["GET", "POST"]),
            Route("/auth/notifications/preferences", preferences, methods=["GET", "POST"]),
            Route("/auth/notifications", inbox, methods=["GET"]),
            Route("/auth/setup", setup, methods=["GET"]),
            Route("/auth/communications/fonts/{family}.woff2", font, methods=["GET"]),
        ]
    )
