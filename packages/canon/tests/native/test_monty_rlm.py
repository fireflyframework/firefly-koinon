# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Required provenance must select the public persistent VM before dispatch."""

import asyncio
import threading
import time
from contextlib import contextmanager
from copy import deepcopy

import pytest
from pyfly.kernel import ServiceUnavailableException

from flycanon.config import CanonSettings
from flycanon.core.agents.model_bindings import push_bindings, reset_bindings
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.actions import ReadRequiredFeedback
from flycanon.core.services.query.rlm.sandbox.executor import SandboxExecutor
from flycanon.core.services.query.rlm.sandbox.monty_executor import ExecutionTreeBudget, MontyExecutor
from flycanon.core.services.query.rlm.session import RLMSession
from flycanon.web.conventions.context import TenantContext, set_tenant_context


class Client:
    action_protocol = "function_tools"

    def __init__(self, codes=None):
        self.calls = 0
        self.codes = codes or ["final('unqualified')"]
        self.messages = []
        self.systems = []
        self.completions = 0

    def chat_raw(self, *args, **kwargs):
        self.calls += 1
        self.messages.append(deepcopy(args[0]))
        self.systems.append(args[1])
        return {"content": [{"type": "tool_use", "id": f"actual-call-{self.calls}", "name": "python",
                             "input": {"code": self.codes[min(self.calls - 1, len(self.codes) - 1)]}}]}

    def complete(self, prompt):
        self.completions += 1
        return "crosscheck"


class Observer:
    async def authorize(self):
        pass

    def document_sync(self, *args):
        pass

    def document_tool_start(self, scope):
        pass

    def document_tool(self, receipt, scope):
        pass


@contextmanager
def required_scope(observer=None):
    context = set_tenant_context(TenantContext(
        tenant_id="fixture", workspace_id="workspace", actor="owner", correlation_id="monty",
    ))
    token = push_bindings(
        tenant_id="fixture", workspace_id="workspace", subject="owner", bindings={}, required=True,
    )
    try:
        with provenance.observe(observer or Observer(), tenant_id="fixture", workspace_id="workspace", actor="owner"):
            provenance.current().source_ids.add("fixture")
            yield
    finally:
        reset_bindings(token)
        context.var.reset(context.token)


def test_product_default_execution_is_monty():
    assert CanonSettings().rlm_sandbox == "monty"
    assert RLMSession(Client()).sandbox_mode == "monty"


@pytest.mark.parametrize("value", ["", "typo"])
def test_unknown_execution_configuration_is_rejected(value):
    with pytest.raises(ValueError):
        CanonSettings(rlm_sandbox=value)


@pytest.mark.parametrize("mode", ["inprocess", "subprocess", "typo"])
@pytest.mark.parametrize("depth", [0, 1])
async def test_required_root_and_nested_never_dispatch_legacy_execution(monkeypatch, mode, depth):
    raw_calls = []

    def forbidden(*args, **kwargs):
        raw_calls.append(True)
        raise AssertionError("Raw CPython execution must not be selected")

    monkeypatch.setattr(RLMSession, "_exec", forbidden)
    monkeypatch.setattr(SandboxExecutor, "start", forbidden)
    client = Client()
    with required_scope(), pytest.raises(ServiceUnavailableException) as raised:
        await asyncio.to_thread(provenance.worker(
            RLMSession(client, depth=depth, max_iters=1, sandbox_mode=mode).run_over_text,
        ), "Inspect the supplied text", "fixture")
    assert raised.value.code == "RLM_SECURE_EXECUTION_REQUIRED"
    assert client.calls == 0 and raw_calls == []


class Documents:
    accessed = []

    def keys(self):
        return ["A"]

    def __getitem__(self, key):
        assert key == "A"
        return "Actual document text"

    def pages(self, key):
        return [self[key]]

    def npages(self, key):
        return 1

    def __contains__(self, key):
        return key == "A"


async def run_secure(client, *, docs=None, observer=None, **kwargs):
    session = RLMSession(client, sandbox_mode="monty", **kwargs)
    with required_scope(observer):
        operation = session.run if docs is not None else session.run_over_text
        return await asyncio.to_thread(provenance.worker(operation), "Inspect the source", docs or "source text")


