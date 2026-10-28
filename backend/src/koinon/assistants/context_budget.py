# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reserve the current request before reconstructing authorized native memory."""

import json
from collections.abc import Sequence

from pydantic_ai import Tool as PydanticTool
from pyfly.agentic.content.compression import TokenEstimator
from pyfly.agentic.tools import AgentTool
from pyfly.kernel import InvalidRequestException

from koinon.assistants.settings import AssistantSettings


class ConservativeTokenEstimator(TokenEstimator):
    def estimate(self, text: str) -> int:
        # The native word heuristic undercounts long identifiers and non-Latin text.
        return max(super().estimate(text), len(text.encode("utf-8")))


def history_budget(
    settings: AssistantSettings, *, system: str, question: str, tools: Sequence[AgentTool], output_tokens: int
) -> int:
    schemas = []
    for tool in tools:
        definition = PydanticTool(
            tool.pydantic_handler(), name=tool.name, description=tool.description
        ).tool_def
        schemas.append(
            {
                "name": definition.name,
                "description": definition.description,
                "parameters": definition.parameters_json_schema,
            }
        )
    estimator = ConservativeTokenEstimator()
    reserved = (
        estimator.estimate(system)
        + estimator.estimate(question)
        + estimator.estimate(json.dumps(schemas, ensure_ascii=False))
        + output_tokens
        + settings.tool_result_tokens
        + 512
    )
    if reserved > settings.max_context_tokens:
        raise InvalidRequestException(
            "The question, instructions and tool definitions exceed the configured context budget. "
            "Shorten the question or select a compatible configuration.",
            code="CONTEXT_BUDGET_EXCEEDED",
        )
    return min(settings.max_history_tokens, settings.max_context_tokens - reserved)
