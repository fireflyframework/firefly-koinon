# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Optional host process admission before reserving durable callback rows."""

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager


class CallbackWorkAdmission(ABC):
    @abstractmethod
    def admit(self) -> AbstractAsyncContextManager[None]: ...