async def test_real_vm_preserves_functions_variables_and_native_re_between_feeds():
    client = Client([
        "retained = 40\ndef add(value):\n    return retained + value\nprint(re.findall(r'\\d+', 'value42'))",
        "final(str(add(2)))",
    ])
    assert await run_secure(client, max_iters=2) == ("42", [], False)
    assert client.calls == 2 and "42" in client.messages[1][-1]["content"][0]["content"]


async def test_accepted_halt_never_executes_code_or_callbacks_after_final():
    client = Client(["final('accepted'); llm('must not run'); print('after final')"])
    assert await run_secure(client, max_iters=1) == ("accepted", [], False)
    assert client.calls == 1 and client.completions == 0


async def test_monty_cannot_return_unexecuted_plaintext_without_a_host_final():
    class Plaintext(Client):
        def chat_raw(self, *args, **kwargs):
            self.calls += 1
            return {"content": [{"type": "text", "text": "unexecuted plaintext"}]}

    client = Plaintext()
    with pytest.raises(ServiceUnavailableException):
        await run_secure(client, max_iters=1, sub_budget=0)
    assert client.calls == 1


@pytest.mark.parametrize("depth", [0, 1])
async def test_required_corpus_final_requires_this_sessions_content_read_at_every_depth(depth):
    client = Client(["final('unread', filings=['A'])"])
    with pytest.raises(ServiceUnavailableException):
        await run_secure(client, docs=Documents(), max_iters=1, depth=depth)
    assert client.calls == 1


@pytest.mark.parametrize("nested", [False, True])
async def test_shared_tree_rechecks_deadline_after_nested_model_authorization(monkeypatch, nested):
    trees = []
    original = ExecutionTreeBudget.__init__

    def record(tree, *args):
        original(tree, *args)
        trees.append(tree)

    monkeypatch.setattr(ExecutionTreeBudget, "__init__", record)

    class ExpireObserver(Observer):
        roots = 0

        def document_sync(self, stage, *args):
            self.roots += stage == "rlm.root"
            if stage == "rlm.submodel" or self.roots == 2:
                trees[0].deadline = time.monotonic() - 1

    client = Client(["rlm('nested', text)" if nested else "llm(text)", "final('must not run')"])
    with pytest.raises(ServiceUnavailableException):
        await run_secure(client, observer=ExpireObserver(), max_iters=2, max_depth=2, sub_budget=2)
    assert client.calls == 1 and client.completions == 0


async def test_nested_required_execution_uses_another_owned_public_vm_on_same_worker(monkeypatch):
    from pyfly.agentic.execution import MontyEnvironment

    original = MontyEnvironment.create_session
    owners = []

    def record(environment, **kwargs):
        owners.append(threading.current_thread())
        return original(environment, **kwargs)

    monkeypatch.setattr(MontyEnvironment, "create_session", record)
    client = Client(["answer = rlm('nested', text); final(answer)", "final('nested actual')"])
    assert await run_secure(client, max_iters=1, max_depth=2, sub_budget=1) == ("nested actual", [], False)
    assert len(owners) == 2 and owners[0] is owners[1] and owners[0] is not threading.current_thread()
    assert client.calls == 2 and client.completions == 0


async def test_authority_revoked_during_content_callback_prevents_guest_release(monkeypatch):
    output_bytes = []
    original = MontyExecutor.run_block

    def observe(executor, *args, **kwargs):
        try:
            return original(executor, *args, **kwargs)
        except ServiceUnavailableException:
            output_bytes.append(executor._session.usage.output_bytes)
            raise

    monkeypatch.setattr(MontyExecutor, "run_block", observe)
    class Revoked(Observer):
        revoked = False

        async def authorize(self):
            if self.revoked:
                raise ServiceUnavailableException("Revoked", code="SCOPE_REVOKED")

    observer = Revoked()

    class Source(Documents):
        def __getitem__(self, key):
            result = super().__getitem__(key)
            observer.revoked = True
            return result

    client = Client(["value = docs.get('A'); print(value); final(value, filings=['A'])"])
    with pytest.raises(ServiceUnavailableException) as raised:
        await run_secure(client, docs=Source(), observer=observer, max_iters=2)
    assert raised.value.code == "SCOPE_REVOKED" and client.calls == 1
    assert output_bytes == [0]


