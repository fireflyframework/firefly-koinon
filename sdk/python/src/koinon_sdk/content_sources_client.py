# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owner-delegated source management. Personal tokens and headless consent are unsupported."""

from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import quote

from pydantic import TypeAdapter

from koinon_sdk.content_sources import (
    SourceCapabilitiesOutput,
    SourceConnectionOutput,
    SourceConnectionPage,
    SourceConnectionRevision,
    SourceFolderPage,
    SourceLocationPage,
)
from koinon_sdk.reader_sources import ReaderSelectionInput, ReaderSelectionOutput
from koinon_sdk.source_sync import (
    SourceControlInput,
    SourceControlOutput,
    SourceExistingPolicyReviewInput,
    SourceMappingOutput,
    SourceOperationReceipt,
    SourcePolicyApplyInput,
    SourcePolicyOperationOutput,
    SourcePolicyReviewInput,
    SourceReviewPage,
    SourceRunItemPage,
    SourceRunOutput,
)
from koinon_sdk.source_sync_pages import SourceMappingPage, SourceRunPage
from koinon_sdk.source_validation import (
    SourceMappingValidationAbandonInput,
    SourceMappingValidationContinueInput,
    SourceMappingValidationInput,
    SourceMappingValidationItemPage,
    SourceMappingValidationOutput,
)


