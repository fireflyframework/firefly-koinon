# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One native template source for transport payloads, structured preview and visual evidence."""

import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import unescape
from importlib.resources import files
from io import BytesIO
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from PIL import Image
from pyfly.container import component
from pyfly.notifications.template import Jinja2TemplateEngine, NotificationTemplateEngine

from koinon.communications.directory import delivery_address
from koinon.communications.dtos import CommunicationUsageSummary, EmailPreview
from koinon.communications.locales import translate
from koinon.communications.settings import InstallationLinks
from koinon.organization_branding.dtos import BrandingValues
from koinon.organization_branding.images import sanitize_image


def _calendar_label(start, end, spanish):
    months = (
        (
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        )
        if spanish
        else (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
    )
    if start.year == end.year and start.month == end.month:
        return (
            f"Del {start.day} al {end.day} de {months[end.month - 1]} de {end.year}"
            if spanish
            else f"{months[start.month - 1]} {start.day} to {end.day}, {end.year}"
        )
    left = (
        f"{start.day} de {months[start.month - 1]} de {start.year}"
        if spanish
        else f"{months[start.month - 1]} {start.day}, {start.year}"
    )
    right = (
        f"{end.day} de {months[end.month - 1]} de {end.year}"
        if spanish
        else f"{months[end.month - 1]} {end.day}, {end.year}"
    )
    return f"Del {left} al {right}" if spanish else f"{left} to {right}"


@dataclass(frozen=True, slots=True)
class InlineImage:
    content_id: str
    content_type: str
    data: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    html: str = field(repr=False)
    text: str = field(repr=False)
    images: tuple[InlineImage, ...] = field(repr=False)


@component(name="communications.email_renderer")
class EmailRenderer:
    def __init__(self, links: InstallationLinks):
        self.links = links
        assets = files("koinon.communications").joinpath("assets")
        self.engine: NotificationTemplateEngine = Jinja2TemplateEngine(
            {
                "communications.html": assets.joinpath("email.html.jinja").read_text(),
                "communications.text": assets.joinpath("email.txt.jinja").read_text(),
            }
        )

    @staticmethod
    def preview_html(rendered: RenderedEmail) -> str:
        html = rendered.html
        for image in rendered.images:
            html = html.replace(
                "cid:" + image.content_id,
                "data:" + image.content_type + ";base64," + base64.b64encode(image.data).decode("ascii"),
            )
        return html

    def _link(self, value):
        if value is None:
            return None
        parsed, origin = urlsplit(value), urlsplit(self.links.public_url)
        if (
            not self.links.public_url
            or (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc)
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/")
            or parsed.path.startswith("//")
            or "\\" in value
            or len(value) > 2048
            or any(ord(c) < 33 for c in value)
        ):
            raise ValueError("Email actions require a fixed canonical same-origin URL")
        return value

    async def render(
        self,
        preview: EmailPreview,
        *,
        action_url,
        preferences_url=None,
        usage: CommunicationUsageSummary | None = None,
        locale="en-US",
    ) -> RenderedEmail:
        preview = EmailPreview.model_validate(preview.model_dump())
        branding = BrandingValues.model_validate(preview.branding.model_dump())
        if (
            not 1 <= len(preview.subject) <= 240
            or any(ord(char) < 32 or ord(char) == 127 for char in preview.subject + preview.sender_name)
            or delivery_address(preview.recipient_email) is None
            or len(preview.paragraphs) > 12
            or any(len(value) > 2000 for value in preview.paragraphs)
            or len(preview.heading) > 240
            or len(preview.footer) > 1000
        ):
            raise ValueError("Email text and headers must be readable and bounded")
        images, logo = (), None
        if branding.logo_light:
            data_url = sanitize_image(branding.logo_light)
            if data_url is None:
                raise ValueError("A configured inline logo is unavailable")
            content = base64.b64decode(data_url.partition(",")[2], validate=True)
            with Image.open(BytesIO(content)) as image:
                factor = min(180 / image.width, 56 / image.height, 1)
                logo = dict(
                    width=max(1, round(image.width * factor)), height=max(1, round(image.height * factor))
                )
            images = (InlineImage("brand-logo", "image/png", content),)
        spanish = locale.lower().startswith("es")
        metrics, window, window_zone, unavailable = [], None, None, None
        if usage is not None:
            usage = CommunicationUsageSummary.model_validate(usage)
            zone = ZoneInfo(usage.time_zone)
            start, end = usage.window_start.astimezone(zone), usage.window_end.astimezone(zone)
            window = _calendar_label(start, end, spanish)
            window_zone = (
                usage.time_zone
                + ", "
                + start.strftime("%H:%M %Z")
                + (" a " if spanish else " to ")
                + end.strftime("%H:%M %Z")
            )
            metrics = [
                dict(
                    label=("Solicitudes a " if spanish else "Requests to ") + branding.assistant_name,
                    value=usage.assistant_runs,
                ),
                dict(label="Completadas" if spanish else "Completed runs", value=usage.completed_runs),
                dict(label="Fallidas" if spanish else "Failed runs", value=usage.failed_runs),
            ]
            if usage.mcp_request_status == "available" and usage.mcp_requests is not None:
                metrics.append(
                    dict(label="Solicitudes MCP" if spanish else "MCP requests", value=usage.mcp_requests)
                )
            else:
                unavailable = (
                    "La actividad de MCP todavía no se incluye en este resumen."
                    if spanish
                    else "MCP activity is not included in this summary yet."
                )
        observations, projects = [], []
        if preview.activity_summary is not None:
            summary = preview.activity_summary
            zone = ZoneInfo(summary.window.time_zone)
            start, end = summary.window.start_at.astimezone(zone), summary.window.end_at.astimezone(zone)
            window, window_zone = _calendar_label(start, end, spanish), summary.window.time_zone
            missing_label = "Sin observación" if spanish else "Not observed"

            def observed(value):
                return (
                    missing_label
                    if value.value is None
                    else str(value.value) + (" (parcial)" if spanish else " (partial)")
                    if value.status == "partial"
                    else str(value.value)
                )

            metrics = [
                dict(label=label, value=observed(value))
                for label, value in (
                    ("Piezas creadas" if spanish else "Pieces created", summary.knowledge.created),
                    ("Piezas actualizadas" if spanish else "Pieces updated", summary.knowledge.updated),
                    ("Piezas consultadas" if spanish else "Pieces consulted", summary.knowledge.consulted),
                    ("Herramientas MCP" if spanish else "MCP tool calls", summary.mcp.tool_calls),
                )
            ]
            unavailable = (
                (
                    "La cobertura de este periodo es parcial."
                    if spanish
                    else "Observation coverage for this window is partial."
                )
                if not summary.coverage.complete_window
                else None
            )
            observations = [
                ("Solicitudes MCP" if spanish else "MCP requests") + ": " + observed(summary.mcp.requests),
                ("Herramientas completadas" if spanish else "Completed tools")
                + ": "
                + observed(summary.mcp.succeeded),
                ("Herramientas con errores" if spanish else "Tools with errors")
                + ": "
                + observed(summary.mcp.failed),
                ("Tiempo medio por herramienta" if spanish else "Average time per tool")
                + ": "
                + observed(summary.mcp.average_duration_ms)
                + (" ms" if summary.mcp.average_duration_ms.value is not None else ""),
            ]
            if (
                summary.audience == "organization_administrators"
                and summary.mcp.p95_duration_ms.value is not None
            ):
                observations.append(
                    ("El 95 % de las herramientas terminó en " if spanish else "95% of tools completed in ")
                    + observed(summary.mcp.p95_duration_ms)
                    + (" ms o menos." if spanish else " ms or less.")
                )
            project_counts = [
                (project, [project.knowledge.created, project.knowledge.updated, project.knowledge.consulted])
                for project in summary.top_projects[:5]
            ]
            totals = [
                sum(value.value for value in counts if value.value is not None)
                for _, counts in project_counts
            ]
            maximum = max(totals, default=1) or 1
            for (project, counts), total in zip(project_counts, totals, strict=True):
                complete = all(value.value is not None for value in counts)
                projects.append(
                    dict(
                        name=project.name,
                        value=(
                            translate(locale, "project_total", count=total)
                            + (
                                (" (parcial)" if spanish else " (partial)")
                                if any(value.status == "partial" for value in counts)
                                else ""
                            )
                        )
                        if complete
                        else missing_label,
                        details="; ".join(
                            translate(locale, "project_" + category) + ": " + observed(value)
                            for category, value in zip(
                                ("created", "updated", "consulted"), counts, strict=True
                            )
                        ),
                        percent=round(100 * total / maximum) if complete else 0,
                    )
                )
            token_counts = [
                summary.models.input_tokens,
                summary.models.output_tokens,
                summary.models.embedding_tokens,
            ]
            if any(value.value is not None for value in token_counts):
                observations.append(
                    (
                        "Tokens observados de entrada / salida / embeddings"
                        if spanish
                        else "Observed input / output / embedding tokens"
                    )
                    + ": "
                    + " / ".join(observed(value) for value in token_counts)
                )
            cost = summary.models.cost
            if cost.amount is not None:
                observations.append(
                    ("Coste observado" if spanish else "Observed cost")
                    + ": "
                    + str(cost.amount)
                    + " "
                    + (cost.currency or "")
                    + " ("
                    + (cost.source or "")
                    + ")"
                )
        context: dict[str, object] = dict(
            preview=preview,
            brand=branding,
            palette=branding.palette.light,
            logo=logo,
            action_url=self._link(action_url),
            preferences_url=self._link(preferences_url),
            preferences_label=translate(locale, "preferences"),
            metrics=metrics,
            projects=projects,
            projects_label="Proyectos con actividad" if spanish else "Projects with activity",
            projects_description=translate(locale, "project_counts_description"),
            observations=observations,
            window=window,
            window_zone=window_zone,
            unavailable=unavailable,
            locale="es" if spanish else "en",
            year=datetime.now(UTC).year,
            organization_label=translate(locale, "organization"),
            workspace_label=translate(locale, "workspace"),
        )
        html = await self.engine.render("communications.html", context)
        text = unescape(await self.engine.render("communications.text", context)).strip() + "\n"
        if len(html.encode()) > 131072 or len(text.encode()) > 32768:
            raise ValueError("Rendered email exceeds the bounded template contract")
        return RenderedEmail(html, text, images)
