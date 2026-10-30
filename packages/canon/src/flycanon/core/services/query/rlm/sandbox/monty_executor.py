# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product-owned admission around the public synchronous persistent VM."""

from __future__ import annotations

import importlib
import json
import math
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from pyfly.kernel import ForbiddenException, ServiceUnavailableException

if TYPE_CHECKING:
    from pyfly.agentic.execution import ExecutionFeedResult, ExecutionSession


def unavailable(message="Required provenance needs an available, safely configured Monty execution session"):
    return ServiceUnavailableException(message, code="RLM_SECURE_EXECUTION_REQUIRED")


class ExecutionTreeBudget:
    """One candidate's admission budget, shared with its synchronous descendants."""

    def __init__(self, max_iters: int, sub_budget: int):
        if (type(max_iters) is not int or not 1 <= max_iters <= 128
                or type(sub_budget) is not int or not 0 <= sub_budget <= 128):
            raise unavailable("Secure execution tree budgets must have finite supported bounds")
        self.owner = threading.current_thread()
        self.deadline = time.monotonic() + 300.0
        self.max_models = max_iters + sub_budget
        self.models = 0
        self.callbacks = 0

    def check(self):
        if threading.current_thread() is not self.owner or time.monotonic() >= self.deadline:
            raise unavailable("The execution tree owner or lifetime admission has ended")

    def remaining(self):
        self.check()
        return self.deadline - time.monotonic()

    def expired(self):
        return time.monotonic() >= self.deadline

    def model(self):
        self.check()
        if self.models >= self.max_models:
            raise unavailable("The execution tree model-call budget is exhausted")
        self.models += 1

    def callback(self):
        self.check()
        if self.callbacks >= 256:
            raise unavailable("The execution tree callback budget is exhausted")
        self.callbacks += 1


_DOCS_BOOTSTRAP = """import re
class _Docs:
    def keys(self):
        return docs_keys()
    def get(self, key):
        return docs_getitem(key)
    def pages(self, key):
        return docs_pages(key)
    def npages(self, key):
        return docs_npages(key)
    def contains(self, key):
        return docs_contains(key)
docs = _Docs()
"""

_TERMINAL_CALLBACK = "_koinon_terminal_answer"
_TERMINAL_SOURCE = _TERMINAL_CALLBACK + "()"


