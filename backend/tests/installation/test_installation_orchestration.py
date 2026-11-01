# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import SecretStr
from test_installation_manifest import example

from koinon.installation.authority import InstallationError, InstallationPermit
from koinon.installation.dtos import InstallationPlan
from koinon.installation.service import InstallationProvisioner


def fixture(completed=False):
    admission, writes, indexes, probe, qualification = (AsyncMock() for _ in range(5))
    admission.admit.return_value = InstallationPermit("run", "example", 1, "owner", completed)
    admission.receipt.return_value = {"status": "completed", "checkpoints": {}}
    writes.probe_snapshot.return_value = SimpleNamespace(
        kind="openai",
        api="chat",
        base_url="https://api.openai.com/v1",
        model_ids=["chat-model"],
        secret=SecretStr("inert"),
    )
    probe.check.return_value = [
        {"id": "connection", "status": "passed"},
        {"id": "models", "status": "passed"},
    ]
    resolver = Mock()
    service = InstallationProvisioner(admission, writes, indexes, probe, qualification, resolver)
    return service, admission, writes, indexes, probe, qualification


async def test_completed_installation_is_read_only_and_does_not_reprobe_or_overwrite():
    service, admission, writes, indexes, probe, qualification = fixture(True)
    result = await service.apply(
        InstallationPlan.model_validate(example()), {"chat": None, "embedding": None}, resume=False
    )
    assert result["status"] == "completed"
    assert (
        not writes.mock_calls
        and not indexes.mock_calls
        and not probe.mock_calls
        and not qualification.mock_calls
    )
    admission.finish.assert_not_called()


async def test_external_failure_marks_partial_without_queuing_job_or_continuing_default():
    service, admission, writes, indexes, probe, qualification = fixture()
    qualification.qualify.side_effect = RuntimeError("provider-body-that-must-not-escape")
    with pytest.raises(InstallationError, match="INSTALLATION_PROVIDER_QUALIFICATION_FAILED"):
        await service.apply(
            InstallationPlan.model_validate(example()), {"chat": None, "embedding": None}, resume=False
        )
    admission.fail.assert_awaited_once()
    writes.agent.assert_not_called()
    writes.default_agent.assert_not_called()
    indexes.intent.assert_not_called()


async def test_empty_indexes_are_qualified_before_default_is_exposed():
    service, admission, writes, indexes, probe, qualification = fixture()
    await service.apply(
        InstallationPlan.model_validate(example()), {"chat": None, "embedding": None}, resume=False
    )
    indexes.intent.assert_awaited_once()
    indexes.create.assert_awaited_once()
    indexes.ready.assert_awaited_once()
    indexes.activate.assert_awaited_once()
    writes.agent.assert_awaited_once()
    writes.default_agent.assert_awaited_once()
    admission.finish.assert_awaited_once()


async def test_embedding_provider_is_qualified_only_by_index_path_never_chat_completion():
    service, _, writes, indexes, _, qualification = fixture()
    plan = InstallationPlan.model_validate(example())
    await service.apply(plan, {"chat": None, "embedding": None}, resume=False)
    assert qualification.qualify.await_count == 2
    assert {call.args[1] for call in qualification.qualify.await_args_list} == {"chat-model"}
    assert all(call.args[1] != "embedding-model" for call in qualification.qualify.await_args_list)
    assert indexes.intent.await_args.args[1].model_id == "embedding-model"
    assert {call.args[1] for call in writes.qualified.await_args_list} == {"chat"}
