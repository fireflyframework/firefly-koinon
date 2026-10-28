# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon.assistants.history.entities import ChatFolder


def folder_dto(folder: ChatFolder, *, conversation_count: int = 0) -> dict:
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "scope": folder.scope,
        "revision": folder.revision,
        "conversation_count": conversation_count,
        "created_at": folder.created_at.isoformat(),
        "updated_at": folder.updated_at.isoformat(),
    }
