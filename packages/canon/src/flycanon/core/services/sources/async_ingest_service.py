# Copyright 2024-2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
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

"""Async-ingest orchestrator.

Public surface (controller side): :meth:`submit_async` creates a
``canon_ingest_jobs`` row in ``queued`` status and broadcasts an
``IngestSourceRequested`` event on the ingest topic. The job's
payload (bytes + metadata) lives on the row's ``metadata_json``
column so the worker can pick it up by id without any out-of-band
storage.

Worker surface: :meth:`process` runs the full intake pipeline for
one job. The :class:`IngestWorker` subscribes to the
``IngestSourceRequested`` event and dispatches here.

Lifecycle events are emitted at every stage so the SSE streaming
endpoint can replay them to the caller. The audit log captures
the bookend events (``ingest.queued`` + the terminal outcome).
"""

from __future__ import annotations

import base64
import json
import logging
import tempfile
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from koinon_storage.files import StoredObjectReference, source_file
from pyfly.container import service
from pyfly.context.consumer_context import PRIVATE_CONSUMER_CONTEXT, consumer_context, public_consumer_data
from pyfly.eda import EventPublisher
from pyfly.scheduling import scheduled

from flycanon.config import CanonSettings
from flycanon.core.services.audit import AuditService
from flycanon.core.services.sources.intake_service import IntakeService
from flycanon.core.services.sources.lease import (
    IngestLease,
    IngestLeaseLost,
    authorize_ingest_output,
    bind_ingest_lease,
)
from flycanon.core.services.storage.object_store import ObjectStore
from flycanon.interfaces.dtos.source import SubmitSourceRequest
from flycanon.interfaces.enums import SourceKind
from flycanon.models.entities.ingest_job import IngestJobRow
from flycanon.models.repositories.ingest_job_repository import IngestJobRepository
from flycanon.web.conventions.headers import HEADER_CORRELATION_ID, HEADER_WEBHOOK_SIGNATURE
from flycanon.web.conventions.webhook_signature import sign_payload

logger = logging.getLogger(__name__)


# Event type the worker subscribes to. Lives on the ``ingest`` topic
# so downstream observers can replay both submit + finish events on
# one subscription if they want.
INGEST_REQUESTED_EVENT = "IngestSourceRequested"


