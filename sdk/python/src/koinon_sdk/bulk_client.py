# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed bounded batch operations; uncertain mutations are never retried automatically."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

from koinon_sdk.bulk import (
    BulkAction,
    FileBatchCapabilities,
    FileBatchCreate,
    FileBatchPage,
    FileBatchView,
    FileItemPage,
    StagedFileReceipt,
)
from koinon_sdk.file_upload import BLOCK_BYTES, MAX_ORIGINAL_BYTES, verified_original


class BulkClientMixin(ABC):
    @staticmethod
    @abstractmethod
    def _tenant(tenant_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    def _batch_path(self, tenant_id: str, batch_id: str) -> str:
        return self._tenant(tenant_id) + "/sources/batches/" + quote(batch_id, safe="")

    def _batch_item_path(self, tenant_id: str, batch_id: str, item_id: str) -> str:
        return self._batch_path(tenant_id, batch_id) + "/items/" + quote(item_id, safe="")

    async def file_batch_capabilities(self, tenant_id: str, workspace_id: str) -> FileBatchCapabilities:
        return FileBatchCapabilities.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/source-batch-capabilities",
                params={"workspace_id": workspace_id},
            )
        )

    async def create_file_batch(
        self, tenant_id: str, value: FileBatchCreate, idempotency_key: str
    ) -> FileBatchView:
        return FileBatchView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/sources/batches",
                json=value.model_dump(mode="json", exclude_unset=True),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def file_batches(self, tenant_id: str, *, page: int = 1, page_size: int = 25) -> FileBatchPage:
        return FileBatchPage.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/sources/batches",
                params={"page": page, "page_size": page_size},
            )
        )

    async def file_batch(self, tenant_id: str, batch_id: str) -> FileBatchView:
        return FileBatchView.model_validate(await self._request("GET", self._batch_path(tenant_id, batch_id)))

    async def file_batch_items(
        self, tenant_id: str, batch_id: str, *, page: int = 1, page_size: int = 25
    ) -> FileItemPage:
        return FileItemPage.model_validate(
            await self._request(
                "GET",
                self._batch_path(tenant_id, batch_id) + "/items",
                params={"page": page, "page_size": page_size},
            )
        )

    async def upload_file_batch_item(
        self, tenant_id: str, batch_id: str, item_id: str, content: bytes, idempotency_key: str
    ) -> StagedFileReceipt:
        if not 1 <= len(content) <= MAX_ORIGINAL_BYTES:
            raise ValueError("Choose a nonempty original of at most 128 MiB")
        return StagedFileReceipt.model_validate(
            await self._request(
                "PUT",
                self._batch_item_path(tenant_id, batch_id, item_id) + "/content",
                content=content,
                headers={"Idempotency-Key": idempotency_key, "Content-Type": "application/octet-stream"},
            )
        )

    async def upload_file_batch_path(
        self,
        tenant_id: str,
        batch_id: str,
        item_id: str,
        path: Path,
        idempotency_key: str,
        *,
        expected_size_bytes: int,
        expected_sha256: str,
    ) -> StagedFileReceipt:
        """Snapshot and verify a caller-selected file, then stream it with bounded memory."""
        async with verified_original(path, expected_size_bytes, expected_sha256) as source:

            async def body() -> AsyncIterator[bytes]:
                count = 0
                while part := source.read(BLOCK_BYTES):
                    count += len(part)
                    if count > expected_size_bytes:
                        raise ValueError("Original grew during upload; inspect its retained receipt")
                    yield part

            response = await self._request(
                "PUT",
                self._batch_item_path(tenant_id, batch_id, item_id) + "/content",
                content=body(),
                headers={
                    "Idempotency-Key": idempotency_key,
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(expected_size_bytes),
                },
            )
            return StagedFileReceipt.model_validate(response)

    async def file_batch_item_receipt(self, tenant_id: str, batch_id: str, item_id: str) -> StagedFileReceipt:
        return StagedFileReceipt.model_validate(
            await self._request("GET", self._batch_item_path(tenant_id, batch_id, item_id) + "/receipt")
        )

    async def submit_file_batch(
        self, tenant_id: str, batch_id: str, value: BulkAction, idempotency_key: str
    ) -> FileBatchView:
        return FileBatchView.model_validate(
            await self._request(
                "POST",
                self._batch_path(tenant_id, batch_id) + "/submit",
                json=value.model_dump(mode="json"),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def cancel_file_batch(
        self, tenant_id: str, batch_id: str, value: BulkAction, idempotency_key: str
    ) -> FileBatchView:
        return FileBatchView.model_validate(
            await self._request(
                "POST",
                self._batch_path(tenant_id, batch_id) + "/cancel",
                json=value.model_dump(mode="json"),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def reconcile_file_batch_item(
        self, tenant_id: str, batch_id: str, item_id: str, value: BulkAction, idempotency_key: str
    ) -> FileBatchView:
        return FileBatchView.model_validate(
            await self._request(
                "POST",
                self._batch_item_path(tenant_id, batch_id, item_id) + "/reconcile",
                json=value.model_dump(mode="json"),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def reconcile_file_batch_original(
        self, tenant_id: str, batch_id: str, item_id: str, value: BulkAction, idempotency_key: str
    ) -> FileBatchView:
        return FileBatchView.model_validate(
            await self._request(
                "POST",
                self._batch_item_path(tenant_id, batch_id, item_id) + "/original/reconcile",
                json=value.model_dump(mode="json"),
                headers={"Idempotency-Key": idempotency_key},
            )
        )
