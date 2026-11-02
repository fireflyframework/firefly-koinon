# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from uuid import uuid4

from conftest import ISSUER, bearer

from koinon.communications.entities import OutboxRecord
from koinon.communications.observation_repository import DeliveryInspectionRepository
from koinon.communications.repositories import OutboxRepository


def test_native_app_resolves_full_recovery_graph_and_passive_http_checks_do_not_send(client):
    context = client.app.state.context
    from koinon.communications.observations import EmailOperationObservations
    from koinon.communications.recovery import WelcomeRecoveryService
    from koinon.communications.submission import EmailSubmission

    submission = context.get_bean(EmailSubmission)
    assert submission.operation_observations is context.get_bean(EmailOperationObservations)
    assert submission.welcome_recovery is context.get_bean(WelcomeRecoveryService)
    assert submission.operation_observations.authority is submission.welcome_recovery
    identifier = str(uuid4())

    async def seed():
        await context.get_bean(OutboxRepository).save(
            OutboxRecord(
                id=identifier,
                dedupe_key=identifier,
                tenant_id="north",
                owner_subject=ISSUER + "|admin",
                kind="welcome",
                event_json={},
                status="unknown",
                attempt_count=1,
                generation=2,
                created_at=datetime.now(UTC),
                next_attempt_at=datetime.now(UTC),
            )
        )

    client.portal.call(seed)
    root = f"/api/v1/tenants/north/communications/deliveries/{identifier}"
    response = client.get(root + "/recovery", headers=bearer())
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["submission_status"] == "unknown" and value["attempt_count"] == 1
    assert value["can_inspect"] is False and value["can_recover_welcome"] is False
    assert client.get(root + "/observations", headers=bearer()).json() == {"items": [], "has_more": False}
    assert client.get(root + "/recovery", headers=bearer("viewer")).status_code == 403
    assert client.get(root.replace("/north/", "/south/") + "/recovery", headers=bearer()).status_code == 403

    async def unchanged():
        row = await context.get_bean(OutboxRepository).find_by_id(identifier)
        assert row.status == "unknown" and row.attempt_count == 1
        assert not await context.get_bean(DeliveryInspectionRepository).find_all()

    client.portal.call(unchanged)