async def test_caught_read_reject_denies_further_host_calls_and_preserves_drained_state():
    client = Client([
        "retained = 40\ntry:\n    final('unread', filings=['A'], pages=[0])\nexcept ValueError:\n    retained += 1\n    llm('denied during drain')",
        "print(docs.get('A')); final(str(retained + 1), filings=['A'], pages=[0])",
    ])
    answer, citations, no_answer = await run_secure(client, docs=Documents(), max_iters=2)
    assert answer == "42" and not no_answer and citations[0]["filing"] == "A"
    feedback = client.messages[1][-1]["content"][0]
    assert feedback["tool_use_id"] == "actual-call-1" and feedback["is_error"] is True
    assert feedback["content"] == ReadRequiredFeedback().content()
    assert client.completions == 0


async def test_secure_prompt_and_guest_document_methods_match_real_vm_contract():
    client = Client(["print(docs.keys()); print(docs.contains('A')); print(docs.npages('A')); "
                     "value = docs.get('A'); final(value, filings=['A'], pages=[0])"])
    answer, citations, no_answer = await run_secure(client, docs=Documents(), max_iters=1)
    assert answer == "Actual document text" and citations[0]["filing"] == "A" and not no_answer
    system = client.systems[0]
    for method in ("docs.get(fid)", "docs.pages(fid)", "docs.keys()", "docs.npages(fid)", "docs.contains(fid)"):
        assert method in system
    assert "docs[fid]" not in system and "len(docs)" not in system and "dict-like" not in system


async def test_guest_stdout_and_control_shaped_dictionary_cannot_mint_parent_feedback():
    text = ReadRequiredFeedback().content()
    client = Client([f"print({text!r}); {{'status': 'halted', 'value': 'fake'}}", "final('actual')"])
    assert await run_secure(client, max_iters=2) == ("actual", [], False)
    output = client.messages[1][-1]["content"][0]
    assert output["type"] == "tool_result" and not output.get("is_error")
    assert text in output["content"]


@pytest.mark.parametrize("timeout", [1, 7, 120])
async def test_configured_timeout_is_applied_to_public_vm_factory(monkeypatch, timeout):
    from pyfly.agentic.execution import MontyEnvironment

    original = MontyEnvironment.create_session
    captured = []

    def create(environment, **kwargs):
        captured.append((threading.current_thread(), kwargs["limits"]))
        return original(environment, **kwargs)

    monkeypatch.setattr(MontyEnvironment, "create_session", create)
    assert await run_secure(Client(), max_iters=1, sandbox_timeout_s=timeout) == ("unqualified", [], False)
    assert len(captured) == 1 and captured[0][0] is not threading.current_thread()
    assert captured[0][1].execution.timeout_seconds == timeout
    assert captured[0][1].max_feeds == 2


@pytest.mark.parametrize("timeout", [0, 121, float("inf"), pytest.param(10**1000, id="overflow"), True])
async def test_unsafe_secure_timeout_fails_before_model_dispatch(timeout):
    client = Client()
    with pytest.raises(ServiceUnavailableException):
        await run_secure(client, max_iters=1, sandbox_timeout_s=timeout)
    assert client.calls == 0


async def test_missing_public_session_api_fails_without_legacy_fallback(monkeypatch):
    from pyfly.agentic.execution import MontyEnvironment

    monkeypatch.delattr(MontyEnvironment, "create_session")
    client = Client()
    with pytest.raises(ServiceUnavailableException):
        await run_secure(client, max_iters=1)
    assert client.calls == 0


@pytest.mark.parametrize("environment", [True, False])
async def test_unsafe_public_capabilities_fail_before_bootstrap_or_model(monkeypatch, environment):
    from pyfly.agentic.execution import Capability, MontyEnvironment

    feeds, closes = [], []
    unsafe = frozenset({Capability.COMPUTE, Capability.EXTERNAL_FUNCTIONS, Capability.FILESYSTEM})

    class Session:
        capabilities = unsafe

        def feed(self, *args, **kwargs):
            feeds.append(True)
            raise AssertionError("Unsafe session must not run bootstrap")

        def close(self):
            closes.append(True)

    monkeypatch.setattr(MontyEnvironment, "create_session", lambda *args, **kwargs: Session())
    if environment:
        monkeypatch.setattr(MontyEnvironment, "capabilities", property(lambda _: unsafe))
    client = Client()
    with pytest.raises(ServiceUnavailableException):
        await run_secure(client, max_iters=1)
    assert client.calls == 0 and feeds == []
    assert bool(closes) is not environment


