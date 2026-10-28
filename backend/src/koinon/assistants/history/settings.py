# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from pyfly.container import component
from pyfly.core import config_properties


@component(name="assistants.history.settings")
@config_properties(prefix="koinon.chat.history")
@dataclass
class ChatHistorySettings:
    max_folders: int = 200
    max_folder_depth: int = 8

    def __post_init__(self):
        if type(self.max_folders) is not int or not 1 <= self.max_folders <= 10000:
            raise ValueError("Chat folder limit must be from 1 to 10000")
        if type(self.max_folder_depth) is not int or not 1 <= self.max_folder_depth <= 16:
            raise ValueError("Chat folder depth must be from 1 to 16")
