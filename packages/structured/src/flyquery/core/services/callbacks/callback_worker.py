# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
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

"""CallbackWorker -- drains flyquery_callback_outbox + delivers webhooks.

One worker instance per process is sufficient; horizontal scale is
achieved via the row-level ``FOR UPDATE SKIP LOCKED`` claim. The
loop is:

    while not shutdown:
        rows = await repo.claim_due_batch(limit=N)
        if not rows:
            await asyncio.sleep(poll_interval_s)
            continue
        await asyncio.gather(*[_dispatch(r) for r in rows])

Each ``_dispatch`` calls ``CallbackDispatcher.deliver`` and persists
the outcome (DELIVERED / FAILED with backoff / DEAD).

The retry schedule is fixed:

    attempt 1 -> immediate
    attempt 2 -> +30s
    attempt 3 -> +5min
    attempt 4 -> +1h
    attempt 5 -> +6h  (last)
    attempt 6 -> DEAD

All-or-nothing per row. Partial-byte writes are not a concern because
the HTTP layer either commits or raises.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import httpx
from pyfly.container import Provider
from pyfly.container import service as service_bean

from flyquery.config import FlyquerySettings
from flyquery.core.services.callbacks.access import CallbackDeliveryAccess
from flyquery.core.services.callbacks.admission import CallbackWorkAdmission
from flyquery.core.services.callbacks.callback_dispatcher import (
    DeliveryOutcome,
    deliver,
)
from flyquery.core.services.callbacks.callback_repository import (
    CallbackOutboxRepository,
)
from flyquery.core.services.workspaces.workspace_repository import WorkspaceAdminRepository
from flyquery.data import workspace_scope
from flyquery.web.conventions.context import current_tenant_context

logger = logging.getLogger(__name__)


# Retry schedule in seconds: index i -> backoff for the (i+1)-th attempt.
# attempts BEFORE this call: 0 -> backoff[0], 1 -> backoff[1], ... .
# Length defines max_attempts (DEAD once attempts >= len(backoff)).
_RETRY_BACKOFF_SECONDS: tuple[int, ...] = (30, 300, 3600, 21600)
_MAX_ATTEMPTS = 1 + len(_RETRY_BACKOFF_SECONDS)


@service_bean(name="structured.CallbackWorker")
class CallbackWorker:
    """Periodic outbox drainer."""

    def __init__(
        self,
        callback_outbox_repository: CallbackOutboxRepository,
        settings: FlyquerySettings,
        workspace_admin_repository: WorkspaceAdminRepository,
        access: Provider[CallbackDeliveryAccess | None] | None = None,
        work_admission: Provider[CallbackWorkAdmission | None] | None = None,
    ) -> None:
        self._repo = callback_outbox_repository
        self._settings = settings
        self._workspace_admin = workspace_admin_repository
        self._access = access
        self._work_admission = work_admission
        # Settings defaults: 5s poll, 25 rows / batch, 10s per-request timeout.
        # Per-attribute getattr so an older settings module without these knobs
        # falls back to sane values instead of AttributeError-ing on startup.
        self._poll_interval_s: float = float(getattr(settings, "callback_poll_interval_s", 5.0))
        self._batch_size: int = int(getattr(settings, "callback_batch_size", 25))
        self._request_timeout_s: float = float(getattr(settings, "callback_request_timeout_s", 10.0))
        self._shutdown = asyncio.Event()

    async def run_forever(self) -> None:
        """Run the drain loop until :meth:`stop` is called.

        Named ``run_forever`` (not ``run``) on purpose: pyfly's
        ``ApplicationContext`` treats any bean method named ``run``
        as an ``ApplicationRunner`` and invokes it at startup with
        a positional ``args`` parameter. That would (a) crash because
        our signature is parameterless and (b) accidentally start the
        callback drain inside the API process. The dedicated
        ``flyquery worker callback`` CLI command is the only intended
        entry point.
        """
        logger.info(
            "callback_worker_started poll_interval_s=%s batch=%d timeout_s=%s",
            self._poll_interval_s,
            self._batch_size,
            self._request_timeout_s,
        )
        async with httpx.AsyncClient(http2=False, timeout=self._request_timeout_s) as client:
            while not self._shutdown.is_set():
                try:
                    await self._drain_scopes(client)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("callback_worker claim failed: %s", exc)
                    await self._sleep_or_exit(self._poll_interval_s)
                    continue

                await self._sleep_or_exit(self._poll_interval_s)

        logger.info("callback_worker_stopped")

    async def _drain_scopes(self, client: httpx.AsyncClient) -> None:
        work = self._work_admission() if self._work_admission is not None else None
        if work is None and getattr(self._settings, "_require_model_bindings", False):
            raise RuntimeError("Managed callback work admission is unavailable")
        for scope in await self._workspace_admin.scopes():
            with workspace_scope(scope["tenant_id"], str(scope["id"])):
                if work is None:
                    rows = await self._repo.claim_due_batch(
                        limit=self._batch_size, lease_seconds=self._request_timeout_s + 30
                    )
                    await asyncio.gather(*[self._dispatch(client, row) for row in rows])
                    continue
                for _ in range(self._batch_size):
                    if self._shutdown.is_set():
                        return
                    async with work.admit():
                        rows = await self._repo.claim_due_batch(
                            limit=1, lease_seconds=self._request_timeout_s + 30
                        )
                        if not rows:
                            break
                        await self._dispatch(client, rows[0])

    async def stop(self) -> None:
        self._shutdown.set()

    async def _sleep_or_exit(self, seconds: float) -> None:
        # Tick on timeout (no shutdown signal in the window).
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._shutdown.wait(), timeout=seconds)

    async def _dispatch(self, client: httpx.AsyncClient, row: dict[str, Any]) -> None:
        context = current_tenant_context()
        if (
            context is None
            or row["tenant_id"] != context.tenant_id
            or str(row["workspace_id"]) != context.workspace_id
        ):
            raise RuntimeError("Callback row disagrees with its trusted workspace scope")
        try:
            access = self._access() if self._access is not None else None
            if access is None and getattr(self._settings, "_require_model_bindings", False):
                raise RuntimeError("Managed callback authority is unavailable")
            if access is not None:
                await access.authorize(row)
        except Exception:
            await self._repo.mark_attempt_failure(
                id_=row["id"],
                status_code=None,
                error="CALLBACK_AUTHORITY_UNAVAILABLE",
                backoff_seconds=0,
                terminal=True,
                claim=row,
            )
            logger.warning("Callback authority is unavailable; delivery was not attempted")
            return
        if not await self._repo.still_owned(row):
            return
        outcome: DeliveryOutcome = await deliver(
            client=client,
            url=row["callback_url"],
            payload=row["payload_json"] or {},
            secret=row["callback_secret"],
            extra_headers=row["callback_headers"] or {},
            event_type=row["event_type"],
            ingest_job_id=row["ingest_job_id"],
            timeout_s=self._request_timeout_s,
        )
        if outcome.success:
            settled = await self._repo.mark_delivered(
                id_=row["id"],
                status_code=outcome.status_code or 0,
                claim=row,
            )
            if not settled:
                logger.warning("Callback delivery outcome lost its reservation")
                return
            logger.info(
                "callback_delivered id=%s job_id=%s status=%s",
                row["id"],
                row["ingest_job_id"],
                outcome.status_code,
            )
            return

        attempts_after = (row["attempts"] or 0) + 1
        terminal = attempts_after >= _MAX_ATTEMPTS
        backoff = 0 if terminal else _RETRY_BACKOFF_SECONDS[row["attempts"] or 0]
        settled = await self._repo.mark_attempt_failure(
            id_=row["id"],
            status_code=outcome.status_code,
            error=outcome.error or "unknown",
            backoff_seconds=backoff,
            terminal=terminal,
            claim=row,
        )
        if not settled:
            logger.warning("Callback failure outcome lost its reservation")
            return
        logger.warning(
            "callback_attempt_failed id=%s job_id=%s attempts=%d/%d terminal=%s status=%s error=%s",
            row["id"],
            row["ingest_job_id"],
            attempts_after,
            _MAX_ATTEMPTS,
            terminal,
            outcome.status_code,
            outcome.error,
        )
