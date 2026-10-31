# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pure effective organization limits constrained by deployment hard caps."""

from koinon.assistants.settings import AssistantSettings
from koinon.organization_chat.dtos import OrganizationMemoryPolicy


def effective_memory_policy(value: dict | None, settings: AssistantSettings) -> OrganizationMemoryPolicy:
    policy = (
        OrganizationMemoryPolicy.model_validate(value) if value is not None else OrganizationMemoryPolicy()
    )
    messages = min(policy.max_history_messages, max(0, settings.max_history_messages), 40)
    return policy.model_copy(
        update={
            "max_history_messages": messages,
            "max_history_tokens": min(policy.max_history_tokens, max(0, settings.max_history_tokens)),
            "max_project_memory_messages": min(policy.max_project_memory_messages, messages),
        }
    )
