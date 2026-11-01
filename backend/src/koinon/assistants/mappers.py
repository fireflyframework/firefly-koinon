# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0


from koinon.assistants.connections import api_base_url, provider_state
from koinon.assistants.entities import ChatMessage, ChatThread, Provider


def provider_dto(provider: Provider) -> dict:
    return {
        "id": provider.id,
        "name": provider.name,
        "kind": provider.kind,
        "base_url": api_base_url(provider.kind, provider.base_url),
        "model_ids": provider.model_ids,
        "enabled": provider.enabled,
        "revision": provider.revision,
        "secret_configured": provider.secret_ciphertext is not None,
        "checks": provider.checks,
        **provider_state(provider),
    }


def thread_dto(thread: ChatThread) -> dict:
    return {
        "id": thread.id,
        "title": thread.title,
        "title_source": thread.title_source,
        "revision": thread.revision,
        "folder_id": thread.folder_id,
        "archived_at": thread.archived_at.isoformat() if thread.archived_at else None,
        "scope": thread.scope,
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
    }


def message_dto(message: ChatMessage, *, release_verified: bool = False) -> dict:
    from koinon.answers.receipts import legacy_notice, message_language

    masked = message.role == "assistant" and not release_verified
    return {
        "id": message.id,
        "role": message.role,
        "text": legacy_notice(message_language(message)) if masked and message.text else message.text,
        "status": message.status,
        "presentation": message.presentation,
        "citations": [] if masked else message.citations,
        "artifacts": [] if masked else message.artifacts,
        **(
            {"answer_policy": {"outcome": "refused", "code": "EVIDENCE_RELEASE_REQUIRED"}}
            if masked and (message.text or message.answer_policy)
            else {"answer_policy": message.answer_policy}
            if message.answer_policy
            else {}
        ),
        "created_at": message.created_at.isoformat(),
    }
