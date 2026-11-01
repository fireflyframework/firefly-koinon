# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One leased item; completed native work is reconciled without model/provider replay."""

import tempfile
from pathlib import Path

from pyfly.container import Provider, service
from pyfly.kernel import ConflictException, ServiceUnavailableException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.knowledge.bulk.ports import BulkIntakePort
from koinon.knowledge.bulk.queue import BulkLease, BulkQueue
from koinon.knowledge.bulk.storage import BulkStorage


@service(name="knowledge.bulk.executor")
class BulkExecutor:
    def __init__(self, queue: BulkQueue, storage: BulkStorage, intakes: Provider[BulkIntakePort | None]):
        self.queue, self.storage, self.intakes = queue, storage, intakes

    async def execute(self, lease: BulkLease) -> None:
        attributes = {"koinon_token_id": lease.token_id} if lease.token_id else {}
        with SecurityContextHolder.using(SecurityContext(user_id=lease.subject, attributes=attributes)):
            try:
                await self.queue.check(lease)
                native = self.intakes.get()
                if native is None:
                    raise ServiceUnavailableException(
                        "Canonical durable intake is unavailable", code="BULK_NATIVE_REQUIRED"
                    )
                await native.reserve(lease)
                observed = await native.inspect(lease)
                if observed.status == "admitted":
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
