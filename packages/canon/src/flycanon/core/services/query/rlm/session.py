# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The Recursive Language Model engine: a CodeAct REPL over context-as-a-variable.

Faithful to alexzhang13/rlm's mechanism (adapted to flycanon):

* The orchestrator LM runs a loop (up to ``max_iters``). Each turn it emits a
  ``python`` tool call; we ``exec`` it in a persistent, **restricted** namespace
  and feed the captured stdout back as the next user turn.
* The corpus is the variable ``docs`` -- the model inspects it with code instead
  of reading it in the prompt. From inside the code it can make **recursive
  sub-calls**: ``llm(prompt)`` (a flat sub-LM call on a chunk) and
  ``rlm(question, text)`` (a nested REPL over a slice, depth-limited -- at
  ``max_depth`` it degrades to ``llm``).
* The loop stops when a code block calls
  ``final(answer, filings=..., pages=..., found=...)``; ``found=False`` flags a
  structured no-answer that flows out of the loop as the third return value.

Required provenance uses the public persistent Monty VM and explicit data-only
host callbacks. Standalone callers may select the legacy CPython runners, whose
restricted namespace/resource controls are not an execution-isolation boundary.

The engine is **corpus-agnostic**: ``docs`` is duck-typed via the
:class:`DocCorpus` protocol, so no concrete document store is imported here.
It is **provider-agnostic** the same way: ``client`` is an
:class:`~flycanon.core.services.query.rlm.chat.RlmChatClient`, so the loop
below is written once and runs against Anthropic or Azure OpenAI depending
only on what ``FLYCANON_RLM_ROOT_MODEL`` names. The content-block vocabulary
this loop speaks -- ``text`` / ``tool_use`` blocks out, ``tool_result``
blocks back in -- is Anthropic's, and the Azure client translates to and
from it; see :mod:`flycanon.core.services.query.rlm.chat` for why that
direction was chosen.
"""

from __future__ import annotations

import io
import logging
import re
import traceback
from collections.abc import Callable
from contextlib import redirect_stdout, suppress
from typing import Any, Protocol, cast, runtime_checkable

from flycanon.core.agents.model_bindings import current_scope
from flycanon.core.services.query.rlm.actions import FinalAnswerRequiredFeedback, ReadRequiredFeedback
from flycanon.core.services.query.rlm.chat import RlmChatClient
from flycanon.core.services.query.rlm.native_client import NativeRlmChatClient, RlmToolProtocolError
from flycanon.core.services.query.rlm.safe_builtins import _SAFE_BUILTINS
from flycanon.core.services.query.rlm.sandbox.executor import BlockResult, SandboxExecutor
from flycanon.core.services.query.rlm.sandbox.monty_executor import (
    ExecutionTreeBudget,
    MontyExecutor,
    unavailable,
)


@runtime_checkable
class DocCorpus(Protocol):
    """Duck-typed document store the REPL inspects with code.

    The concrete implementation (``CanonDocStore``) arrives in a later PR; the
    engine only relies on this dict-like surface plus page accessors.
    """

    def keys(self) -> list[str]: ...

    def __getitem__(self, key: str) -> str: ...

    def __contains__(self, key: object) -> bool: ...

    def pages(self, key: str) -> list[str]: ...

    def npages(self, key: str) -> int: ...


class _ContentReads:
    """Per-run successful content releases, separate from shared corpus/citation state."""

    def __init__(self, docs: DocCorpus, *, enforce: bool):
        self._docs = docs
        self._enforce = enforce
        self._released: set[str] = set()

    @property
    def read(self):
        return bool(self._released)

    def admits(self, filings):
        if not self._enforce:
            return True
        if not self._released:
            return False
        if filings is None:
            return True
        if isinstance(filings, str):
            filings = [filings]
        return isinstance(filings, (list, tuple)) and all(
            isinstance(key, str) and key in self._released for key in filings
        )

    @property
    def accessed(self):
        return getattr(self._docs, "accessed", [])

    def keys(self):
        return list(self._docs.keys())

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def __contains__(self, key):
        return key in self._docs

    def __getitem__(self, key):
        release = getattr(self._docs, "_execution_read", None)
        content = release(key, as_pages=False) if callable(release) else self._docs[key]
        self._released.add(key)
        return content

    def pages(self, key):
        release = getattr(self._docs, "_execution_read", None)
        pages = release(key, as_pages=True) if callable(release) else self._docs.pages(key)
        self._released.add(key)
        return pages

    def npages(self, key):
        return self._docs.npages(key)


class _ContentReadRequired(ValueError):
    pass


# The single tool the orchestrator drives: a persistent Python REPL. Claude emits
# native tool-use blocks for this rather than markdown code fences, so execution
# is reliable.
_PY_TOOL = [
    {
        "name": "python",
        "description": "Execute Python in the persistent REPL and return its stdout. The "
        "namespace has `docs`, `re`, `llm`, `rlm`, `final`. "
        "Use the existing helpers directly; imports, files, and network access are unavailable. Call "
        "`final(answer, filings=[...], pages=[...], found=True)` from code to finish; "
        "pass `found=False` when the documents do not contain the answer.",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python source to execute"}},
            "required": ["code"],
        },
    }
]

_MONTY_TOOL = [{
    **_PY_TOOL[0],
    "description": (
        "Execute the Monty Python subset with native re and the supplied docs, llm, rlm, and final helpers. "
        "Use docs.get(fid), docs.pages(fid), and docs.keys(); "
        "host files, environment, and network are unavailable. "
        "Finish with final(answer, filings=[...], pages=[...], found=True)."
    ),
}]

# ---------------------------------------------------------------------------
# restricted exec sandbox
# ---------------------------------------------------------------------------
# ``_SAFE_BUILTIN_NAMES`` / ``_SAFE_BUILTINS`` live in the dependency-free
# ``safe_builtins`` leaf module so the out-of-process sandbox child shares the
# exact same whitelist without importing this engine's ``httpx``/config stack.
_MAX_STDOUT = 4000  # truncate each turn's printed output fed back to the model

# How much model-written code / REPL stdout to keep on each DEBUG trace line.
_TRACE_CHARS = 1500

logger = logging.getLogger(__name__)
# Cap on cited page text. A dense 10-K page is ~3-5k chars; this keeps the
# whole page the model read (structure intact) rather than a tiny prefix.
_CITATION_CONTENT_CHARS = 4000


class _Final(Exception):
    def __init__(self, answer: str, citations: list[dict], no_answer: bool = False):
        self.answer, self.citations, self.no_answer = answer, citations, no_answer


_WORD = re.compile(r"[a-zA-Z][a-zA-Z']+")


def _best_page(question: str, pages: list[str]) -> int:
    """Deterministic keyword-best page -- used to give the judge a real evidence
    page when the model cites a filing without a specific page."""
    q = {w.lower() for w in _WORD.findall(question) if len(w) > 2}
    if not pages:
        return 0
    return max(
        range(len(pages)),
        key=lambda i: len(q & {w.lower() for w in _WORD.findall(pages[i])}),
    )


SYSTEM = """\
You are a Recursive Language Model solving a question about a document corpus by
writing Python in a REPL. You do NOT see the documents in this prompt -- they are
the variable `docs`, which you inspect with code.

