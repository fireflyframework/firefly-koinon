# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Organization bounds constrain personal opt-in without old-client resets."""

from conftest import bearer

PATH = "/api/v1/tenants/north/chat/settings"


def test_organization_can_bound_or_disable_project_memory_and_old_put_preserves(client):
    default = client.get(PATH, headers=bearer()).json()
    assert default["memory"]["allow_project_memory"] is True
    policy = {
        "allow_project_memory": False,
        "max_history_messages": 12,
        "max_history_tokens": 2048,
        "max_project_memory_messages": 6,
    }
    result = client.put(
        PATH,
        headers=bearer(),
        json={
            "default_agent_id": None,
            "expected_revision": 0,
            "memory": policy,
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["memory"] == policy
    legacy = client.put(PATH, headers=bearer(), json={"default_agent_id": None, "expected_revision": 1})
    assert legacy.status_code == 200
    assert legacy.json()["memory"] == policy
    for value in [
        None,
        {"allow_project_memory": "false"},
        {"max_history_messages": True},
        {"max_history_messages": 2, "max_project_memory_messages": 3},
    ]:
        denied = client.put(
            PATH,
            headers=bearer(),
            json={
                "default_agent_id": None,
                "expected_revision": 2,
                "memory": value,
            },
        )
        assert denied.status_code in {400, 422}
    denied = client.put(
        PATH,
        headers=bearer("viewer"),
        json={
            "default_agent_id": None,
            "expected_revision": 2,
            "memory": policy,
        },
    )
    assert denied.status_code == 403


def test_partial_nested_policy_preserves_existing_bounds(client):
    current = {
        "allow_project_memory": False,
        "max_history_messages": 12,
        "max_history_tokens": 2048,
        "max_project_memory_messages": 6,
    }
    assert (
        client.put(
            PATH,
            headers=bearer(),
            json={
                "default_agent_id": None,
                "expected_revision": 0,
                "memory": current,
            },
        ).status_code
        == 200
    )
    updated = client.put(
        PATH,
        headers=bearer(),
        json={
            "default_agent_id": None,
            "expected_revision": 1,
            "memory": {"allow_project_memory": True},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["memory"] == {**current, "allow_project_memory": True}


def test_explicit_limits_above_deployment_reject_but_inherited_defaults_clamp(client):
    from koinon.assistants.settings import AssistantSettings

    settings = client.native_app.state.context.get_bean(AssistantSettings)
    settings.max_history_messages = 8
    settings.max_history_tokens = 512
    effective = client.get(PATH, headers=bearer()).json()["memory"]
    assert effective["max_history_messages"] == effective["max_project_memory_messages"] == 8
    assert effective["max_history_tokens"] == 512
    for policy in [
        {"max_history_messages": 9},
        {"max_history_tokens": 513},
        {"max_project_memory_messages": 9},
    ]:
        denied = client.put(
            PATH,
            headers=bearer(),
            json={
                "default_agent_id": None,
                "expected_revision": 0,
                "memory": policy,
            },
        )
        assert denied.status_code in {400, 422}
    assert (
        client.put(
            PATH,
            headers=bearer(),
            json={
                "default_agent_id": None,
                "expected_revision": 0,
            },
        ).status_code
        == 200
    )
    assert client.get(PATH, headers=bearer()).json()["memory"] == effective


def test_partial_history_is_validated_after_saved_project_limit_is_merged(client):
    assert (
        client.put(
            PATH,
            headers=bearer(),
            json={
                "default_agent_id": None,
                "expected_revision": 0,
                "memory": {"max_history_messages": 30, "max_project_memory_messages": 6},
            },
        ).status_code
        == 200
    )
    updated = client.put(
        PATH,
        headers=bearer(),
        json={
            "default_agent_id": None,
            "expected_revision": 1,
            "memory": {"max_history_messages": 10},
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["memory"]["max_project_memory_messages"] == 6
    denied = client.put(
        PATH,
        headers=bearer(),
        json={
            "default_agent_id": None,
            "expected_revision": 2,
            "memory": {"max_project_memory_messages": 12},
        },
    )
    assert denied.status_code in {400, 422}
    current = client.get(PATH, headers=bearer()).json()
    assert current["revision"] == 2
    assert current["memory"]["max_history_messages"] == 10
    assert current["memory"]["max_project_memory_messages"] == 6
