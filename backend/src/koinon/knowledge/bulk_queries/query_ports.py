# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from pydantic import JsonValue

QueryCommit = Callable[[dict[str, JsonValue]], Awaitable[None]]
QueryPublicationGuard = Callable[[], AbstractAsyncContextManager[None]]

QueryAuthorize = Callable[[], Awaitable[None]]