def test_actual_vm_cannot_resume_with_a_host_object_callback_result():
    class HostObject:
        secret = "owned-host-only-secret"

    executor = MontyExecutor(functions={"host": HostObject}, authorize=lambda: None,
        tree=ExecutionTreeBudget(1, 0), max_iters=1, timeout=5, text="fixture")
    try:
        executor.start()
        result = executor.run_block("value = host(); print(value.secret)")
        assert not result.result.success and result.state == "broken"
        assert HostObject.secret not in result.result.stdout
    finally:
        executor.close()


async def test_expiry_after_root_authorization_prevents_model_dispatch(monkeypatch):
    original = ExecutionTreeBudget.model

    def expire(tree):
        tree.deadline = time.monotonic() - 1
        return original(tree)

    monkeypatch.setattr(ExecutionTreeBudget, "model", expire)
    client = Client()
    with pytest.raises(ServiceUnavailableException):
        await run_secure(client, max_iters=1)
    assert client.calls == 0


async def test_required_default_protocol_exhaustion_never_forces_another_model_call():
    client = Client(["print('not finished')"])
    with pytest.raises(ServiceUnavailableException):
        await run_secure(client, max_iters=1, sub_budget=0)
    assert client.calls == 1


async def test_late_valid_halt_is_preserved_and_never_replayed(monkeypatch):
    original = MontyExecutor.halt

    def late(executor, value):
        halt = original(executor, value)
        executor.tree.deadline = time.monotonic() - 1
        return halt

    monkeypatch.setattr(MontyExecutor, "halt", late)
    client = Client(["final('accepted'); llm('never')"])
    with pytest.raises(ServiceUnavailableException) as raised:
        await run_secure(client, max_iters=2)
    assert raised.value.__dict__["accepted_final"]["answer"] == "accepted"
    assert client.calls == 1 and client.completions == 0


async def test_late_read_rejection_retains_typed_feedback_but_cannot_continue(monkeypatch):
    original = MontyExecutor.reject_read

    def late(executor, message):
        reject = original(executor, message)
        executor.tree.deadline = time.monotonic() - 1
        return reject

    monkeypatch.setattr(MontyExecutor, "reject_read", late)
    client = Client(["final('unread', filings=['A'])"])
    with pytest.raises(ServiceUnavailableException) as raised:
        await run_secure(client, docs=Documents(), max_iters=2)
    assert any(feedback.code == "RLM_DOCUMENT_READ_REQUIRED"
               for feedback in raised.value.__dict__["execution_feedback"])
    assert client.calls == 1


@pytest.mark.parametrize("iterations,subcalls", [(0, 0), (129, 0), (1, -1), (1, 129), (True, 0)])
async def test_invalid_secure_tree_budgets_fail_before_dispatch(iterations, subcalls):
    client = Client()
    with pytest.raises(ServiceUnavailableException):
        await run_secure(client, max_iters=iterations, sub_budget=subcalls)
    assert client.calls == 0


@pytest.mark.parametrize("capability", ["file", "environment", "network"])
def test_real_vm_denies_ambient_host_capabilities(tmp_path, monkeypatch, capability):
    import socket

    secret = "owned-monty-secret-731"
    path = tmp_path / "owned-secret.txt"
    path.write_text(secret)
    monkeypatch.setenv("KOINON_MONTY_TEST_SECRET", secret)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(0.05)
    port = listener.getsockname()[1]
    code = {
        "file": f"open({str(path)!r}).read()",
        "environment": "import os\nos.getenv('KOINON_MONTY_TEST_SECRET')",
        "network": f"import socket\nsocket.create_connection(('127.0.0.1', {port}))",
    }[capability]
    executor = MontyExecutor(functions={}, authorize=lambda: None, tree=ExecutionTreeBudget(2, 0),
                             max_iters=2, timeout=5, text="fixture")
    try:
        executor.start()
        result = executor.run_block(code)
        assert not result.result.success
        assert secret not in str(result.result.output) + result.result.stdout
        with pytest.raises(TimeoutError):
            listener.accept()
    finally:
        executor.close()
        listener.close()