@service(name="canon.AsyncIngestService")
class AsyncIngestService:
    def __init__(
        self,
        intake: IntakeService,
        repository: IngestJobRepository,
        audit: AuditService,
        event_publisher: EventPublisher,
        settings: CanonSettings,
        object_store: ObjectStore | None = None,
    ) -> None:
        self._intake = intake
        self._repository = repository
        self._audit = audit
        self._publisher = event_publisher
        self._settings = settings
        self._object_store = object_store

    # ------------------------------------------------------------------
    # Submit side
    # ------------------------------------------------------------------

    async def submit_async(
        self,
        *,
        request: SubmitSourceRequest,
        content: bytes,
        filename: str | None,
        content_type: str | None,
        actor: str | None,
        correlation_id: str | None,
        tenant_id: str,
        workspace_id: str,
        callback_url: str | None = None,
    ) -> IngestJobRow:
        """Persist a job row + broadcast the IngestSourceRequested event.

        ``tenant_id`` and ``workspace_id`` are required -- callers must
        propagate the request-bound :class:`TenantContext`. A missing
        scope is a controller bug, not a silent ``"default"`` fallback.
        """
        with tempfile.TemporaryDirectory(prefix="koinon-intake-") as directory:
            path = Path(directory) / "original"
            if len(content) > self._settings.max_bytes:
                raise ValueError("Document exceeds the configured intake byte limit")
            path.write_bytes(content)
            return await self.submit_file_async(
                request=request,
                path=path,
                filename=filename,
                content_type=content_type,
                actor=actor,
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                callback_url=callback_url,
            )

    async def submit_file_async(
        self,
        *,
        request,
        path,
        filename,
        content_type,
        actor,
        correlation_id,
        tenant_id,
        workspace_id,
        callback_url=None,
    ) -> IngestJobRow:
        if self._object_store is None or not self._settings.store_originals:
            raise RuntimeError("Durable pinned original storage is required for queued ingestion")
        if (
            not tenant_id
            or not workspace_id
            or any("/" in value or ".." in value for value in (tenant_id, workspace_id))
        ):
            raise ValueError("A valid authoritative document scope is required")
        job_id = str(uuid.uuid4())
        scope_tenant, scope_workspace = tenant_id, workspace_id
        with source_file(path, self._settings.max_bytes):
            pass
        reference = await self._object_store.create_file(
            f"koinon/{tenant_id}/{workspace_id}/pending/{job_id}/original", path, content_type
        )
        if reference.size_bytes > self._settings.max_bytes:
            raise ValueError("Document exceeds the configured intake byte limit")
        payload: dict[str, Any] = {
            "content_reference": {
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
                "object": reference.to_dict(),
            },
            "kind": request.kind.value if request.kind else SourceKind.unknown.value,
            "uri": request.uri,
            "metadata": public_consumer_data(_serialise_metadata(request)),
        }
        captured = consumer_context()
        if captured is not None:
            payload[PRIVATE_CONSUMER_CONTEXT] = captured
        row = IngestJobRow(
            id=job_id,
            tenant_id=scope_tenant,
            workspace_id=scope_workspace,
            status="queued",
            filename=filename,
            content_type=content_type,
            uri=request.uri,
            actor=actor,
            correlation_id=correlation_id,
            callback_url=callback_url,
            metadata_json=payload,
        )
        stored = await self._repository.add(row)
        await self._repository.append_event(
            stored.id,
            stage="queued",
            message="job queued -- waiting for worker pickup",
            tenant_id=scope_tenant,
            workspace_id=scope_workspace,
        )
        await self._audit.record(
            event_type="ingest.queued",
            subject_kind="ingest_job",
            subject_id=stored.id,
            tenant_id=scope_tenant,
            workspace_id=scope_workspace,
            actor=actor,
            correlation_id=correlation_id,
            payload={
                "filename": filename,
                "content_type": content_type,
                "uri": request.uri,
            },
        )
        await self._publish_requested(
            stored.id,
            correlation_id,
            tenant_id=scope_tenant,
            workspace_id=scope_workspace,
        )
        logger.info(
            "ingest job queued id=%s filename=%s bytes=%d",
            stored.id,
            filename,
            reference.size_bytes,
        )
        return stored

    async def _publish_requested(
        self,
        job_id: str,
        correlation_id: str | None,
        *,
        tenant_id: str,
        workspace_id: str,
    ) -> None:
        """Publish ``IngestSourceRequested`` for ``job_id`` with its scope.

        Scope travels on the ingest topic (26.7.1) so a consumer on a
        shared broker can route by tenant without a DB lookup; the
        worker itself still reads the row for the scope. The two
        arguments are keyword-only and required, not optional with a
        "when both are passed" branch: the first cut had that branch,
        and the stuck-job sweep -- which had only ids in hand -- took
        it, so the one republish path that fires after something has
        already gone wrong was also the one path that published an
        unscoped event. A caller that has no scope has no business
        publishing this event; make it read the row first.
        """
        if self._publisher is None:
            return
        payload: dict[str, Any] = {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
        }
        try:
            await self._publisher.publish(  # type: ignore[attr-defined]
                destination=self._settings.ingest_topic,
                event_type=INGEST_REQUESTED_EVENT,
                payload=payload,
                headers={"correlation-id": correlation_id} if correlation_id else None,
            )
        except Exception as exc:
            logger.warning("IngestSourceRequested publish failed job_id=%s: %s", job_id, exc)

    # ------------------------------------------------------------------
    # Worker side
    # ------------------------------------------------------------------

    async def process(self, job_id: str, *, admission=None) -> None:
        """Run the intake pipeline for one queued job.

        Idempotent on terminal states -- if the job is already
        succeeded / failed we skip without re-running (a duplicate
        EDA delivery should not double-emit citations).

        The worker dispatch path receives only the job id in the EDA
        payload, so we read the row through the cross-workspace
        helper to learn the scope. Every subsequent repo call --
        including any that follow on the request path -- is keyed
        by the row's own ``tenant_id`` / ``workspace_id``.

        RLS bypass
        ----------
        Row-level security is enabled on every tenant-scoped table.
        The request flow sets ``app.tenant_id`` /
        ``app.workspace_id`` via :func:`install_tenant_guc_hook`, but
        worker invocations have no :class:`TenantContext` bound -- so
        the GUCs stay empty and RLS would reject the first read.

        Deployment must therefore connect the worker process as a
        Postgres role with ``BYPASSRLS`` (planned: ``flycanon_admin``).
        The application code stays unchanged; only the database role
        differs from the API server (which connects as the unprivileged
        ``flycanon_app`` role). The first cross-workspace query --
        ``get_across_workspaces`` above -- relies on this bypass.
        """
        job = await self._repository.get_across_workspaces(job_id)
        if job is None:
            logger.warning("worker received unknown job_id=%s -- dropping", job_id)
            return
        if job.status in ("succeeded", "failed"):
            logger.info(
                "ingest job %s already in terminal state %s -- skipping",
                job_id,
                job.status,
            )
            return

        running = await self._repository.mark_running(
            job_id,
            lease_seconds=self._settings.ingest_timeout_s,
        )
        if running is None:
            # Another worker holds an active lease OR the job is already
            # terminal. The atomic claim returns nothing in either case
            # and we treat it as an idempotent skip.
            logger.info(
                "ingest job %s could not be claimed (live lease held or terminal) "
                "-- skipping duplicate delivery",
                job_id,
            )
            return
        job = running
        # ``attempts`` from this claim is our lease identity: subsequent
        # mark_succeeded / mark_failed UPDATEs are guarded by it so a
        # poached lease (worker took too long, another replica
        # re-claimed) can't silently overwrite the new owner's state.
        lease_attempts = job.attempts
        # Poison-job guard: once a job has been reclaimed past the
        # attempts ceiling, give up and mark it failed rather than
        # looping forever. A worker that keeps crashing on the same
        # payload would otherwise eat replica budget indefinitely.
        if job.attempts > self._settings.ingest_max_attempts:
            logger.warning(
                "ingest job %s exhausted attempts (%d > %d) -- marking failed",
                job_id,
                job.attempts,
                self._settings.ingest_max_attempts,
            )
            await self._repository.mark_failed(
                job_id,
                code="attempts_exhausted",
                message=f"job aborted after {job.attempts} attempts",
                expected_attempts=lease_attempts,
            )
            return

        started = job.started_at
        if started is None:
            raise IngestLeaseLost()
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        lease = IngestLease(
            job.id,
            job.tenant_id,
            job.workspace_id,
            job.attempts,
            started,
            started + timedelta(seconds=self._settings.ingest_timeout_s),
        )
        with bind_ingest_lease(lease):
            try:
                async with admission(job, lease) if admission is not None else nullcontext():
                    await self._process_claimed(job, lease_attempts)
            except IngestLeaseLost:
                return
            except Exception as error:
                await self._repository.mark_failed(
                    job.id,
                    code=str(getattr(error, "code", None) or "INGEST_FAILED"),
                    message="Ingestion authority is unresolved; review and submit a new job",
                    expected_attempts=lease_attempts,
                )

    async def _process_claimed(self, job, lease_attempts):
        job_id = job.id
        payload = job.metadata_json or {}
        try:
            kind_value = payload.get("kind") or SourceKind.unknown.value
            metadata = payload.get("metadata") or {}
            request = SubmitSourceRequest.model_validate(
                {
                    "kind": kind_value,
                    "uri": payload.get("uri"),
                    "metadata": metadata,
                }
            )

            await self._repository.append_event(
                job_id,
                stage="normalising",
                message="binary normalise + load",
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
            )
            arguments = dict(
                request=request,
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
                filename=job.filename,
                content_type=job.content_type,
                actor=job.actor,
                correlation_id=job.correlation_id,
            )
            if "content_reference" in payload:
                captured = payload["content_reference"]
                if (
                    not isinstance(captured, dict)
                    or set(captured) != {"tenant_id", "workspace_id", "object"}
                    or (captured["tenant_id"], captured["workspace_id"]) != (job.tenant_id, job.workspace_id)
                ):
                    raise ValueError("Pending original scope differs from its authoritative job")
                reference = StoredObjectReference.from_dict(captured["object"])
                expected_prefix = f"koinon/{job.tenant_id}/{job.workspace_id}/pending/{job.id}/"
                if not reference.key.startswith(expected_prefix) or self._object_store is None:
                    raise ValueError("Pending original does not belong to this document job")
                with tempfile.TemporaryDirectory(prefix="koinon-document-") as directory:
                    path = Path(directory) / "original"
                    await self._object_store.download_file(
                        reference, path, max_bytes=self._settings.max_bytes
                    )
                    source = await self._intake.submit_file(
                        **arguments,
                        path=path,
                        original_reference=reference,
                        logical_source_key=f"ingest:{job.id}",
                        operation_id=f"ingest:{job.id}",
                    )
            else:
                encoded = payload.get("content_base64") or ""
                # Old retained jobs remain readable, with their original 32 MiB ceiling.
                legacy_max = min(self._settings.max_bytes, 32 * 1024**2)
                if not isinstance(encoded, str) or len(encoded) > ((legacy_max + 2) // 3) * 4:
                    raise ValueError("Legacy document exceeds its registered byte bound")
                content = base64.b64decode(encoded, validate=True)
                if len(content) > legacy_max:
                    raise ValueError("Legacy document exceeds its registered byte bound")
                source = await self._intake.submit(**arguments, content=content)
            await self._repository.append_event(
                job_id,
                stage="finished",
                message="intake pipeline complete",
                payload={
                    "source_id": source.id,
                    "n_chunks": source.n_chunks,
                    "content_sha256": source.content_sha256,
                },
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
            )
            finalised = await self._repository.mark_succeeded(
                job_id,
                source_id=source.id,
                content_sha256=source.content_sha256,
                expected_attempts=lease_attempts,
            )
            if finalised is None:
                # Lease was poached mid-run. The new owner is the source
                # of truth -- don't publish a second IngestSourceFinished
                # or fire the webhook from this stale path.
                logger.warning(
                    "ingest job %s lease lost mid-run (attempts moved past %d) -- skipping success publish",
                    job_id,
                    lease_attempts,
                )
                return
            await self._audit.record(
                event_type="ingest.succeeded",
                subject_kind="ingest_job",
                subject_id=job_id,
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
                actor=job.actor,
                correlation_id=job.correlation_id,
                payload={
                    "source_id": source.id,
                    "n_chunks": source.n_chunks,
                },
            )
            await self._publish_finish(
                event_type="IngestSourceFinished",
                job_id=job_id,
                payload={
                    "source_id": source.id,
                    "n_chunks": source.n_chunks,
                    "tenant_id": job.tenant_id,
                    "workspace_id": job.workspace_id,
                },
            )
            logger.info("ingest job succeeded id=%s source_id=%s", job_id, source.id)

            if job.callback_url:
                # Webhook delivery is best-effort -- the durable
                # record is the audit row.
                await self._fire_webhook(job, status="succeeded", source_id=source.id)
        except IngestLeaseLost:
            return
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", None) or type(exc).__name__
            await self._repository.append_event(
                job_id,
                stage="failed",
                message=str(exc),
                payload={"code": code},
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
            )
            failed = await self._repository.mark_failed(
                job_id,
                code=str(code),
                message=str(exc),
                expected_attempts=lease_attempts,
            )
            if failed is None:
                # Same lease-poaching guard as the success path: another
                # worker took over while we were running; let them be
                # the canonical source of the failure narrative.
                logger.warning(
                    "ingest job %s lease lost mid-run (attempts moved past %d) -- skipping failure publish",
                    job_id,
                    lease_attempts,
                )
                return
            await self._audit.record(
                event_type="ingest.failed",
                subject_kind="ingest_job",
                subject_id=job_id,
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
                actor=job.actor,
                correlation_id=job.correlation_id,
                payload={"code": str(code), "message": str(exc)},
            )
            await self._publish_finish(
                event_type="IngestSourceFailed",
                job_id=job_id,
                payload={
                    "code": str(code),
                    "message": str(exc),
                    "tenant_id": job.tenant_id,
                    "workspace_id": job.workspace_id,
                },
            )
            logger.warning("ingest job failed id=%s code=%s error=%s", job_id, code, exc)
            if job.callback_url:
                await self._fire_webhook(job, status="failed", error_code=str(code), error_message=str(exc))

    # ------------------------------------------------------------------
    # Periodic stuck-job sweep
    # ------------------------------------------------------------------

    @scheduled(fixed_rate=timedelta(seconds=60))
    async def sweep_stuck_jobs(self) -> None:
        """Demote stale ``running`` rows back to ``queued`` + republish.

        ``mark_running`` already re-claims stale rows opportunistically
        when a worker receives a duplicate ``IngestSourceRequested``
        event. This sweep covers the case where the original event
        delivery has been lost (worker crashed before completing AND
        the broker dropped the message): without it, a row sitting at
        ``running`` past its lease has no path back into a worker's
        dispatch loop.

        The sweep is opportunistic, idempotent, and self-rate-limited:

        * ``reclaim_stuck`` uses the same lease threshold
          (``ingest_timeout_s``) as the in-band claim. Rows that have
          legitimate live owners stay at ``running``.
        * Each reclaimed id triggers an ``IngestSourceRequested``
          republish. ``mark_running``'s atomic claim handles the case
          where multiple workers see the republish.
        * The default ``fixed_rate`` of 60s is well below any sensible
          lease budget; a stuck job is observable within one sweep
          interval rather than waiting for an inbound delivery.
        """
        try:
            reclaimed = await self._repository.reclaim_stuck(
                lease_seconds=self._settings.ingest_timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 -- swallow so the scheduler loop survives
            logger.warning("stuck-job sweep failed: %s", exc)
            return
        if not reclaimed:
            return
        logger.info(
            "stuck-job sweep reclaimed %d job(s): %s",
            len(reclaimed),
            [job.job_id for job in reclaimed],
        )
        for job in reclaimed:
            await self._publish_requested(
                job.job_id,
                correlation_id=None,
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
            )

    async def _publish_finish(self, *, event_type: str, job_id: str, payload: dict[str, Any]) -> None:
        if self._publisher is None:
            return
        try:
            await self._publisher.publish(  # type: ignore[attr-defined]
                destination=self._settings.ingest_topic,
                event_type=event_type,
                payload={"job_id": job_id, **payload},
            )
        except Exception as exc:
            logger.warning("%s publish failed job_id=%s: %s", event_type, job_id, exc)

    async def _fire_webhook(
        self,
        job: IngestJobRow,
        *,
        status: str,
        source_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """POST the terminal outcome to ``job.callback_url``, signed.

        The payload carries ``tenant_id`` / ``workspace_id`` so a
        receiver serving many tenants can route the callback without
        first looking the job up. The body is serialised ONCE and those
        exact bytes are both signed and sent (see
        :mod:`flycanon.web.conventions.webhook_signature` for why the
        MAC must cover the raw bytes). When ``FLYCANON_WEBHOOK_SECRET``
        is empty the request goes out unsigned, which the boot log has
        already warned about. Delivery is best-effort and single-shot;
        the durable record is the audit row and the job row, so a
        receiver that missed a delivery polls ``GET /api/v1/ingest-jobs/
        {id}``.

        ``callback_url`` was vetted by the host policy at submit time
        (see :meth:`SourcesController.submit_json`); it is not re-checked
        here because the worker may legitimately run with
        ``FLYCANON_URL_FETCH_ALLOW_PRIVATE`` set differently from the API
        and the submit-time decision is the one the caller was told.
        """
        if not job.callback_url:
            return
        try:
            import httpx
        except ImportError:  # pragma: no cover
            return
        payload = {
            "job_id": job.id,
            "tenant_id": job.tenant_id,
            "workspace_id": job.workspace_id,
            "status": status,
            "source_id": source_id,
            "error_code": error_code,
            "error_message": error_message,
            "occurred_at": datetime.now(UTC).isoformat(),
        }
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if job.correlation_id:
            headers[HEADER_CORRELATION_ID] = job.correlation_id
        secret = self._settings.webhook_secret
        if secret:
            headers[HEADER_WEBHOOK_SIGNATURE] = sign_payload(secret, body)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    lease = await authorize_ingest_output(
                        required=bool(getattr(self._settings, "_require_model_bindings", False))
                    )
                    if lease is not None:
                        current = await self._repository.get(
                            job.id, tenant_id=lease.tenant_id, workspace_id=lease.workspace_id
                        )
                        started = current.started_at if current is not None else None
                        if started is not None and started.tzinfo is None:
                            started = started.replace(tzinfo=UTC)
                        if (
                            current is None
                            or (
                                current.id,
                                current.tenant_id,
                                current.workspace_id,
                                current.attempts,
                                started,
                                current.status,
                            )
                            != (
                                lease.id,
                                lease.tenant_id,
                                lease.workspace_id,
                                lease.attempts,
                                lease.started_at,
                                status,
                            )
                            or status not in {"succeeded", "failed"}
                        ):
                            raise IngestLeaseLost()
                except Exception:
                    logger.warning(
                        "webhook delivery denied", extra={"error_code": "CALLBACK_AUTHORITY_UNAVAILABLE"}
                    )
                    return
                await client.post(job.callback_url, content=body, headers=headers)
        except Exception as exc:  # noqa: BLE001
            logger.warning("webhook delivery failed", extra={"error_type": type(exc).__name__})


def _serialise_metadata(request: SubmitSourceRequest) -> dict[str, Any]:
    """Round-trip-safe serialisation of ``SubmitSourceRequest.metadata``."""
    meta = request.metadata.model_dump(mode="json") if request.metadata else {}
    return meta