class MontyExecutor:
    """No raw runner, host object, asynchronous bridge, or replacement VM exists here."""

    def __init__(
        self, *, functions: dict[str, Callable[..., Any]], authorize: Callable[[], None],
        tree: ExecutionTreeBudget, max_iters: int, timeout: float, text: str | None = None,
    ):
        if type(timeout) not in (int, float) or not 1 <= timeout <= 120 or not math.isfinite(timeout):
            raise unavailable("Secure VM timeout must be finite and between 1 and 120 seconds")
        self.tree, self.timeout, self.max_iters, self.text = tree, timeout, max_iters, text
        self.functions, self.authorize = dict(functions), authorize
        self._session: ExecutionSession | None = None
        self._api: Any = None
        self._fatal: Exception | None = None
        self._started = False
        self._pending_terminal: str | None = None
        self._terminal_invoked = False
        self._terminal_result: Any = None
        self._terminal_feed = None
        self.last_feed = None

    def start(self):
        if self._started:
            raise unavailable("An execution session cannot be reopened or replaced")
        self._started = True
        self.tree.check()
        try:
            api = importlib.import_module("pyfly.agentic.execution")
            for name in (
                "MontyEnvironment", "ExecutionSessionLimits", "ExecutionLimits", "ExecutionHalt",
                "ExecutionReject", "ExecutionFeedback", "ExecutionFeedStatus", "ExecutionSessionState",
            ):
                if not hasattr(api, name):
                    raise ImportError("Public persistent execution API is unavailable")
            self._api = api
            environment = api.MontyEnvironment(type_check=False)
            expected = frozenset({api.Capability.COMPUTE, api.Capability.EXTERNAL_FUNCTIONS})
            if environment.capabilities != expected:
                raise unavailable("Secure execution cannot grant filesystem or network capabilities")
            limits = api.ExecutionSessionLimits(
                execution=api.ExecutionLimits(
                    timeout_seconds=float(self.timeout), max_memory_bytes=64 * 1024**2,
                    max_recursion_depth=200,
                ),
                max_session_seconds=min(300.0, self.tree.remaining()), max_feeds=self.max_iters + 1,
                max_external_calls=256, max_suspensions=4096, max_output_bytes=1024**2,
                max_value_bytes=8 * 1024**2,
            )
            if _TERMINAL_CALLBACK in self.functions:
                raise unavailable("A reserved terminal callback cannot be supplied")
            functions = {name: self._guarded(function, name) for name, function in self.functions.items()}
            functions[_TERMINAL_CALLBACK] = self._guarded(self._finish_terminal, _TERMINAL_CALLBACK)
            session = cast(
                "ExecutionSession", environment.create_session(external_functions=functions, limits=limits),
            )
            self._session = session
            if session.capabilities != expected:
                raise unavailable("The execution session capabilities changed")
            bootstrap = _DOCS_BOOTSTRAP if self.text is None else "import re\n"
            result = self.run_block(bootstrap, inputs={"text": self.text} if self.text is not None else None)
            if (result.status != api.ExecutionFeedStatus.COMPLETED or not result.result.success
                    or result.state != api.ExecutionSessionState.READY):
                raise unavailable("The secure execution bootstrap did not complete")
        except BaseException as error:
            self.close()
            if isinstance(error, KeyboardInterrupt | SystemExit):
                raise
            if isinstance(error, ServiceUnavailableException):
                raise
            raise unavailable() from error

    def _guarded(self, function, name):
        def invoke(*args, **kwargs):
            try:
                self.tree.callback()
                self.authorize()
                self.tree.check()
                if ((self._pending_terminal is not None and name != _TERMINAL_CALLBACK)
                        or self._pending_terminal is None and name == _TERMINAL_CALLBACK):
                    raise unavailable("The terminal callback phase does not admit this operation")
            except Exception as error:
                self._fatal = error
                return self._api.ExecutionReject(
                    "RLM_EXECUTION_UNAVAILABLE", "Execution authority has ended.",
                )
            try:
                result = function(*args, **kwargs)
                if type(result) in (self._api.ExecutionHalt, self._api.ExecutionReject):
                    return result
                self.authorize()
                self.tree.check()
                return result
            except (ForbiddenException, ServiceUnavailableException) as error:
                self._fatal = error
                return self._api.ExecutionReject("RLM_EXECUTION_UNAVAILABLE", "Execution cannot continue.")
        return invoke

    def _finish_terminal(self):
        if self._pending_terminal is None or self._terminal_invoked:
            raise unavailable("A terminal payload can only be consumed once")
        self._terminal_invoked = True
        self._terminal_result = self.functions["final"](**json.loads(self._pending_terminal))
        return self._terminal_result

    def run_terminal(self, payload):
        self.tree.check()
        if self._pending_terminal is not None:
            raise unavailable("A terminal feed is already active")
        self._pending_terminal = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        self._terminal_invoked = False
        self._terminal_result = None
        try:
            result = self.run_block(_TERMINAL_SOURCE)
            self._terminal_feed = result
            if not self._terminal_invoked or type(self._terminal_result) not in (
                self._api.ExecutionHalt, self._api.ExecutionReject,
            ):
                self.close()
                raise unavailable("The terminal feed did not invoke the admitted final callback")
            if type(self._terminal_result) is self._api.ExecutionHalt and (
                result.status != self._api.ExecutionFeedStatus.HALTED
                or result.result.output != self._terminal_result.value
            ):
                self.close()
                raise unavailable("The terminal feed did not preserve its accepted outcome")
            return result
        finally:
            self._pending_terminal = None
            self._terminal_result = None

    def halt(self, value):
        return self._api.ExecutionHalt(value)

    def reject_read(self, message):
        return self._api.ExecutionReject("RLM_DOCUMENT_READ_REQUIRED", message)

    def reject_final_answer(self, message):
        return self._api.ExecutionReject("RLM_FINAL_ANSWER_REQUIRED", message)

    def read_required(self, result, message):
        return any(
            type(feedback) is self._api.ExecutionFeedback
            and feedback.code == "RLM_DOCUMENT_READ_REQUIRED"
            and feedback.function_name == (_TERMINAL_CALLBACK if result is self._terminal_feed else "final")
            and type(feedback.call_index) is int and feedback.call_index > 0 and feedback.message == message
            for feedback in result.feedback
        )

    def final_answer_required(self, result, message):
        return any(
            type(feedback) is self._api.ExecutionFeedback
            and feedback.code == "RLM_FINAL_ANSWER_REQUIRED"
            and feedback.function_name == (_TERMINAL_CALLBACK if result is self._terminal_feed else "final")
            and type(feedback.call_index) is int and feedback.call_index > 0 and feedback.message == message
            for feedback in result.feedback
        )

    def run_block(self, code: str, *, inputs=None) -> ExecutionFeedResult:
        self.tree.check()
        if self._session is None:
            raise unavailable("The execution session is not open")
        result = self._session.feed(code, inputs=inputs)
        self.last_feed = result
        if self._fatal is not None:
            self._fatal.__dict__["execution_feedback"] = result.feedback
            self.close()
            raise self._fatal
        if result.status != self._api.ExecutionFeedStatus.HALTED:
            try:
                self.tree.check()
            except BaseException as error:
                if isinstance(error, Exception):
                    error.__dict__["execution_feedback"] = result.feedback
                self.close()
                raise
        return result

    def close(self):
        self._pending_terminal = None
        self._terminal_result = None
        if self._session is not None:
            self._session.close()