def test_closed_product_executor_cannot_replace_its_vm():
    executor = MontyExecutor(functions={}, authorize=lambda: None, tree=ExecutionTreeBudget(2, 0),
                             max_iters=2, timeout=5, text="fixture")
    try:
        executor.start()
        executor.close()
        with pytest.raises(ServiceUnavailableException):
            executor.start()
    finally:
        executor.close()


def test_authority_that_returns_after_tree_expiry_cannot_start_host_body():
    tree = ExecutionTreeBudget(2, 0)
    calls = []

    def late_authority():
        tree.deadline = time.monotonic() - 1

    executor = MontyExecutor(functions={"touch": lambda: calls.append(True)},
                             authorize=late_authority, tree=tree, max_iters=2, timeout=5, text="fixture")
    try:
        executor.start()
        with pytest.raises(ServiceUnavailableException):
            executor.run_block("touch()")
        assert calls == []
    finally:
        executor.close()


@pytest.mark.parametrize("halted", [True, False])
async def test_public_terminal_cleanup_or_rejection_result_never_restarts_model(monkeypatch, halted):
    from pyfly.agentic.execution import (
        Capability,
        ExecutionFeedback,
        ExecutionFeedResult,
        ExecutionFeedStatus,
        ExecutionResult,
        ExecutionSessionState,
        ExecutionSessionUsage,
        MontyEnvironment,
    )

    class Session:
        capabilities = frozenset({Capability.COMPUTE, Capability.EXTERNAL_FUNCTIONS})
        feeds = 0
        closes = 0

        def feed(self, code, *, inputs=None):
            self.feeds += 1
            if self.feeds == 1:
                status, state, result, feedback = (ExecutionFeedStatus.COMPLETED,
                    ExecutionSessionState.READY, ExecutionResult(success=True), ())
            elif halted:
                status, state, result, feedback = (ExecutionFeedStatus.HALTED,
                    ExecutionSessionState.BROKEN, ExecutionResult(success=False,
                        output={"answer": "accepted", "citations": [], "no_answer": False},
                        error_type="ExecutionCleanupError"), ())
            else:
                status, state, result, feedback = (ExecutionFeedStatus.ERROR,
                    ExecutionSessionState.BROKEN, ExecutionResult(success=False), (
                        ExecutionFeedback("RLM_DOCUMENT_READ_REQUIRED", ReadRequiredFeedback().content(), "final", 1),))
            return ExecutionFeedResult(status, result, state, feedback,
                ExecutionSessionUsage(self.feeds, 0, 0, 0, 0.0))

        def close(self):
            self.closes += 1

    session = Session()
    monkeypatch.setattr(MontyEnvironment, "create_session", lambda *args, **kwargs: session)
    client = Client()
    with pytest.raises(ServiceUnavailableException) as raised:
        await run_secure(client, max_iters=2)
    assert client.calls == 1 and session.feeds == 2 and session.closes >= 1
    if halted:
        assert raised.value.__dict__["accepted_final"]["answer"] == "accepted"
    else:
        assert raised.value.__dict__["execution_feedback"][0].code == "RLM_DOCUMENT_READ_REQUIRED"


@pytest.mark.parametrize("answer", ["", " \t\r\n"])
@pytest.mark.parametrize("depth", [0, 1])
@pytest.mark.parametrize("found", [True, False])
async def test_secure_blank_final_is_rejected_and_same_vm_can_finish(answer, depth, found):
    client = Client([
        f"retained = 40; final({answer!r}, found={found!r})",
        "final(str(retained + 2))",
    ])
    assert await run_secure(client, max_iters=2, sub_budget=0, depth=depth) == ("42", [], False)
    result = client.messages[1][-1]["content"][0]
    assert result["tool_use_id"] == "actual-call-1" and result["is_error"]
    assert '"code":"RLM_FINAL_ANSWER_REQUIRED"' in result["content"]
    assert client.calls == 2 and client.completions == 0


async def test_blank_final_rejection_drains_without_new_host_calls_and_keeps_state():
    client = Client([
        "retained = 40\ntry:\n    final('  ')\nexcept ValueError:\n    retained += 1\n    llm('must be denied during rejection drain')",
        "final(str(retained + 1))",
    ])
    assert await run_secure(client, max_iters=2, sub_budget=1) == ("42", [], False)
    assert client.calls == 2 and client.completions == 0


