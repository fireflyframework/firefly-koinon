# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One leased item; completed native work is reconciled without model/provider replay."""

import tempfile
from pathlib import Path

from pyfly.container import Provider, service
from pyfly.kernel import ConflictException, ServiceUnavailableException
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.bulk.authority import execution_context
from koinon.knowledge.bulk.ports import BulkIntakePort
from koinon.knowledge.bulk.queue import BulkLease, BulkQueue
from koinon.knowledge.bulk.storage import BulkStorage


@service(name="knowledge.bulk.executor")
class BulkExecutor:
    def __init__(self, queue: BulkQueue, storage: BulkStorage, intakes: Provider[BulkIntakePort | None]):
        self.queue, self.storage, self.intakes = queue, storage, intakes

    async def execute(self, lease: BulkLease) -> None:
        try:
            with SecurityContextHolder.using(execution_context(lease.subject, lease.token_id)):
                inspection_only = False
                try:
                    await self.queue.check(lease)
                except (ConflictException, AccessDenied) as denied:
                    if not isinstance(denied, AccessDenied) and denied.code != "SOURCE_PUBLICATION_DENIED":
                        raise
                    # Cancellation can follow a successful native commit whose
                    # primary acknowledgement was lost. Recover that exact receipt
                    # without reserving or creating any additional native work.
                    try:
                        await self.queue.reconcile_source(lease)
                    except ConflictException as unavailable:
                        if unavailable.code == "SOURCE_PUBLICATION_DENIED":
                            raise denied from unavailable
                        raise
                    inspection_only = True
                native = self.intakes.get()
                if native is None:
                    raise ServiceUnavailableException(
                        "Canonical durable intake is unavailable", code="BULK_NATIVE_REQUIRED"
                    )
                if not inspection_only:
                    await native.reserve(lease)
                observed = await (
                    native.inspect_committed(lease) if inspection_only else native.inspect(lease)
                )
                if inspection_only:
                    if observed.status != "committed" or observed.receipt is None:
                        await self.queue.failed(lease, code="BULK_NATIVE_OUTCOME_UNRESOLVED", unknown=True)
                        return
                    if (
                        observed.receipt.sha256 != lease.sha256
                        or observed.receipt.size_bytes != lease.size_bytes
                    ):
                        raise ConflictException(
                            "Native receipt differs from admitted bytes", code="BULK_NATIVE_RECEIPT_CONFLICT"
                        )
                    await native.settle_source_receipt(lease, observed.receipt)
                    return
                recovery = getattr(lease, "recovery_operation", None)
                expected_failure = getattr(lease, "recovery_failure", None)
                expected_state = {
                    "retry_processing": "failed" if expected_failure is not None else "absent",
                    "finalize_publication": "prepared",
                }
                if recovery is not None and observed.status != expected_state.get(recovery):
                    raise ConflictException(
                        "Native recovery state changed", code="BULK_RECOVERY_STATE_CHANGED"
                    )
                if expected_failure is not None and (
                    recovery != "retry_processing" or observed.failure != expected_failure
                ):
                    raise ConflictException("Native failure changed", code="BULK_RECOVERY_STATE_CHANGED")
                if observed.status in {"admitted", "failed"} and expected_failure is None:
                    await self.queue.failed(lease, code="BULK_NATIVE_OUTCOME_UNRESOLVED", unknown=True)
                    return
                if observed.status == "committed":
                    if observed.receipt is None:
                        raise ConflictException(
                            "Native commit lacks a receipt", code="BULK_NATIVE_RECEIPT_REQUIRED"
                        )
                    receipt = observed.receipt
                elif observed.status == "prepared":
                    receipt = await native.finalize_prepared(lease)
                else:
                    original = await self.queue.original(lease)
                    if original.object_reference_json is not None:
                        with tempfile.TemporaryDirectory(prefix="koinon-bulk-") as directory:
                            path = Path(directory) / "original"
                            await self.storage.read_file(original, path)
                            await self.queue.check(lease)
                            receipt = await native.execute_file(lease, path)
                    else:
                        content = await self.storage.read(
                            original.object_key,
                            original.size_bytes,
                            original.sha256,
                            storage_identity=original.storage_identity,
                        )
                        await self.queue.check(lease)
                        receipt = await native.execute(lease, content)
                if receipt.sha256 != lease.sha256 or receipt.size_bytes != lease.size_bytes:
                    raise ConflictException(
                        "Native receipt differs from admitted bytes", code="BULK_NATIVE_RECEIPT_CONFLICT"
                    )
                await native.acknowledge(lease, receipt)
        except Exception as error:
            code = getattr(error, "code", None) or "BULK_PROCESSING_FAILED"
            try:
                await self.queue.failed(lease, code=code, unknown=True)
            except ConflictException as lost:
                if lost.code != "BULK_LEASE_LOST":
                    raise