Environment (persists across turns):
- `docs`: dict-like over the corpus. `docs.keys()` -> document ids. `docs[fid]` ->
  full document text. `docs.pages(fid)` -> list of page strings.
  `docs.npages(fid)` -> page count.
- `llm(prompt: str) -> str`: a sub-LM call. Use it to extract/compute from a chunk
  you pass in (e.g. a statement page) when reading is easier delegated.
- `rlm(question: str, text: str) -> str`: a recursive sub-call that itself reasons
  over a large `text`. Use for big sections you want decomposed.
- `re` is available. `final(answer, filings=[...], pages=[...])`: call this to
  finish, citing the document id(s) and page number(s) you used.

Rules:
- Imports are disabled. `re` and the helpers above are already available; do not
  run `import re` or try to load modules, files, or network clients.
- Use the `python` tool to run code; its stdout is returned to you. Call it
  repeatedly, building on the persistent namespace.
- Strategy: find the right document from `docs.keys()` (match the entity in the
  question), read the relevant pages (search the text for the figure), extract the
  answer, then call `final(...)`. Print intermediate findings so you can see them.
  Keep printed output small (slice/grep; don't print whole documents).
- Treat sub-model output as secondary assistance, not source data. Check its
  claims against `docs` before using them. Calculate from figures read directly
  from the original text; list numbers and explanatory examples are not data.
- `print()` output shown back to you is truncated to ~4000 characters for DISPLAY
  ONLY -- a long string in a variable is kept in full even when its printout looks
  cut off. So if your answer is already complete in a variable, do NOT decide it was
  "cut off" and re-`print` it, re-ask the sub-`llm`, or "reassemble" it; the variable
  holds the full text -- pass it straight to `final(...)`.
- Verifying your facts IS required before you finish: confirm every benchmark,
  threshold, or computed figure against the actual document text (grep the page for
  it). NEVER state a benchmark or target you have not found in the documents -- if the
  documents do not give one, say so explicitly instead of inventing a number, and in
  particular never assume the benchmark equals the figure you were asked to evaluate.
  This is about correctness; it is NOT a licence to re-fetch an answer you already
  hold in full just because its printout looked truncated.
- Always finish by calling `final(...)`. If the evidence is not present, call
  `final('the documents do not contain this', filings=[...], found=False)`."""

_NESTED_SYSTEM = """\
You are a recursive sub-model answering a question over a text passage held in the
variable `text` (a string). Inspect it with the `python` tool. Helpers: `llm(prompt)`,
`re`, `print`, and `final(answer)` to finish. Its stdout returns to you. Imports are
disabled; use the supplied `re` and helpers without importing modules. Read figures
directly from `text` and verify sub-model summaries against it. Extract the answer,
then call `final(...)`. If the evidence is not present, call
`final('the documents do not contain this', found=False)`."""

_NATIVE_SYSTEM = SYSTEM.replace("Use the `python` tool", "Use the configured action protocol").replace(
    "- Always finish by calling `final(...)`. If the evidence is not present, call\n"
    "  `final('the documents do not contain this', filings=[...], found=False)`.",
    "- Finish with final only after examining the original evidence. Use found=False only\n"
    "  when that examination genuinely did not locate an answer; an unexecuted read is not absence.",
) + """

Completion contract:
- `final(answer, filings=None, pages=None, found=True)` requires answer text as its
  first argument. `filings` is a list of actual document ids from `docs.keys()`,
  not extracted facts. `pages` is a corresponding list of zero-based integer page
  indexes, not page text. `found=False` reports that evidence was not found.
- Read original document contents before any positive or negative corpus conclusion.
  Listing ids, checking metadata, or encountering an execution error does not show
  that the documents lack the answer. Verify source facts before finalizing.
"""

_NATIVE_NESTED_SYSTEM = _NESTED_SYSTEM.replace(
    "with the `python` tool", "using the configured action protocol"
).replace(
    "then call `final(...)`. If the evidence is not present, call\n"
    "`final('the documents do not contain this', found=False)`.",
    "then finish with final. Choose found=False only after examining the supplied text\n"
    "and genuinely failing to find the answer.",
)

_MONTY_DOCS = """- `docs` is a guest helper. `docs.keys()` returns actual document ids.
  `docs.get(fid)` returns full document text; `docs.pages(fid)` returns page strings.
  `docs.npages(fid)` returns the page count; `docs.contains(fid)` checks an id.
  Iterate `docs.keys()` and use `len(docs.keys())` for the document count."""


def _monty_system(system, *, documents):
    system = system.replace(
        "- Imports are disabled. `re` and the helpers above are already available; do not\n"
        "  run `import re` or try to load modules, files, or network clients.",
        "- Native `re` and the supplied helpers are already available. Host module\n"
        "  objects, files, environment, and network access are unavailable.",
    ).replace(
        "Its stdout returns to you. Imports are\ndisabled; "
        "use the supplied `re` and helpers without importing modules.",
        "Its stdout returns to you. Native `re` and the supplied helpers are already available.",
    ).replace(
        "- Always finish by calling `final(...)`. If the evidence is not present, call\n"
        "  `final('the documents do not contain this', filings=[...], found=False)`.",
        "- Finish with final after examining the source. Choose found=False only when\n"
        "  the inspected evidence genuinely does not answer the question.",
    )
    if documents:
        system = system.replace(
            "- `docs`: dict-like over the corpus. `docs.keys()` -> document ids. `docs[fid]` ->\n"
            "  full document text. `docs.pages(fid)` -> list of page strings.\n"
            "  `docs.npages(fid)` -> page count.", _MONTY_DOCS,
        )
    return system + "\nExecution uses Monty's Python subset. Native `re` and the supplied helpers are ready."


class RLMSession:
    """One root (or nested) CodeAct REPL run against a corpus or text slice."""

    def __init__(
        self,
        client: RlmChatClient,
        depth: int = 0,
        max_depth: int = 1,
        max_iters: int = 8,
        sub_budget: int = 12,
        on_turn: Callable[[int, list[str]], None] | None = None,
        sandbox_mode: str = "monty",
        sandbox_timeout_s: int = 30,
        corpus_context: str | None = None,
        _execution_tree: ExecutionTreeBudget | None = None,
    ):
        self.client = client
        self.depth, self.max_depth = depth, max_depth
        self.max_iters, self.sub_budget = max_iters, sub_budget
        self.sub_calls = 0
        self.turns = 0
        # Required scopes use the persistent VM. Explicit legacy modes are
        # standalone compatibility only and provide no isolation guarantee.
        self.sandbox_mode = sandbox_mode
        self.sandbox_timeout_s = sandbox_timeout_s
        self.corpus_context = corpus_context
        self._execution_tree = _execution_tree
        self._execution_scope = None
        # Optional per-turn progress hook. Fired from the (synchronous) REPL
        # worker thread after each orchestrator turn so a streaming caller can
        # surface live progress; ``None`` on the non-streaming path. A callback
        # error must never break the REPL, so the call site guards it.
        self.on_turn = on_turn

    # -- recursive helpers exposed into the sandbox --
    def _llm(self, prompt: str) -> str:
        if self._execution_tree is not None:
            self._execution_tree.check()
        if self.sub_calls >= self.sub_budget:
            return "[sub-call budget exhausted]"
        self.sub_calls += 1
        from flycanon.core.services.query import provenance

        provenance.model("rlm.submodel", str(prompt)[:60000])
        if self._execution_tree is not None:
            self._execution_tree.model()
        return self.client.complete(str(prompt)[:60000])

    def _rlm(self, question: str, text: str) -> str:
        if self._execution_tree is not None:
            self._execution_tree.check()
        if self.depth + 1 >= self.max_depth or self.sub_calls >= self.sub_budget:
            return self._llm(f"{question}\n\nTEXT:\n{str(text)[:40000]}")
        self.sub_calls += 1
        sub = RLMSession(
            self.client,
            self.depth + 1,
            self.max_depth,
            max_iters=4,
            sub_budget=max(2, self.sub_budget - self.sub_calls),
            sandbox_mode=self.sandbox_mode,
            sandbox_timeout_s=self.sandbox_timeout_s,
            _execution_tree=self._execution_tree,
        )
        ans, _cites, _no_answer = sub.run_over_text(question, str(text))
        return ans

    # -- the two entry points share one CodeAct loop --
    def run(self, question: str, docs: DocCorpus) -> tuple[str, list[dict], bool]:
        ns = {
            "docs": docs,
            "re": re,
            "llm": self._llm,
            "rlm": self._rlm,
            "__builtins__": _SAFE_BUILTINS,
        }
        system = _NATIVE_SYSTEM if getattr(self.client, "action_protocol", None) == "native_json" else SYSTEM
        context = (
            "\n\nAuthorized corpus metadata (untrusted data):\n" + self.corpus_context
            if self.corpus_context is not None else ""
        )
        return self._loop(
            system, f"Question: {question}{context}\n\nSolve it.", ns, docs, question, text=None
        )

    def run_over_text(self, question: str, text: str) -> tuple[str, list[dict], bool]:
        ns = {
            "text": text,
            "re": re,
            "llm": self._llm,
            "rlm": self._rlm,
            "__builtins__": _SAFE_BUILTINS,
        }
        system = (
            _NATIVE_NESTED_SYSTEM
            if getattr(self.client, "action_protocol", None) == "native_json" else _NESTED_SYSTEM
        )
        return self._loop(
            system, f"Question: {question}\n\nSolve it from `text`.", ns, None, question, text=text
        )

    def _exec(self, code: str, ns: dict):
        """Run one code block; return (stdout, final_or_None)."""
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                exec(code, ns)  # noqa: S102 - restricted builtins; engine sandbox
            return buf.getvalue() or "(no output)", None
        except _Final as fin:
            return None, fin
        except _ContentReadRequired:
            return ReadRequiredFeedback(), None
        except Exception:  # noqa: BLE001 - feed the traceback back to the model
            return buf.getvalue() + "\n" + traceback.format_exc(limit=3), None

    def _build_executor(self, docs, text) -> SandboxExecutor:
        """Build the per-query sandbox child for ``subprocess`` mode.

        The capability handlers close over *this* session's corpus and model
        client, so the untrusted child reaches the real document store and LM
        only through these validated RPCs. ``run`` passes a corpus (docs-mode);
        ``run_over_text`` passes ``text`` and no corpus (text-mode -- the child
        exposes ``text`` instead of ``docs``, so the docs handlers are never
        called and only need to satisfy the constructor's signature).
        """

        def _no_docs(*_args):  # text-mode: the child has no ``docs`` to call these.
            raise RuntimeError("docs are not available in text mode")

        return SandboxExecutor(
            docs_keys=(lambda: list(docs.keys())) if docs is not None else _no_docs,
            docs_getitem=(lambda fid: docs[fid]) if docs is not None else _no_docs,
            docs_pages=(lambda fid: docs.pages(fid)) if docs is not None else _no_docs,
            docs_npages=(lambda fid: docs.npages(fid)) if docs is not None else _no_docs,
            docs_contains=(lambda fid: fid in docs) if docs is not None else _no_docs,
            llm=self._llm,
            rlm=self._rlm,
            timeout=float(self.sandbox_timeout_s),
            text=text,
        )

    def _loop(self, system: str, first_user: str, ns: dict, docs, question, text):
        scope = current_scope()
        required = scope is not None and scope.required
        if required and self.sandbox_mode != "monty":
            raise unavailable("Required provenance cannot select legacy execution")
        if self.sandbox_mode not in {"monty", "inprocess", "subprocess"}:
            raise ValueError("Unknown RLM execution mode")
        if docs is not None and required:
            docs = _ContentReads(docs, enforce=True)
            ns["docs"] = docs

        if self.sandbox_mode == "monty":
            system = _monty_system(system, documents=docs is not None)
            self._execution_scope = scope if required else None
            if self._execution_tree is None:
                self._execution_tree = ExecutionTreeBudget(self.max_iters, self.sub_budget)
            self._authorize_execution()
            executor = self._build_monty(docs, text, question)
            try:
                executor.start()
                return self._run_loop(system, first_user, docs, question, executor)
            finally:
                executor.close()

        def final(answer, filings=None, pages=None, found=True):
            if isinstance(docs, _ContentReads) and not docs.admits(filings):
                raise _ContentReadRequired
            raise _Final(
                str(answer),
                self._citations(filings, pages, docs, question),
                no_answer=not found,
            )

        ns["final"] = final

        if self.sandbox_mode == "subprocess":
            executor = self._build_executor(docs, text)
            executor.start()
            try:
                return self._run_loop(system, first_user, docs, question, executor)
            finally:
                # Always reap the child -- on a normal return, an exception, or
                # an out-of-iters exit.
                executor.close()
        return self._run_loop(system, first_user, docs, question, ns)

    def _authorize_execution(self):
        from flycanon.core.services.query import provenance

        if self._execution_tree is not None:
            self._execution_tree.check()
        if self._execution_scope is not None and current_scope() is not self._execution_scope:
            raise unavailable("The admitted execution connection lifetime has ended")
        observation = provenance.current()
        if self._execution_scope is not None and observation is None:
            raise unavailable("Required execution provenance is unavailable")
        if observation is not None:
            with observation.lock:
                provenance.authority(observation)

    def _build_monty(self, docs, text, question):
        def document(key, operation):
            if docs is None:
                raise ValueError("docs are unavailable in text mode")
            if type(key) is not str:
                raise TypeError("A document identifier must be a string")
            return operation(key)

        def final(answer, filings=None, pages=None, found=True):
            if type(answer) is not str or type(found) is not bool:
                raise TypeError("final requires answer text and a boolean found value")
            if not answer.strip():
                return executor.reject_final_answer(FinalAnswerRequiredFeedback().content())
            if filings is not None and not (
                type(filings) is str or type(filings) in (list, tuple)
                and all(type(value) is str for value in filings)
            ):
                raise TypeError("filings must contain document identifiers")
            if pages is not None and not (
                type(pages) is int or type(pages) in (list, tuple)
                and all(value is None or type(value) is int for value in pages)
            ):
                raise TypeError("pages must contain integer indexes")
            if isinstance(docs, _ContentReads) and not docs.admits(filings):
                return executor.reject_read(ReadRequiredFeedback().content())
            citations = self._citations(filings, pages, docs, question)
            self._authorize_execution()
            return executor.halt({"answer": answer, "citations": citations, "no_answer": not found})

        functions = {
            "docs_keys": lambda: list(docs.keys()) if docs is not None else [],
            "docs_getitem": lambda key: document(key, lambda value: docs[value]),
            "docs_pages": lambda key: document(key, lambda value: docs.pages(value)),
            "docs_npages": lambda key: document(key, lambda value: docs.npages(value)),
            "docs_contains": lambda key: document(key, lambda value: value in docs),
            "llm": self._llm, "rlm": self._rlm, "final": final,
        }
        assert self._execution_tree is not None
        executor = MontyExecutor(
            functions=functions, authorize=self._authorize_execution, tree=self._execution_tree,
            max_iters=self.max_iters, timeout=self.sandbox_timeout_s, text=text,
        )
        return executor

    def _run_loop(self, system, first_user, docs, question, runner):
        """The shared CodeAct orchestration loop.

        ``runner`` is either the in-process exec namespace (``dict``) or a
        started :class:`SandboxExecutor`; ``_run_block`` dispatches on its type.
        """
        messages: list[dict[str, Any]] = [{"role": "user", "content": first_user}]
        dead_sandbox = False
        protocol_error = None
        native_json = getattr(self.client, "action_protocol", None) == "native_json"
        native_client = cast(NativeRlmChatClient, self.client) if native_json else None
        tools = _MONTY_TOOL if isinstance(runner, MontyExecutor) else _PY_TOOL
        for _ in range(self.max_iters):
            if self._execution_tree is not None:
                self._execution_tree.check()
            self.turns += 1
            logger.debug("rlm turn %d/%d starting", self.turns, self.max_iters)
            if self.on_turn is not None:
                # ``docs`` is the corpus on the root path (carries ``.accessed``)
                # and ``None`` on the nested-text path. A callback failure must
                # never break the REPL.
                with suppress(Exception):  # progress hook must not break the loop
                    self.on_turn(self.turns, list(docs.accessed) if docs is not None else [])
            from flycanon.core.services.query import provenance

            request = native_client.prepare_action(messages, system) if native_client else None
            provenance.model("rlm.root", request.manifest if request else repr((system, messages, tools)))
            if self._execution_tree is not None:
                self._execution_tree.model()
            try:
                resp = (
                    native_client.request_action(request) if native_client and request
                    else self.client.chat_raw(messages, system, tools)
                )
            except RlmToolProtocolError as error:
                protocol_error = error
                messages.append({
                    "role": "user",
                    "content": (
                        "Return only a JSON object with exactly one nonblank string field named code. "
                        "Do not return function calls, Markdown, or plain text."
                        if native_json else
                        "Call the actual python function tool with a nonblank string code argument. "
                        "Do not use Markdown, code fences, or plain text."
                    ),
                })
                continue
            content = resp.get("content", [])
            messages.append({"role": "assistant", "content": content})
            if logger.isEnabledFor(logging.DEBUG):
                reasoning = "".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
                if reasoning:
                    logger.debug("rlm turn %d reasoning: %s", self.turns, reasoning[:_TRACE_CHARS])
            tool_uses = [
                b for b in content if b.get("type") == ("python_action" if native_json else "tool_use")
            ]
            if not tool_uses:  # model answered in text without running code
                if isinstance(runner, MontyExecutor):
                    raise RlmToolProtocolError(
                        "Secure execution requires an actual code action and accepted final callback",
                        code="RLM_TOOL_PROTOCOL_REQUIRED",
                    )
                text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
                logger.debug(
                    "rlm turn %d answered in plain text without running code (len=%d)",
                    self.turns,
                    len(text.strip()),
                )
                # best-effort plain-text answer: not a structured no-answer.
                return text.strip(), self._citations(None, None, docs, question), False
            results = []
            for idx, tu in enumerate(tool_uses):
                code = tu["code"] if native_json else str(tu.get("input", {}).get("code", ""))
                logger.debug("rlm turn %d code[%d]: %s", self.turns, idx, code[:_TRACE_CHARS])
                stdout, fin = self._run_block(code, runner, docs, question)
                if fin is not None:
                    logger.debug(
                        "rlm turn %d called final() (found=%s, answer_len=%d)",
                        self.turns,
                        not fin.no_answer,
                        len(fin.answer),
                    )
                    return fin.answer, fin.citations, fin.no_answer
                # stdout is None only on the _Final path (returned above) or when
                # the sandbox child died: in that case stop running blocks -- the
                # executor is dead and another run_block would just return
                # TERMINATED again -- and fall through to the plain-text fallback
                # below, which uses the PARENT's client and works with no child.
                if stdout is None:
                    dead_sandbox = True
                    # The Messages API requires EVERY tool_use in the assistant
                    # turn to be answered by a tool_result in the next user
                    # message. The block that just died and any later blocks in
                    # this same turn are still unanswered -- emit an error
                    # tool_result for each so the transcript stays well-formed
                    # for the fallback chat_raw below.
                    for dangling in tool_uses[idx:]:
                        results.append(
                            {
                                "type": "action_result" if native_json else "tool_result",
                                "action_id" if native_json else "tool_use_id":
                                    dangling["action_id"] if native_json else dangling["id"],
                                "content": "sandbox terminated: the REPL child exited.",
                                "is_error": True,
                            }
                        )
                    break
                if isinstance(stdout, (ReadRequiredFeedback, FinalAnswerRequiredFeedback)):
                    if type(stdout) not in (ReadRequiredFeedback, FinalAnswerRequiredFeedback):
                        raise unavailable("Unrecognized secure execution control feedback")
                    if native_json:
                        results.append({
                            "type": "control_feedback", "action_id": tu["action_id"], "feedback": stdout,
                        })
                    else:
                        results.append({
                            "type": "tool_result", "tool_use_id": tu["id"],
                            "content": stdout.content(), "is_error": True,
                        })
                    continue
                logger.debug("rlm turn %d stdout: %s", self.turns, stdout[:_TRACE_CHARS])
                results.append(
                    {
                        "type": "action_result" if native_json else "tool_result",
                        "action_id" if native_json else "tool_use_id":
                            tu["action_id"] if native_json else tu["id"],
                        "content": stdout[:_MAX_STDOUT],
                    }
                )
            # Append the tool_result turn even when the sandbox died -- with the
            # error results above the transcript is API-valid -- then fall
            # through to the plain-text fallback.
            messages.append({"role": "user", "content": results})
            if dead_sandbox:
                break
        if protocol_error is not None:
            raise protocol_error
        if native_json or isinstance(runner, MontyExecutor):
            raise RlmToolProtocolError(
                "The selected model did not finish its actions within the configured turn limit.",
                code="RLM_TOOL_PROTOCOL_REQUIRED",
            )
        # ran out of turns -> ask for a direct answer from the transcript. This
        # is the divergence path behind the empty-answer failure mode: the
        # orchestrator never committed to ``final()`` within the budget. Surface
        # it at WARNING so it is visible in logs without DEBUG turn tracing.
        logger.warning(
            "rlm exhausted %d iterations without calling final(); forcing a tool-less final answer",
            self.max_iters,
        )
        messages.append(
            {
                "role": "user",
                "content": (
                    "You have run out of analysis turns. Using everything you have read and "
                    "computed above, write your COMPLETE final answer to the question now, as "
                    "plain text. Do not run any more code."
                ),
            }
        )
        # Re-ask with NO tools so the model cannot keep running code and MUST emit
        # its answer as text; a larger token budget lets a long synthesised answer
        # through in one shot. This is the safety net behind the empty-answer mode:
        # even when the loop never called final(), the transcript already holds the
        # evidence, so a tool-less turn reliably produces a substantive answer.
        from flycanon.core.services.query import provenance

        provenance.model("rlm.forced_final", repr((system, messages)))
        text = "".join(
            b.get("text", "")
            for b in self.client.chat_raw(messages, system, [], max_tokens=4096).get("content", [])
            if b.get("type") == "text"
        )
        logger.debug("rlm forced-final plain-text answer (len=%d)", len(text.strip()))
        # ran out of iterations: forced best-effort answer, not a structured no-answer.
        return text.strip(), self._citations(None, None, docs, question), False

    def _run_block(self, code: str, runner, docs, question):
        """Run one code block via ``runner``; return ``(stdout, final_or_None)``.

        ``runner`` is the in-process namespace (``dict``) -> delegate to
        :meth:`_exec`, or a :class:`SandboxExecutor` -> run the block in the
        child and translate its :class:`BlockResult` into the same contract.
        Citations for a child ``final`` frame are built parent-side, since the
        child only ships raw filings/pages.

        Returns ``(None, None)`` when the sandbox child is dead
        (``terminated``): the caller stops the loop and degrades to a
        parent-side answer instead of running another block on a dead executor.
        ``(None, fin)`` signals a ``final``; ``(stdout, None)`` a live result.
        """
        if isinstance(runner, MontyExecutor):
            feed = runner.run_block(code)
            if feed.status == "halted":
                if not feed.result.success or feed.state != "halted" or runner.tree.expired():
                    error = unavailable(
                        "Final was accepted but execution cleanup or deadline admission failed; "
                        "it cannot be replayed"
                    )
                    error.__dict__["accepted_final"] = feed.result.output
                    raise error
                payload = feed.result.output
                if type(payload) is not dict or set(payload) != {"answer", "citations", "no_answer"}:
                    raise unavailable("The accepted execution result is invalid")
                return None, _Final(payload["answer"], payload["citations"], payload["no_answer"])
            if feed.state != "ready":
                error = unavailable("The secure execution session ended and cannot be resumed")
                error.__dict__["execution_feedback"] = feed.feedback
                raise error
            if feed.status == "rejected":
                if runner.read_required(feed, ReadRequiredFeedback().content()):
                    return ReadRequiredFeedback(), None
                if runner.final_answer_required(feed, FinalAnswerRequiredFeedback().content()):
                    return FinalAnswerRequiredFeedback(), None
                raise unavailable("Unrecognized secure execution control feedback")
            if not feed.result.success:
                return str(feed.result.error_type) + ": " + str(feed.result.error), None
            return feed.result.stdout or "(no output)", None
        if not isinstance(runner, SandboxExecutor):
            return self._exec(code, runner)
        result: BlockResult = runner.run_block(code)
        if result.kind == "final":
            if isinstance(docs, _ContentReads) and not docs.admits((result.final or {}).get("filings")):
                return ReadRequiredFeedback(), None
            payload = result.final or {}
            fin = _Final(
                str(payload.get("answer", "")),
                self._citations(payload.get("filings"), payload.get("pages"), docs, question),
                no_answer=not bool(payload.get("found", True)),
            )
            return None, fin
        if result.kind == "terminated":
            # The child is gone (resource limit / crash / kill / timeout). Signal
            # the loop to stop; it falls through to the plain-text fallback.
            return None, None
        if result.kind == "error":
            # A normal child exception (child still alive): feed the traceback back.
            return (result.error or "") + "\n", None
        return (result.stdout or "(no output)"), None

    def _citations(self, filings, pages, docs, question) -> list[dict]:
        if isinstance(docs, _ContentReads):
            docs = docs._docs
        if not filings:
            return []
        if isinstance(filings, str):
            filings = [filings]
        pages = pages if isinstance(pages, (list, tuple)) else [pages] if pages is not None else []
        cites = []
        for i, fid in enumerate(filings):
            page = pages[i] if i < len(pages) and pages[i] is not None else None
            if docs is not None and isinstance(fid, str) and fid in docs:
                pg_list = docs.pages(fid)
                if page is None:
                    page = _best_page(question, pg_list)
                page = max(0, min(int(page), len(pg_list) - 1))
                # Keep the page's text structure (newlines / table layout) -- the
                # judge needs the actual page the model read, not a flattened
                # prefix. Financial statements align labels to numbers by row.
                content = pg_list[page].strip()[:_CITATION_CONTENT_CHARS]
            else:
                content = ""
            cites.append({"filing": fid, "page": page, "content": content})
        return cites