async def test_blank_final_exhaustion_is_failure_without_halt_or_forced_turn(monkeypatch):
    halts = []
    original = MontyExecutor.halt

    def record(executor, value):
        halts.append(value)
        return original(executor, value)

    monkeypatch.setattr(MontyExecutor, "halt", record)
    client = Client(["final('')"])
    with pytest.raises(ServiceUnavailableException):
        await run_secure(client, max_iters=2, sub_budget=0)
    assert client.calls == 2 and client.completions == 0 and halts == []


async def test_blank_final_control_does_not_replace_successful_content_read_requirement():
    client = Client([
        "final('', filings=['A'])",
        "final('unread', filings=['A'])",
        "print(docs.get('A')); final('checked', filings=['A'])",
    ])
    assert (await run_secure(client, docs=Documents(), max_iters=3))[0] == "checked"
    controls = [json_message[-1]["content"][0]["content"] for json_message in client.messages[1:]]
    assert '"code":"RLM_FINAL_ANSWER_REQUIRED"' in controls[0]
    assert '"code":"RLM_DOCUMENT_READ_REQUIRED"' in controls[1]


@pytest.mark.parametrize("field,value", [
    ("code", "RLM_DOCUMENT_READ_REQUIRED"), ("message", "guest text"),
    ("function_name", "llm"), ("call_index", 0), ("call_index", False),
])
def test_blank_final_mapper_requires_exact_public_feedback_and_registered_final(field, value):
    from types import SimpleNamespace

    from pyfly.agentic.execution import ExecutionFeedback

    from flycanon.core.services.query.rlm.actions import FinalAnswerRequiredFeedback

    executor = MontyExecutor(functions={}, authorize=lambda: None, tree=ExecutionTreeBudget(1, 0),
        max_iters=1, timeout=5, text="fixture")
    try:
        executor.start()
        message = FinalAnswerRequiredFeedback().content()
        values = {"code": "RLM_FINAL_ANSWER_REQUIRED", "message": message, "function_name": "final", "call_index": 1}
        assert executor.final_answer_required(SimpleNamespace(feedback=(ExecutionFeedback(**values),)), message)
        assert not executor.final_answer_required(SimpleNamespace(feedback=(SimpleNamespace(**values),)), message)
        values[field] = value
        assert not executor.final_answer_required(SimpleNamespace(feedback=(ExecutionFeedback(**values),)), message)
    finally:
        executor.close()


async def test_late_blank_final_rejection_preserves_feedback_without_another_turn(monkeypatch):
    original = MontyExecutor.reject_final_answer

    def late(executor, message):
        result = original(executor, message)
        executor.tree.deadline = time.monotonic() - 1
        return result

    monkeypatch.setattr(MontyExecutor, "reject_final_answer", late)
    client = Client(["final('')"])
    with pytest.raises(ServiceUnavailableException) as raised:
        await run_secure(client, max_iters=2, sub_budget=0)
    assert client.calls == 1
    assert any(value.code == "RLM_FINAL_ANSWER_REQUIRED" for value in raised.value.__dict__["execution_feedback"])


@pytest.mark.parametrize("answer", ["", " \t"])
async def test_explicit_standalone_legacy_blank_final_behavior_is_preserved(answer):
    result = RLMSession(Client([f"final({answer!r})"]), max_iters=1, sandbox_mode="inprocess").run_over_text("q", "text")
    assert result == (answer, [], False)


@pytest.mark.parametrize("nested,expected_hash", [
    (False, "fa28a1a0a6e16a1228c7c9459e3873bc0c5a7bc9716b7a1a703432ec1a68eaab"),
    (True, "da44ff4106743d5956c13cf7d0a4ac62a515551b5df1fabec2d1988963993a72"),
])
def test_extraction_workflow_does_not_change_explicit_legacy_prompts(nested, expected_hash):
    from hashlib import sha256

    client = Client(["final('unchanged')"])
    session = RLMSession(client, max_iters=1, sub_budget=0, sandbox_mode="inprocess")
    result = session.run_over_text("q", "text") if nested else session.run("q", Documents())
    assert result == ("unchanged", [], False) and client.calls == 1
    assert sha256(client.systems[0].encode()).hexdigest() == expected_hash
    assert "When extraction depends on wording or layout" not in client.systems[0]
