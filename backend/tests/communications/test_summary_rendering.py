# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

import pytest
from test_email_templates import preview

from koinon.activity.dtos import (
    ActivityCoverage,
    ActivitySummary,
    ActivityWindow,
    KnowledgeActivityCounts,
    McpActivityCounts,
    ModelActivityCounts,
    ObservedCost,
    ObservedCount,
)
from koinon.communications.locales import subject_line
from koinon.communications.settings import InstallationLinks
from koinon.communications.templates import EmailRenderer


@pytest.mark.parametrize("locale", ["en-US", "es-ES"])
@pytest.mark.parametrize("kind", ["invitation", "welcome", "security", "digest"])
async def test_all_subjects_are_personalized_and_reject_header_injection(locale, kind):
    result = subject_line(
        locale, product="Research Brain", kind=kind, scope="Knowledge team", cadence="monthly"
    )
    assert "Research Brain" in result and "Knowledge team" in result and len(result) <= 240
    for field in ("product", "scope"):
        values = dict(product="Research Brain", scope="Knowledge team")
        values[field] = "Injected\r\nBcc:other@example.test"
        with pytest.raises(ValueError):
            subject_line(locale, kind=kind, cadence="monthly", **values)


async def test_actual_activity_metrics_preserve_unavailable_and_html_text_parity():
    summary = ActivitySummary(
        tenant_id="north",
        audience="personal",
        window=ActivityWindow(
            start_at=datetime.fromisoformat("2026-10-01T00:00:00Z"),
            end_at=datetime.fromisoformat("2026-11-01T00:00:00Z"),
            time_zone="Europe/Madrid",
        ),
        coverage=ActivityCoverage(observed_since=None, complete_window=False, missing_observations=1),
        knowledge=KnowledgeActivityCounts(
            created=ObservedCount(value=4, status="observed"),
            updated=ObservedCount(status="unavailable"),
            consulted=ObservedCount(status="unavailable"),
        ),
        mcp=McpActivityCounts(
            **{
                name: ObservedCount(status="unavailable")
                for name in (
                    "requests",
                    "tool_calls",
                    "succeeded",
                    "failed",
                    "rejected",
                    "average_duration_ms",
                    "p95_duration_ms",
                )
            }
        ),
        models=ModelActivityCounts(
            input_tokens=ObservedCount(status="unavailable"),
            output_tokens=ObservedCount(status="unavailable"),
            embedding_tokens=ObservedCount(status="unavailable"),
            cost=ObservedCost(status="unavailable"),
        ),
    )
    renderer = EmailRenderer(InstallationLinks(public_url="https://brain.test"))
    value = preview(activity_summary=summary, effective_locale="es-ES")
    rendered = await renderer.render(
        value, action_url="https://brain.test/auth/notifications/preferences", locale="es-ES"
    )
    assert "Piezas creadas" in rendered.html and "Piezas creadas" in rendered.text
    assert "Sin observación" in rendered.html and "Sin observación" in rendered.text
    assert "4" in rendered.html and "4" in rendered.text
    assert "MCP" in rendered.html and "Claude" not in rendered.html


def activity_summary(*, audience="personal", projects=None):
    from koinon.activity.dtos import ProjectActivity

    missing = ObservedCount(status="unavailable")
    knowledge = KnowledgeActivityCounts(
        created=ObservedCount(value=2, status="observed"),
        updated=ObservedCount(value=3, status="observed"),
        consulted=ObservedCount(value=5, status="observed"),
    )
    return ActivitySummary(
        tenant_id="north",
        audience=audience,
        window=ActivityWindow(
            start_at=datetime.fromisoformat("2026-10-01T00:00:00Z"),
            end_at=datetime.fromisoformat("2026-11-01T00:00:00Z"),
            time_zone="Europe/Madrid",
        ),
        coverage=ActivityCoverage(observed_since=None, complete_window=False, missing_observations=None),
        knowledge=knowledge,
        top_projects=projects
        if projects is not None
        else [
            ProjectActivity(project_id="research", workspace_id="space", name="Research", knowledge=knowledge)
        ],
        mcp=McpActivityCounts(
            **{
                key: missing
                for key in (
                    "requests",
                    "tool_calls",
                    "succeeded",
                    "failed",
                    "rejected",
                    "average_duration_ms",
                    "p95_duration_ms",
                )
            }
        ),
        models=ModelActivityCounts(
            input_tokens=missing,
            output_tokens=missing,
            embedding_tokens=missing,
            cost=ObservedCost(status="unavailable"),
        ),
    )


@pytest.mark.parametrize(
    "locale,total,created,caption",
    [
        ("en-US", "10 activities", "Created: 2", "A piece may appear in more than one category."),
        ("es-ES", "10 actividades", "Creadas: 2", "Una pieza puede aparecer en más de una categoría."),
    ],
)
async def test_project_bars_name_activity_sum_and_preserve_category_counts_in_html_and_text(
    locale, total, created, caption
):
    value = preview(activity_summary=activity_summary(), effective_locale=locale)
    rendered = await EmailRenderer(InstallationLinks(public_url="https://brain.test")).render(
        value, action_url="https://brain.test/auth/notifications/preferences", locale=locale
    )
    for body in (rendered.html, rendered.text):
        assert total in body and created in body and caption in body
        assert "Research: 10" in body
