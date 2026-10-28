# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import bearer
from test_chat_sse import seed


def test_native_signed_activity_route_pages_calls_and_projects_history(client):
    async def populate():
        from koinon.assistants.entities import ChatEvent
        from koinon.assistants.lifecycle import timestamp
        from koinon.assistants.repositories import ChatEventRepository, ChatRunRepository
        from koinon.assistants.tool_activity import ToolActivity

        context = client.native_app.state.context
        run_id = await seed(context)
        repository = context.get_bean(ChatEventRepository)
        sequence = 3
        for index in range(7):
            for status in ("queued", "running", "completed"):
                sequence += 1
                activity = ToolActivity(
                    call_id=f"call-{index}",
                    tool_name="inspect_schema",
                    status=status,
                    occurred_at=timestamp().isoformat(),
                    summary="Inspect dataset schema",
                )
                await repository.save(
                    ChatEvent(
                        id=f"activity-{sequence}",
                        run_id=run_id,
                        sequence=sequence,
                        type="tool_activity",
                        data={"tool_activity": activity.model_dump(exclude_none=True)},
                    )
                )
        row = await context.get_bean(ChatRunRepository).find_by_id(run_id)
        return run_id, row.thread_id

    run, thread = client.portal.call(populate)
    path = f"/api/v1/tenants/north/chat/runs/{run}/activity"
    response = client.get(path + "?page=2&page_size=2", headers=bearer())
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == 7 and page["pages"] == 4
    assert [item["call_id"] for item in page["items"]] == ["call-2", "call-3"]
    assert all(item["status"] == "completed" for item in page["items"])
    history = client.get(f"/api/v1/tenants/north/chat/threads/{thread}/messages", headers=bearer())
    assert history.status_code == 200
    answer = next(item for item in history.json()["items"] if item["role"] == "assistant")
    assert answer["tool_activity_count"] == 7 and len(answer["tool_activities"]) == 5
    assert answer["tool_activity_has_more"] is True
    assert client.get(path, headers=bearer("viewer")).status_code == 403
    assert client.get(path.replace("/north/", "/south/"), headers=bearer()).status_code == 403
    assert client.get(path + "?page_size=101", headers=bearer()).status_code == 400
