# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import service
from pyfly.kernel import ConflictException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.knowledge.bulk_queries.native import BulkQueryNative
from koinon.knowledge.bulk_queries.queue import QueryBatchQueue, QueryLease


@service(name="knowledge.bulk_queries.executor")
class QueryBatchExecutor:
    def __init__(self, queue: QueryBatchQueue, native: BulkQueryNative):
        self.queue, self.native = queue, native

    async def execute(self, lease: QueryLease) -> None:
        with SecurityContextHolder.using(
            SecurityContext(
                user_id=lease.subject,
                attributes={"koinon_token_id": lease.token_id} if lease.token_id else {},
            )
        ):
            try:
                await self.queue.check(lease)
                status, receipt = await self.native.inspect(lease)
                if status == "admitted":
                    await self.queue.failed(lease, code="BULK_QUERY_OUTCOME_UNRESOLVED", unknown=True)
                    return
                if status == "absent":
                    receipt = await self.native.execute(lease)
                if receipt is None:
                    raise ConflictException("Query receipt unavailable", code="BULK_QUERY_RECEIPT_REQUIRED")
                await self.native.acknowledge(lease, receipt)
            except Exception as error:
                try:
                    await self.queue.failed(
                        lease, code=getattr(error, "code", None) or "BULK_QUERY_FAILED", unknown=True
                    )
                except ConflictException as lost:
                    if lost.code != "BULK_LEASE_LOST":
                        raise
