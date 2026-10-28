# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository

from koinon.assistants.history.entities import ChatFolder


@repository(name="assistants.history.folders")
class ChatFolderRepository(Repository[ChatFolder, str]):
    """Private organization of conversations; knowledge scope remains independently authorized."""
