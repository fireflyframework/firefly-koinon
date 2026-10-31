# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Wait for blocking reader operations before releasing their owned paths."""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Callable


async def run_native[**P, T](function: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    """Preserve context and defer cancellation until the native call finishes.

    Cancellation cannot interrupt native code; timeouts remain soft while it
    drains. An executor Future avoids a child Task that loop shutdown could
    cancel independently while its thread still uses the caller's paths.
    """
    context = contextvars.copy_context()

    def invoke() -> T:
        return context.run(function, *args, **kwargs)

    worker = asyncio.get_running_loop().run_in_executor(None, invoke)
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError as cancelled:
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except BaseException:
                break
        try:
            worker.result()
        except BaseException as failure:
            if failure is cancelled:
                raise
            raise cancelled from failure
        raise