class ContentSourcesClientMixin(ABC):
    async def reader_source_selection(self, tenant_id: str) -> ReaderSelectionOutput:
        return ReaderSelectionOutput.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/content-sources/reader-selection")
        )

    async def replace_reader_source_selection(
        self, tenant_id: str, value: ReaderSelectionInput
    ) -> ReaderSelectionOutput:
        """Replace this caller's selection; the server requires native browser authority."""
        return ReaderSelectionOutput.model_validate(
            await self._request(
                "PUT",
                self._tenant(tenant_id) + "/content-sources/reader-selection",
                json=value.model_dump(mode="json", exclude_none=True),
            )
        )

    @staticmethod
    @abstractmethod
    def _tenant(tenant_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    def _source_path(self, tenant_id: str, connection_id: str | None = None) -> str:
        root = self._tenant(tenant_id) + "/content-sources/connections"
        return root if connection_id is None else root + "/" + quote(connection_id, safe="")

    async def source_connections(
        self, tenant_id: str, *, cursor: str | None = None, limit: int = 25
    ) -> SourceConnectionPage:
        return SourceConnectionPage.model_validate(
            await self._request(
                "GET", self._source_path(tenant_id), params={"cursor": cursor, "limit": limit}
            )
        )

    async def source_connection(self, tenant_id: str, connection_id: str) -> SourceConnectionOutput:
        return SourceConnectionOutput.model_validate(
            await self._request("GET", self._source_path(tenant_id, connection_id))
        )

    async def disconnect_source_connection(
        self, tenant_id: str, connection_id: str, value: SourceConnectionRevision
    ) -> SourceConnectionOutput:
        return SourceConnectionOutput.model_validate(
            await self._request(
                "POST",
                self._source_path(tenant_id, connection_id) + "/disconnect",
                json=value.model_dump(mode="json"),
            )
        )

    async def source_sites(
        self, tenant_id: str, connection_id: str, q: str, *, cursor: str | None = None
    ) -> SourceLocationPage:
        return SourceLocationPage.model_validate(
            await self._request(
                "GET",
                self._source_path(tenant_id, connection_id) + "/sites",
                params={"q": q, "cursor": cursor},
            )
        )

    async def source_drives(
        self, tenant_id: str, connection_id: str, *, site_id: str | None = None, cursor: str | None = None
    ) -> SourceLocationPage:
        return SourceLocationPage.model_validate(
            await self._request(
                "GET",
                self._source_path(tenant_id, connection_id) + "/drives",
                params={"site_id": site_id, "cursor": cursor},
            )
        )

    async def source_children(
        self,
        tenant_id: str,
        connection_id: str,
        drive_id: str,
        *,
        folder_id: str | None = None,
        cursor: str | None = None,
    ) -> SourceFolderPage:
        return SourceFolderPage.model_validate(
            await self._request(
                "GET",
                self._source_path(tenant_id, connection_id) + "/children",
                params={"drive_id": drive_id, "folder_id": folder_id, "cursor": cursor},
            )
        )

    async def source_capabilities(self, tenant_id: str) -> SourceCapabilitiesOutput:
        return SourceCapabilitiesOutput.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/content-sources/capabilities")
        )

    async def source_mappings(
        self, tenant_id: str, *, limit: int = 25, cursor: str | None = None
    ) -> SourceMappingPage:
        return TypeAdapter(SourceMappingPage).validate_python(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/content-sources" + "/" + "mappings",
                params={"limit": limit, "cursor": cursor},
            )
        )

    async def source_mapping(self, tenant_id: str, mapping_id: str) -> SourceMappingOutput:
        return TypeAdapter(SourceMappingOutput).validate_python(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mappings"
                + "/"
                + quote(str(mapping_id), safe=""),
            )
        )

    async def source_mapping_runs(
        self, tenant_id: str, mapping_id: str, *, limit: int = 25, cursor: str | None = None
    ) -> SourceRunPage:
        return TypeAdapter(SourceRunPage).validate_python(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mappings"
                + "/"
                + quote(str(mapping_id), safe="")
                + "/"
                + "runs",
                params={"limit": limit, "cursor": cursor},
            )
        )

    async def source_initial_operation(
        self, tenant_id: str, operation_id: str, *, action: str
    ) -> SourceOperationReceipt:
        return TypeAdapter(SourceOperationReceipt).validate_python(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "operations"
                + "/"
                + quote(str(operation_id), safe=""),
                params={"action": action},
            )
        )

    async def source_operation(
        self, tenant_id: str, mapping_id: str, operation_id: str, *, action: str
    ) -> SourceOperationReceipt:
        return TypeAdapter(SourceOperationReceipt).validate_python(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mappings"
                + "/"
                + quote(str(mapping_id), safe="")
                + "/"
                + "operations"
                + "/"
                + quote(str(operation_id), safe=""),
                params={"action": action},
            )
        )

    async def source_run(self, tenant_id: str, run_id: str) -> SourceRunOutput:
        return TypeAdapter(SourceRunOutput).validate_python(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "runs"
                + "/"
                + quote(str(run_id), safe=""),
            )
        )

    async def source_run_items(
        self, tenant_id: str, run_id: str, *, limit: int = 25, cursor: str | None = None
    ) -> SourceRunItemPage:
        return TypeAdapter(SourceRunItemPage).validate_python(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "runs"
                + "/"
                + quote(str(run_id), safe="")
                + "/"
                + "items",
                params={"limit": limit, "cursor": cursor},
            )
        )

    async def cancel_source_run(
        self, tenant_id: str, run_id: str, value: SourceControlInput
    ) -> SourceControlOutput:
        return TypeAdapter(SourceControlOutput).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "runs"
                + "/"
                + quote(str(run_id), safe="")
                + "/"
                + "cancel",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def retry_source_run(
        self, tenant_id: str, run_id: str, value: SourceControlInput
    ) -> SourceControlOutput:
        return TypeAdapter(SourceControlOutput).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "runs"
                + "/"
                + quote(str(run_id), safe="")
                + "/"
                + "retry",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def review_source_mapping(
        self, tenant_id: str, value: SourcePolicyReviewInput
    ) -> SourcePolicyOperationOutput:
        return TypeAdapter(SourcePolicyOperationOutput).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/content-sources" + "/" + "mapping-reviews",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def source_review_items(
        self, tenant_id: str, review_id: str, *, limit: int = 25, cursor: str | None = None
    ) -> SourceReviewPage:
        return TypeAdapter(SourceReviewPage).validate_python(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mapping-reviews"
                + "/"
                + quote(str(review_id), safe="")
                + "/"
                + "items",
                params={"limit": limit, "cursor": cursor},
            )
        )

    async def create_source_mapping(
        self, tenant_id: str, value: SourcePolicyApplyInput
    ) -> SourcePolicyOperationOutput:
        return TypeAdapter(SourcePolicyOperationOutput).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/content-sources" + "/" + "mappings",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def revise_source_mapping(
        self, tenant_id: str, mapping_id: str, value: SourceExistingPolicyReviewInput
    ) -> SourcePolicyOperationOutput:
        return TypeAdapter(SourcePolicyOperationOutput).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mappings"
                + "/"
                + quote(str(mapping_id), safe="")
                + "/"
                + "reviews",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def apply_source_mapping(
        self, tenant_id: str, mapping_id: str, value: SourcePolicyApplyInput
    ) -> SourcePolicyOperationOutput:
        return TypeAdapter(SourcePolicyOperationOutput).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mappings"
                + "/"
                + quote(str(mapping_id), safe="")
                + "/"
                + "apply",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def sync_source_mapping(
        self, tenant_id: str, mapping_id: str, value: SourceControlInput
    ) -> SourceControlOutput:
        return TypeAdapter(SourceControlOutput).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mappings"
                + "/"
                + quote(str(mapping_id), safe="")
                + "/"
                + "sync",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def pause_source_mapping(
        self, tenant_id: str, mapping_id: str, value: SourceControlInput
    ) -> SourceControlOutput:
        return TypeAdapter(SourceControlOutput).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mappings"
                + "/"
                + quote(str(mapping_id), safe="")
                + "/"
                + "pause",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def resume_source_mapping(
        self, tenant_id: str, mapping_id: str, value: SourceControlInput
    ) -> SourceControlOutput:
        return TypeAdapter(SourceControlOutput).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mappings"
                + "/"
                + quote(str(mapping_id), safe="")
                + "/"
                + "resume",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def retire_source_mapping(
        self, tenant_id: str, mapping_id: str, value: SourceControlInput
    ) -> SourceControlOutput:
        return TypeAdapter(SourceControlOutput).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mappings"
                + "/"
                + quote(str(mapping_id), safe="")
                + "/"
                + "retire",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def begin_source_mapping_validation(
        self, tenant_id: str, value: SourceMappingValidationInput
    ) -> SourceMappingValidationOutput:
        return SourceMappingValidationOutput.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/content-sources" + "/" + "mapping-validations",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def source_mapping_validation_receipt(
        self, tenant_id: str, operation_id: str
    ) -> SourceMappingValidationOutput:
        return SourceMappingValidationOutput.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mapping-validations"
                + "/"
                + "operations"
                + "/"
                + quote(str(operation_id), safe=""),
            )
        )

    async def source_mapping_validation(
        self, tenant_id: str, validation_id: str
    ) -> SourceMappingValidationOutput:
        return SourceMappingValidationOutput.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mapping-validations"
                + "/"
                + quote(str(validation_id), safe=""),
            )
        )

    async def advance_source_mapping_validation(
        self, tenant_id: str, validation_id: str, value: SourceMappingValidationContinueInput
    ) -> SourceMappingValidationOutput:
        return SourceMappingValidationOutput.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mapping-validations"
                + "/"
                + quote(str(validation_id), safe="")
                + "/"
                + "continue",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )

    async def source_mapping_validation_items(
        self, tenant_id: str, validation_id: str, *, cursor: str | None = None, limit: int = 25
    ) -> SourceMappingValidationItemPage:
        return SourceMappingValidationItemPage.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mapping-validations"
                + "/"
                + quote(str(validation_id), safe="")
                + "/"
                + "items",
                params={"cursor": cursor, "limit": limit},
            )
        )

    async def abandon_source_mapping_validation(
        self, tenant_id: str, validation_id: str, value: SourceMappingValidationAbandonInput
    ) -> SourceMappingValidationOutput:
        return SourceMappingValidationOutput.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/content-sources"
                + "/"
                + "mapping-validations"
                + "/"
                + quote(str(validation_id), safe="")
                + "/"
                + "abandon",
                json=value.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
        )
