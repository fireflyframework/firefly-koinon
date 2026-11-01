# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import inspect
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Any, Literal, Self, Unpack, cast
from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import BaseModel, JsonValue, SecretStr, TypeAdapter

from koinon_sdk.activity import ActivitySummary, ActivityWindow
from koinon_sdk.answer_audit import AnswerAudit
from koinon_sdk.attachments import (
    AttachmentCapabilities,
    AttachmentPage,
    AttachmentPromotionInput,
    AttachmentPromotionView,
    AttachmentRevision,
    AttachmentView,
    PrivateChunkPage,
)
from koinon_sdk.authorized_applications import AuthorizedApplication
from koinon_sdk.availability import (
    AvailabilityRequest,
    AvailabilityResponse,
    ProcessingRequest,
    ProcessingResponse,
)
from koinon_sdk.bulk_client import BulkClientMixin
from koinon_sdk.communications_client import CommunicationsClientMixin
from koinon_sdk.connection_filters import (
    AttachmentChunkFilter,
    AttachmentFilter,
    ExportFilter,
    IdentityFilter,
    IdentityGroupFilter,
    IdentityMappingFilter,
    IndexFilter,
    IndexScope,
    ShareFilter,
)
from koinon_sdk.contracts import (
    AgentFilter,
    AuditFilter,
    AuthorizedApplicationFilter,
    BinaryDownload,
    CatalogFilter,
    ContentUpdate,
    Deleted,
    FolderCreate,
    FolderFilter,
    FolderPatch,
    InvitationFilter,
    KnowledgeConnection,
    KnowledgeConnectionInput,
    KnowledgeRoles,
    MemberInput,
    MembershipFilter,
    MemberUpdate,
    QueryContext,
    SearchContext,
    StatusFilter,
    ThreadFilter,
    ThreadPatch,
    TitleRequest,
    TitleSuggestion,
)
from koinon_sdk.coordinates import (
    CoordinateCellRequest,
    TableColumnBindingPage,
    TableCoordinateManifest,
    TableCoordinateSelection,
    TableRowRangePage,
)
from koinon_sdk.corporate_profiles import (
    CorporateProfileRefresh,
    CorporateProfileRefreshInput,
    OrganizationPresentation,
    OrganizationPresentationInput,
)
from koinon_sdk.curated import (
    KnowledgeCommitOutcome,
    KnowledgeConfirmation,
    KnowledgeIntent,
    KnowledgeIntentInput,
    KnowledgeItemPage,
    KnowledgeItemView,
)
from koinon_sdk.dataset_files import DatasetFileAppendResult
from koinon_sdk.document_history import (
    DocumentExtractionPage,
    DocumentPartContent,
    DocumentPartPage,
    DocumentVersion,
    DocumentVersionPage,
)
from koinon_sdk.evidence import EvidenceManifest
from koinon_sdk.exports import (
    Export,
    ExportCreate,
    ExportPage,
    ExportReview,
    ExportReviewInput,
    MessageSelection,
)
from koinon_sdk.external_file_reviews import (
    ExternalFileChunkInput,
    ExternalFileCleanupInput,
    ExternalFileCleanupResult,
    ExternalFileReviewInput,
    ExternalFileReviewView,
)
from koinon_sdk.external_reviews import ExternalReviewDecision, ExternalReviewInput, ExternalReviewView
from koinon_sdk.glossary import GlossaryPage, GlossaryTermCreate, GlossaryTermRead, GlossaryTermUpdate
from koinon_sdk.identity import (
    IdentityActivation,
    IdentityGroupPage,
    IdentityMapping,
    IdentityMappingInput,
    IdentityMappingPage,
    IdentityProvider,
    IdentityProviderInput,
    IdentityProviderPage,
    IdentityProviderPatch,
    IdentityRevision,
    IdentityValidation,
)
from koinon_sdk.indexes import (
    IndexActivateInput,
    IndexCreateInput,
    IndexJobView,
    IndexPage,
    IndexPlanInput,
    IndexPlanView,
    IndexRevisionInput,
    KnowledgeIndexView,
    NativeIndexChoice,
    NativeIndexPage,
)
from koinon_sdk.mcp import McpConnectionDescriptor
from koinon_sdk.mcp_applications import (
    McpOAuthClient,
    McpOAuthClientCredential,
    McpOAuthClientInput,
    McpOAuthClientPage,
    McpOAuthClientPatch,
    McpOAuthClientReadiness,
    McpOAuthClientRevision,
)
from koinon_sdk.models import (
    AgentConfiguration,
    AgentInput,
    AuditEvent,
    Capabilities,
    CatalogEntry,
    CatalogMove,
    ChatFolder,
    ChatMessage,
    ChatRun,
    ChatThread,
    Configuration,
    ContextResponse,
    DatasetSchema,
    DocumentChunks,
    EvidenceResult,
    Invitation,
    InvitationCreated,
    InvitationInput,
    InvitationPreview,
    Job,
    KnowledgeScope,
    Lineage,
    Membership,
    ModelProvider,
    Page,
    Person,
    PersonalToken,
    ProfileUpdate,
    ProviderInput,
    QueryResponse,
    RunInput,
    SearchResponse,
    TokenCreated,
    TokenInput,
    TokenScopeOptions,
    ToolActivity,
    UploadResponse,
    UserProfile,
    ValidationResult,
)
from koinon_sdk.organization_branding import (
    BrandingResetInput,
    BrandingValues,
    OrganizationBranding,
    OrganizationBrandingInput,
)
from koinon_sdk.organization_chat import OrganizationChatSettings, OrganizationChatSettingsInput
from koinon_sdk.organization_filters import (
    OrganizationPeopleFilter,
    OrganizationReportsFilter,
    OrganizationUnitFilter,
)
from koinon_sdk.organization_knowledge import (
    OrganizationKnowledgeSettings,
    OrganizationKnowledgeSettingsInput,
)
from koinon_sdk.organization_people import (
    OrganizationDirectorySettings,
    OrganizationDirectorySettingsInput,
    OrganizationPerson,
    OrganizationPersonCreate,
    OrganizationPersonPage,
    OrganizationPersonPatch,
    OrganizationProfileMapping,
    OrganizationProfileMappingInput,
    OrganizationUnit,
    OrganizationUnitInput,
    OrganizationUnitPage,
    OrganizationUnitPatch,
)
from koinon_sdk.proposals import CatalogProposal, ProposalConfirmation, ProposalRevision
from koinon_sdk.provenance import TableProvenance, TableSnapshotPage
from koinon_sdk.query_batch_client import QueryBatchClientMixin
from koinon_sdk.sharing import (
    Share,
    ShareCreate,
    SharedConversation,
    SharePage,
    ShareReview,
    ShareReviewInput,
)
from koinon_sdk.streaming import EventStream, read_events


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.request_id = status, code, request_id
        self.transaction_id = request_id


class KoinonClient(BulkClientMixin, QueryBatchClientMixin, CommunicationsClientMixin):
    def __init__(
        self,
        base_url: str,
        *,
        token_provider: Callable[[], str | Awaitable[str]],
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30,
    ) -> None:
        self._tokens = token_provider
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            transport=transport,
            timeout=timeout,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=10),
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    @staticmethod
    def _tenant(tenant_id: str) -> str:
        return "tenants/" + quote(tenant_id, safe="")

    async def _headers(self) -> dict[str, str]:
        token = self._tokens()
        if inspect.isawaitable(token):
            token = await token
        return {"Authorization": "Bearer " + self._require_token(token)}

    @staticmethod
    def _require_token(token: object) -> str:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("A caller-supplied bearer token is required")
        return token

    @staticmethod
    async def _check(response: httpx.Response) -> None:
        if response.is_success:
            return
        await response.aread()
        try:
            raw: object = response.json()
        except ValueError:
            raw = {}
        body = cast(dict[str, JsonValue], raw) if isinstance(raw, dict) else {}
        nested = body.get("error")
        legacy = cast(dict[str, JsonValue], nested) if isinstance(nested, dict) else {}
        reference = body.get("transactionId") or legacy.get("transaction_id") or body.get("request_id")
        request_id = (
            reference
            if isinstance(reference, str)
            else response.headers.get("X-Request-Id") or response.headers.get("X-Transaction-Id")
        )
        raise ApiError(
            response.status_code,
            str(body.get("code") or legacy.get("code") or "HTTP_ERROR"),
            str(
                body.get("detail")
                or legacy.get("message")
                or body.get("message")
                or body.get("title")
                or response.reason_phrase
            ),
            request_id,
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        headers.update(await self._headers())
        response = await self._http.request(method, path, headers=headers, **kwargs)
        await self._check(response)
        return response.json() if response.content else None

    async def context(self) -> ContextResponse:
        return ContextResponse.model_validate(await self._request("GET", "context"))

    async def delete(self, tenant_id: str, entry_id: str) -> None:
        await self._request("DELETE", self._tenant(tenant_id) + "/catalog/" + quote(entry_id, safe=""))

    async def add_member(self, tenant_id: str, value: MemberInput) -> Membership:
        return Membership.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/members",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def update_member(self, tenant_id: str, member_id: str, value: MemberUpdate) -> Membership:
        return Membership.model_validate(
            await self._request(
                "PATCH",
                self._tenant(tenant_id) + "/members/" + quote(member_id, safe=""),
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def remove_member(self, tenant_id: str, member_id: str) -> None:
        await self._request("DELETE", self._tenant(tenant_id) + "/members/" + quote(member_id, safe=""))

    async def job(self, tenant_id: str, job_id: str) -> Job:
        return Job.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/jobs/" + quote(job_id, safe=""))
        )

    async def cancel_job(self, tenant_id: str, job_id: str) -> Job:
        return Job.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/jobs/" + quote(job_id, safe="") + "/cancel"
            )
        )

    async def knowledge_roles(self, tenant_id: str, *, workspace_id: str | None = None) -> KnowledgeRoles:
        return KnowledgeRoles.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/knowledge-roles",
                params={"workspace_id": workspace_id} if workspace_id is not None else {},
            )
        )

    async def knowledge_connections(
        self, tenant_id: str, *, workspace_id: str | None = None
    ) -> Page[KnowledgeConnection]:
        return Page[KnowledgeConnection].model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/knowledge-connections",
                params={"workspace_id": workspace_id} if workspace_id is not None else {},
            )
        )

    async def knowledge_connection(self, tenant_id: str, connection_id: str) -> KnowledgeConnection:
        return KnowledgeConnection.model_validate(
            await self._request(
                "GET", self._tenant(tenant_id) + "/knowledge-connections/" + quote(connection_id, safe="")
            )
        )

    async def create_knowledge_connection(
        self, tenant_id: str, value: KnowledgeConnectionInput
    ) -> KnowledgeConnection:
        return KnowledgeConnection.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/knowledge-connections",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def update_knowledge_connection(
        self, tenant_id: str, connection_id: str, value: KnowledgeConnectionInput
    ) -> KnowledgeConnection:
        return KnowledgeConnection.model_validate(
            await self._request(
                "PUT",
                self._tenant(tenant_id) + "/knowledge-connections/" + quote(connection_id, safe=""),
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def delete_knowledge_connection(
        self, tenant_id: str, connection_id: str, *, expected_revision: int
    ) -> Deleted:
        return Deleted.model_validate(
            await self._request(
                "DELETE",
                self._tenant(tenant_id) + "/knowledge-connections/" + quote(connection_id, safe=""),
                params={"expected_revision": expected_revision},
            )
        )

    async def _download(
        self, path: str, *, params: dict[str, str] | None = None, if_none_match: str | None = None
    ) -> BinaryDownload:
        headers = await self._headers()
        if if_none_match is not None:
            headers["If-None-Match"] = if_none_match
        response = await self._http.get(path, headers=headers, params=params)
        if response.status_code != 304:
            await self._check(response)
        disposition = response.headers.get("Content-Disposition", "")
        from email.message import Message

        message = Message()
        message["Content-Disposition"] = disposition
        filename = message.get_filename()
        return BinaryDownload(
            response.content,
            response.headers.get("Content-Type"),
            response.headers.get("ETag"),
            filename,
            response.status_code == 304,
        )

    async def document_download(self, tenant_id: str, document_id: str) -> BinaryDownload:
        return await self._download(
            self._tenant(tenant_id) + "/documents/" + quote(document_id, safe="") + "/original"
        )

    async def person_avatar(
        self,
        tenant_id: str,
        profile_id: str,
        *,
        workspace_id: str | None = None,
        if_none_match: str | None = None,
    ) -> BinaryDownload:
        return await self._download(
            self._tenant(tenant_id) + "/people/" + quote(profile_id, safe="") + "/avatar",
            params={"workspace_id": workspace_id} if workspace_id is not None else None,
            if_none_match=if_none_match,
        )

    async def avatar_download(self, *, if_none_match: str | None = None) -> BinaryDownload:
        return await self._download("profile/avatar", if_none_match=if_none_match)

    @staticmethod
    def _precondition(value: str) -> dict[str, str]:
        if not value or any(character in value for character in ('"', "\r", "\n")):
            raise ValueError("Supply the unquoted current content digest or snapshot ID")
        return {"If-Match": '"' + value + '"'}

    @staticmethod
    def _document_revision(version: str | None, extraction: str | None) -> dict[str, str]:
        if (version is None) != (extraction is None):
            raise ValueError("Supply the exact source version and extraction together")
        if version is None or extraction is None:
            return {}
        return {"X-Koinon-Source-Version": str(UUID(version)), "X-Koinon-Extraction": str(UUID(extraction))}

    async def replace_document(
        self,
        tenant_id: str,
        document_id: str,
        *,
        filename: str,
        content: bytes,
        expected_sha256: str,
        acknowledge_chunk_invalidation: bool = False,
        expected_source_version_id: str | None = None,
        expected_extraction_id: str | None = None,
    ) -> ContentUpdate:
        return ContentUpdate.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/documents/" + quote(document_id, safe="") + "/content",
                headers={
                    **self._precondition(expected_sha256),
                    **self._document_revision(expected_source_version_id, expected_extraction_id),
                },
                files={"file": (filename, content)},
                data={"acknowledge_chunk_invalidation": str(acknowledge_chunk_invalidation).lower()},
            )
        )

    async def reingest_document(
        self,
        tenant_id: str,
        document_id: str,
        *,
        expected_sha256: str,
        acknowledge_chunk_invalidation: bool = False,
        expected_source_version_id: str | None = None,
        expected_extraction_id: str | None = None,
    ) -> ContentUpdate:
        return ContentUpdate.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/documents/" + quote(document_id, safe="") + "/reingest",
                headers={
                    **self._precondition(expected_sha256),
                    **self._document_revision(expected_source_version_id, expected_extraction_id),
                },
                json={"acknowledge_chunk_invalidation": acknowledge_chunk_invalidation},
            )
        )

    async def replace_table(
        self,
        tenant_id: str,
        dataset_id: str,
        table_id: str,
        *,
        filename: str,
        content: bytes,
        expected_snapshot_id: str,
    ) -> ContentUpdate:
        return ContentUpdate.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/datasets/"
                + quote(dataset_id, safe="")
                + "/tables/"
                + quote(table_id, safe="")
                + "/content",
                headers=self._precondition(expected_snapshot_id),
                files={"file": (filename, content)},
            )
        )

    async def reingest_table(
        self, tenant_id: str, dataset_id: str, table_id: str, *, expected_snapshot_id: str
    ) -> ContentUpdate:
        return ContentUpdate.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/datasets/"
                + quote(dataset_id, safe="")
                + "/tables/"
                + quote(table_id, safe="")
                + "/reingest",
                headers=self._precondition(expected_snapshot_id),
                json={},
            )
        )

    async def catalog(self, tenant_id: str, **filters: Unpack[CatalogFilter]) -> Page[CatalogEntry]:
        return Page[CatalogEntry].model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/catalog", params=filters)
        )

    async def get(self, tenant_id: str, entry_id: str) -> CatalogEntry:
        return CatalogEntry.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/catalog/" + quote(entry_id, safe=""))
        )

    async def create(
        self,
        tenant_id: str,
        *,
        kind: str,
        name: str,
        parent_id: str | None = None,
        description: str = "",
        metadata: dict[str, JsonValue] | None = None,
    ) -> CatalogEntry:
        body: dict[str, Any] = {
            "kind": kind,
            "name": name,
            "description": description,
            "metadata": metadata or {},
        }
        if parent_id is not None:
            body["parent_id"] = parent_id
        return CatalogEntry.model_validate(
            await self._request("POST", self._tenant(tenant_id) + "/catalog", json=body)
        )

    async def update(
        self,
        tenant_id: str,
        entry_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        metadata: dict[str, JsonValue] | None = None,
    ) -> CatalogEntry:
        fields = {
            key: value
            for key, value in {
                "name": name,
                "description": description,
                "metadata": metadata,
            }.items()
            if value is not None
        }
        return CatalogEntry.model_validate(
            await self._request(
                "PATCH", self._tenant(tenant_id) + "/catalog/" + quote(entry_id, safe=""), json=fields
            )
        )

    async def move(self, tenant_id: str, entry_id: str, input: CatalogMove) -> CatalogEntry:
        return CatalogEntry.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/catalog/" + quote(entry_id, safe="") + "/move",
                json=input.model_dump(mode="json"),
            )
        )

    async def archive(self, tenant_id: str, entry_id: str) -> CatalogEntry:
        return CatalogEntry.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/catalog/" + quote(entry_id, safe="") + "/archive"
            )
        )

    async def restore(self, tenant_id: str, entry_id: str) -> CatalogEntry:
        return CatalogEntry.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/catalog/" + quote(entry_id, safe="") + "/restore"
            )
        )

    async def search(self, tenant_id: str, question: str, **context: Unpack[SearchContext]) -> SearchResponse:
        return SearchResponse.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/search", json={"question": question, **context}
            )
        )

    async def query(
        self, tenant_id: str, dataset_id: str, question: str = "", **context: Unpack[QueryContext]
    ) -> QueryResponse:
        return QueryResponse.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/query",
                json={"dataset_id": dataset_id, "question": question, **context},
            )
        )

    async def capabilities(self) -> Capabilities:
        return Capabilities.model_validate(await self._request("GET", "capabilities"))

    async def schema(self, tenant_id: str, dataset_id: str) -> DatasetSchema:
        return DatasetSchema.model_validate(
            await self._request(
                "GET", self._tenant(tenant_id) + "/datasets/" + quote(dataset_id, safe="") + "/schema"
            )
        )

    async def lineage(self, tenant_id: str, asset_id: str | None = None) -> Lineage:
        return Lineage.model_validate(
            await self._request(
                "GET", self._tenant(tenant_id) + "/lineage", params={"asset_id": asset_id} if asset_id else {}
            )
        )

    def _table(self, tenant_id: str, dataset_id: str, table_id: str) -> str:
        return (
            self._tenant(tenant_id)
            + "/datasets/"
            + quote(dataset_id, safe="")
            + "/tables/"
            + quote(table_id, safe="")
        )

    async def preview_knowledge(self, tenant_id: str, value: KnowledgeIntentInput) -> KnowledgeIntent:
        return KnowledgeIntent.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/knowledge-intents",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def cleanup_external_file_reviews(
        self, tenant_id: str, value: ExternalFileCleanupInput
    ) -> ExternalFileCleanupResult:
        return ExternalFileCleanupResult.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/external-file-reviews/cleanup",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def stage_external_file_review(
        self, tenant_id: str, value: ExternalFileReviewInput, *, idempotency_key: str
    ) -> ExternalFileReviewView:
        return ExternalFileReviewView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/external-file-reviews",
                json=value.model_dump(mode="json", exclude_unset=True),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def external_file_review(self, tenant_id: str, review_id: str) -> ExternalFileReviewView:
        return ExternalFileReviewView.model_validate(
            await self._request(
                "GET", self._tenant(tenant_id) + "/external-file-reviews/" + quote(review_id, safe="")
            )
        )

    async def upload_external_file_chunk(
        self, tenant_id: str, review_id: str, value: ExternalFileChunkInput
    ) -> ExternalFileReviewView:
        return ExternalFileReviewView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/external-file-reviews/" + quote(review_id, safe="") + "/chunks",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def seal_external_file_review(self, tenant_id: str, review_id: str) -> ExternalFileReviewView:
        return ExternalFileReviewView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/external-file-reviews/" + quote(review_id, safe="") + "/seal",
            )
        )

    async def approve_external_file_review(
        self, tenant_id: str, review_id: str, value: ExternalReviewDecision, *, idempotency_key: str
    ) -> ExternalFileReviewView:
        return ExternalFileReviewView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/external-file-reviews/" + quote(review_id, safe="") + "/approve",
                json=value.model_dump(mode="json", exclude_unset=True),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def cancel_external_file_review(
        self, tenant_id: str, review_id: str, value: ExternalReviewDecision
    ) -> ExternalFileReviewView:
        return ExternalFileReviewView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/external-file-reviews/" + quote(review_id, safe="") + "/cancel",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def mcp_connection(self) -> McpConnectionDescriptor:
        return McpConnectionDescriptor.model_validate(await self._request("GET", "/mcp/connection"))

    async def organization_mcp_connection(self, tenant_id: str) -> McpConnectionDescriptor:
        return McpConnectionDescriptor.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/mcp/connection")
        )

    async def mcp_oauth_clients_readiness(self, tenant_id: str) -> McpOAuthClientReadiness:
        return McpOAuthClientReadiness.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/mcp/oauth-clients/readiness")
        )

    async def mcp_oauth_clients(
        self,
        tenant_id: str,
        *,
        q: str = "",
        status: Literal["all", "enabled", "disabled"] = "all",
        page: int = 1,
        page_size: int = 25,
        sort: Literal["name", "updated_at"] = "name",
        order: Literal["asc", "desc"] = "asc",
    ) -> McpOAuthClientPage:
        return McpOAuthClientPage.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/mcp/oauth-clients",
                params={
                    "q": q,
                    "status": status,
                    "page": page,
                    "page_size": page_size,
                    "sort": sort,
                    "order": order,
                },
            )
        )

    async def create_mcp_oauth_client(
        self,
        tenant_id: str,
        value: McpOAuthClientInput,
    ) -> McpOAuthClientCredential:
        return McpOAuthClientCredential.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/mcp/oauth-clients",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def mcp_oauth_client(self, tenant_id: str, client_id: str) -> McpOAuthClient:
        return McpOAuthClient.model_validate(
            await self._request(
                "GET", self._tenant(tenant_id) + "/mcp/oauth-clients/" + quote(client_id, safe="")
            )
        )

    async def update_mcp_oauth_client(
        self,
        tenant_id: str,
        client_id: str,
        value: McpOAuthClientPatch,
    ) -> McpOAuthClient:
        return McpOAuthClient.model_validate(
            await self._request(
                "PATCH",
                self._tenant(tenant_id) + "/mcp/oauth-clients/" + quote(client_id, safe=""),
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def rotate_mcp_oauth_client_secret(
        self,
        tenant_id: str,
        client_id: str,
        value: McpOAuthClientRevision,
    ) -> McpOAuthClientCredential:
        return McpOAuthClientCredential.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/mcp/oauth-clients/"
                + quote(client_id, safe="")
                + "/rotate-secret",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def stage_external_review(
        self, tenant_id: str, value: ExternalReviewInput, *, idempotency_key: str
    ) -> ExternalReviewView:
        return ExternalReviewView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/external-knowledge-reviews",
                json=value.model_dump(mode="json", exclude_unset=True),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def external_review(self, tenant_id: str, review_id: str) -> ExternalReviewView:
        return ExternalReviewView.model_validate(
            await self._request(
                "GET", self._tenant(tenant_id) + "/external-knowledge-reviews/" + quote(review_id, safe="")
            )
        )

    async def approve_external_review(
        self, tenant_id: str, review_id: str, value: ExternalReviewDecision, *, idempotency_key: str
    ) -> KnowledgeCommitOutcome:
        return TypeAdapter(KnowledgeCommitOutcome).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/external-knowledge-reviews/"
                + quote(review_id, safe="")
                + "/approve",
                json=value.model_dump(mode="json", exclude_unset=True),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def cancel_external_review(
        self, tenant_id: str, review_id: str, value: ExternalReviewDecision
    ) -> ExternalReviewView:
        return ExternalReviewView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/external-knowledge-reviews/"
                + quote(review_id, safe="")
                + "/cancel",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def knowledge_intent(self, tenant_id: str, intent_id: str) -> KnowledgeIntent:
        return KnowledgeIntent.model_validate(
            await self._request(
                "GET", self._tenant(tenant_id) + "/knowledge-intents/" + quote(intent_id, safe="")
            )
        )

    async def confirm_knowledge(
        self, tenant_id: str, intent_id: str, value: KnowledgeConfirmation, *, idempotency_key: str
    ) -> KnowledgeCommitOutcome:
        return TypeAdapter(KnowledgeCommitOutcome).validate_python(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/knowledge-intents/" + quote(intent_id, safe="") + "/confirm",
                json=value.model_dump(mode="json", exclude_unset=True),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def cancel_knowledge(
        self, tenant_id: str, intent_id: str, *, expected_revision: int
    ) -> KnowledgeIntent:
        return KnowledgeIntent.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/knowledge-intents/" + quote(intent_id, safe="") + "/cancel",
                json={"expected_revision": expected_revision},
            )
        )

    async def knowledge_items(
        self,
        tenant_id: str,
        *,
        workspace_id: str | None = None,
        project_id: str | None = None,
        destination_id: str | None = None,
        q: str = "",
        page: int = 1,
        page_size: int = 25,
    ) -> KnowledgeItemPage:
        params = {
            key: value
            for key, value in {
                "workspace_id": workspace_id,
                "project_id": project_id,
                "destination_id": destination_id,
                "q": q,
                "page": page,
                "page_size": page_size,
            }.items()
            if value is not None
        }
        return KnowledgeItemPage.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/knowledge-items", params=params)
        )

    async def knowledge_item(self, tenant_id: str, item_id: str) -> KnowledgeItemView:
        return KnowledgeItemView.model_validate(
            await self._request(
                "GET", self._tenant(tenant_id) + "/knowledge-items/" + quote(item_id, safe="")
            )
        )

    async def knowledge_version(self, tenant_id: str, item_id: str, version: int) -> KnowledgeItemView:
        return KnowledgeItemView.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/knowledge-items/"
                + quote(item_id, safe="")
                + "/versions/"
                + str(version),
            )
        )

    async def table_coordinates(
        self, tenant_id: str, dataset_id: str, table_id: str, *, snapshot_id: str
    ) -> TableCoordinateManifest:
        return TableCoordinateManifest.model_validate(
            await self._request(
                "GET",
                self._table(tenant_id, dataset_id, table_id) + "/coordinates",
                params={"snapshot_id": snapshot_id},
            )
        )

    async def table_coordinate_cells(
        self, tenant_id: str, dataset_id: str, table_id: str, value: CoordinateCellRequest
    ) -> TableCoordinateSelection:
        return TableCoordinateSelection.model_validate(
            await self._request(
                "POST",
                self._table(tenant_id, dataset_id, table_id) + "/coordinates/cells",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def table_coordinate_rows(
        self,
        tenant_id: str,
        dataset_id: str,
        table_id: str,
        *,
        snapshot_id: str,
        page: int = 1,
        page_size: int = 25,
    ) -> TableRowRangePage:
        return TableRowRangePage.model_validate(
            await self._request(
                "GET",
                self._table(tenant_id, dataset_id, table_id) + "/coordinates/rows",
                params={"snapshot_id": snapshot_id, "page": page, "page_size": page_size},
            )
        )

    async def table_coordinate_columns(
        self,
        tenant_id: str,
        dataset_id: str,
        table_id: str,
        *,
        snapshot_id: str,
        page: int = 1,
        page_size: int = 25,
    ) -> TableColumnBindingPage:
        return TableColumnBindingPage.model_validate(
            await self._request(
                "GET",
                self._table(tenant_id, dataset_id, table_id) + "/coordinates/columns",
                params={"snapshot_id": snapshot_id, "page": page, "page_size": page_size},
            )
        )

    async def table_provenance(
        self, tenant_id: str, dataset_id: str, table_id: str, *, snapshot_id: str
    ) -> TableProvenance:
        return TableProvenance.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/datasets/"
                + quote(dataset_id, safe="")
                + "/tables/"
                + quote(table_id, safe="")
                + "/provenance",
                params={"snapshot_id": snapshot_id},
            )
        )

    async def table_snapshots(
        self, tenant_id: str, dataset_id: str, table_id: str, *, page: int = 1, page_size: int = 25
    ) -> TableSnapshotPage:
        return TableSnapshotPage.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/datasets/"
                + quote(dataset_id, safe="")
                + "/tables/"
                + quote(table_id, safe="")
                + "/snapshots",
                params={"page": page, "page_size": page_size},
            )
        )

    async def knowledge_availability(self, tenant_id: str, body: AvailabilityRequest) -> AvailabilityResponse:
        return AvailabilityResponse.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/catalog/availability",
                json=body.model_dump(mode="json", exclude_none=True),
            )
        )

    async def knowledge_processing(self, tenant_id: str, body: ProcessingRequest) -> ProcessingResponse:
        return ProcessingResponse.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/knowledge-processing",
                json=body.model_dump(mode="json", exclude_none=True),
            )
        )

    def _document_version_path(
        self, tenant_id: str, document_id: str, source_version_id: str | None = None
    ) -> str:
        path = self._tenant(tenant_id) + "/documents/" + quote(document_id, safe="") + "/versions"
        return path + "/" + quote(source_version_id, safe="") if source_version_id is not None else path

    async def document_versions(
        self,
        tenant_id: str,
        document_id: str,
        *,
        page: int = 1,
        page_size: int = 25,
    ) -> DocumentVersionPage:
        return DocumentVersionPage.model_validate(
            await self._request(
                "GET",
                self._document_version_path(tenant_id, document_id),
                params={"page": page, "page_size": page_size},
            )
        )

    async def document_version(
        self,
        tenant_id: str,
        document_id: str,
        source_version_id: str,
    ) -> DocumentVersion:
        return DocumentVersion.model_validate(
            await self._request(
                "GET",
                self._document_version_path(tenant_id, document_id, source_version_id),
            )
        )

    async def document_extractions(
        self,
        tenant_id: str,
        document_id: str,
        source_version_id: str,
        *,
        page: int = 1,
        page_size: int = 25,
    ) -> DocumentExtractionPage:
        return DocumentExtractionPage.model_validate(
            await self._request(
                "GET",
                self._document_version_path(tenant_id, document_id, source_version_id) + "/extractions",
                params={"page": page, "page_size": page_size},
            )
        )

    async def document_parts(
        self,
        tenant_id: str,
        document_id: str,
        source_version_id: str,
        extraction_id: str,
        *,
        kind: Literal["artifact", "section", "chunk", "page"] | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> DocumentPartPage:
        filters: dict[str, int | str] = {"page": page, "page_size": page_size}
        if kind is not None:
            filters["kind"] = kind
        return DocumentPartPage.model_validate(
            await self._request(
                "GET",
                self._document_version_path(tenant_id, document_id, source_version_id)
                + "/extractions/"
                + quote(extraction_id, safe="")
                + "/parts",
                params=filters,
            )
        )

    async def document_part(
        self,
        tenant_id: str,
        document_id: str,
        source_version_id: str,
        extraction_id: str,
        source_part_id: str,
    ) -> DocumentPartContent:
        return DocumentPartContent.model_validate(
            await self._request(
                "GET",
                self._document_version_path(tenant_id, document_id, source_version_id)
                + "/extractions/"
                + quote(extraction_id, safe="")
                + "/parts/"
                + quote(source_part_id, safe=""),
            )
        )

    async def document_version_original(
        self,
        tenant_id: str,
        document_id: str,
        source_version_id: str,
    ) -> BinaryDownload:
        return await self._download(
            self._document_version_path(tenant_id, document_id, source_version_id) + "/original",
        )

    async def document_chunks(
        self,
        tenant_id: str,
        document_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
        page: int | None = None,
        section: str | None = None,
        q: str | None = None,
    ) -> DocumentChunks:
        filters = {
            key: value
            for key, value in {
                "offset": offset,
                "limit": limit,
                "page": page,
                "section": section,
                "q": q,
            }.items()
            if value is not None
        }
        return DocumentChunks.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/documents/" + quote(document_id, safe="") + "/chunks",
                params=filters,
            )
        )

    async def document_original(self, tenant_id: str, document_id: str) -> bytes:
        response = await self._http.get(
            self._tenant(tenant_id) + "/documents/" + quote(document_id, safe="") + "/original",
            headers=await self._headers(),
        )
        await self._check(response)
        return response.content

    async def audit(self, tenant_id: str, **filters: Unpack[AuditFilter]) -> Page[AuditEvent]:
        return Page[AuditEvent].model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/audit", params=dict(filters))
        )

    async def members(self, tenant_id: str, **filters: Unpack[MembershipFilter]) -> Page[Membership]:
        return Page[Membership].model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/members",
                params={key: value for key, value in filters.items() if value is not None},
            )
        )

    async def invitations(self, tenant_id: str, **filters: Unpack[InvitationFilter]) -> Page[Invitation]:
        return Page[Invitation].model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/invitations", params=dict(filters))
        )

    async def create_invitation(self, tenant_id: str, value: InvitationInput) -> InvitationCreated:
        return InvitationCreated.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/invitations", json=value.model_dump(exclude_unset=True)
            )
        )

    async def revoke_invitation(self, tenant_id: str, invitation_id: str) -> None:
        await self._request(
            "DELETE", self._tenant(tenant_id) + "/invitations/" + quote(invitation_id, safe="")
        )

    async def inspect_invitation(self, token: str) -> InvitationPreview:
        return InvitationPreview.model_validate(
            await self._request("POST", "/invitations/inspect", json={"token": token})
        )

    async def redeem_invitation(self, token: str) -> Membership:
        return Membership.model_validate(
            await self._request("POST", "/invitations/redeem", json={"token": token})
        )

    async def jobs(self, tenant_id: str) -> Page[Job]:
        return Page[Job].model_validate(await self._request("GET", self._tenant(tenant_id) + "/jobs"))

    async def upload(
        self,
        tenant_id: str,
        *,
        filename: str,
        content: bytes,
        parent_id: str,
        workspace_id: str,
        project_id: str,
        mode: Literal["document", "dataset"],
    ) -> UploadResponse:
        return UploadResponse.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/sources/upload",
                files={"file": (filename, content)},
                data={
                    "parent_id": parent_id,
                    "workspace_id": workspace_id,
                    "project_id": project_id,
                    "mode": mode,
                },
            )
        )

    async def append_dataset_file(
        self, tenant_id: str, dataset_id: str, *, filename: str, content: bytes, idempotency_key: str
    ) -> DatasetFileAppendResult:
        return DatasetFileAppendResult.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/datasets/" + quote(dataset_id, safe="") + "/files",
                files={"file": (filename, content)},
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def configuration(self, tenant_id: str) -> Configuration:
        return Configuration.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/configuration")
        )

    @staticmethod
    def _input(value: BaseModel) -> dict[str, JsonValue]:
        from datetime import datetime
        from uuid import UUID

        def wire(item: object) -> JsonValue:
            if isinstance(item, SecretStr):
                return item.get_secret_value()
            if isinstance(item, BaseModel):
                return wire(item.model_dump(mode="python", exclude_unset=True))
            if isinstance(item, dict):
                mapping = cast(dict[str, object], item)
                return {key: wire(value) for key, value in mapping.items()}
            if isinstance(item, (list, tuple)):
                return [wire(value) for value in cast(list[object], item)]
            if isinstance(item, (datetime, UUID)):
                return str(item.isoformat() if isinstance(item, datetime) else item)
            if item is None or isinstance(item, (str, bool, int, float)):
                return item
            raise TypeError("Use explicit exact-value helpers for non-JSON values")

        return cast(dict[str, JsonValue], wire(value))

    async def create_provider(self, tenant_id: str, value: ProviderInput) -> ModelProvider:
        return ModelProvider.model_validate(
            await self._request("POST", self._tenant(tenant_id) + "/providers", json=self._input(value))
        )

    async def update_provider(self, tenant_id: str, provider_id: str, value: ProviderInput) -> ModelProvider:
        return ModelProvider.model_validate(
            await self._request(
                "PUT",
                self._tenant(tenant_id) + "/providers/" + quote(provider_id, safe=""),
                json=self._input(value),
            )
        )

    async def validate_provider(self, tenant_id: str, provider_id: str) -> ValidationResult:
        return ValidationResult.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/providers/" + quote(provider_id, safe="") + "/validate"
            )
        )

    async def agents(self, tenant_id: str, **filters: Unpack[AgentFilter]) -> Page[AgentConfiguration]:
        return Page[AgentConfiguration].model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/agents", params=filters)
        )

    async def create_agent(self, tenant_id: str, value: AgentInput) -> AgentConfiguration:
        return AgentConfiguration.model_validate(
            await self._request("POST", self._tenant(tenant_id) + "/agents", json=self._input(value))
        )

    async def update_agent(self, tenant_id: str, agent_id: str, value: AgentInput) -> AgentConfiguration:
        return AgentConfiguration.model_validate(
            await self._request(
                "PATCH",
                self._tenant(tenant_id) + "/agents/" + quote(agent_id, safe=""),
                json=self._input(value),
            )
        )

    async def validate_agent(self, tenant_id: str, agent_id: str) -> AgentConfiguration:
        return AgentConfiguration.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/agents/" + quote(agent_id, safe="") + "/validate"
            )
        )

    async def threads(self, tenant_id: str, **filters: Unpack[ThreadFilter]) -> Page[ChatThread]:
        return Page[ChatThread].model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/chat/threads", params=filters)
        )

    async def create_thread(
        self,
        tenant_id: str,
        *,
        title: str | None = None,
        scope: KnowledgeScope | None = None,
        folder_id: str | None = None,
    ) -> ChatThread:
        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if folder_id is not None:
            body["folder_id"] = folder_id
        if scope is not None:
            body["scope"] = scope.model_dump(exclude_none=True)
        return ChatThread.model_validate(
            await self._request("POST", self._tenant(tenant_id) + "/chat/threads", json=body)
        )

    async def thread(self, tenant_id: str, thread_id: str) -> ChatThread:
        return ChatThread.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/chat/threads/" + quote(thread_id, safe=""))
        )

    async def update_thread(self, tenant_id: str, thread_id: str, value: ThreadPatch) -> ChatThread:
        return ChatThread.model_validate(
            await self._request(
                "PATCH",
                self._tenant(tenant_id) + "/chat/threads/" + quote(thread_id, safe=""),
                json=self._input(value),
            )
        )

    async def suggest_title(self, tenant_id: str, thread_id: str, value: TitleRequest) -> TitleSuggestion:
        return TitleSuggestion.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/chat/threads/" + quote(thread_id, safe="") + "/title-suggestion",
                json=self._input(value),
            )
        )

    async def delete_thread(self, tenant_id: str, thread_id: str, *, expected_revision: int) -> None:
        await self._request(
            "DELETE",
            self._tenant(tenant_id) + "/chat/threads/" + quote(thread_id, safe=""),
            params={"expected_revision": expected_revision},
        )

    async def folders(self, tenant_id: str, **filters: Unpack[FolderFilter]) -> Page[ChatFolder]:
        return Page[ChatFolder].model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/chat/folders", params=filters)
        )

    async def folder(self, tenant_id: str, folder_id: str) -> ChatFolder:
        return ChatFolder.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/chat/folders/" + quote(folder_id, safe=""))
        )

    async def create_folder(self, tenant_id: str, value: FolderCreate) -> ChatFolder:
        return ChatFolder.model_validate(
            await self._request("POST", self._tenant(tenant_id) + "/chat/folders", json=self._input(value))
        )

    async def update_folder(self, tenant_id: str, folder_id: str, value: FolderPatch) -> ChatFolder:
        return ChatFolder.model_validate(
            await self._request(
                "PATCH",
                self._tenant(tenant_id) + "/chat/folders/" + quote(folder_id, safe=""),
                json=self._input(value),
            )
        )

    async def delete_folder(self, tenant_id: str, folder_id: str, *, expected_revision: int) -> None:
        await self._request(
            "DELETE",
            self._tenant(tenant_id) + "/chat/folders/" + quote(folder_id, safe=""),
            params={"expected_revision": expected_revision},
        )

    async def messages(
        self, tenant_id: str, thread_id: str, *, before: str | None = None, limit: int = 50
    ) -> Page[ChatMessage]:
        return Page[ChatMessage].model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/chat/threads/" + quote(thread_id, safe="") + "/messages",
                params={"limit": limit, **({"before": before} if before is not None else {})},
            )
        )

    async def submit_run(self, tenant_id: str, thread_id: str, value: RunInput) -> ChatRun:
        return ChatRun.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/chat/threads/" + quote(thread_id, safe="") + "/runs",
                json=self._input(value),
            )
        )

    async def cancel_run(self, tenant_id: str, run_id: str) -> ChatRun:
        return ChatRun.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/chat/runs/" + quote(run_id, safe="") + "/cancel"
            )
        )

    async def retry_run(self, tenant_id: str, run_id: str) -> ChatRun:
        return ChatRun.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/chat/runs/" + quote(run_id, safe="") + "/retry"
            )
        )

    async def result(self, tenant_id: str, run_id: str, result_id: str) -> EvidenceResult:
        return EvidenceResult.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + "/chat/runs/"
                + quote(run_id, safe="")
                + "/results/"
                + quote(result_id, safe=""),
            )
        )

    def events(self, tenant_id: str, run_id: str, *, last_event_id: str | None = None) -> EventStream:
        return EventStream(self._events(tenant_id, run_id, last_event_id))

    async def _events(self, tenant_id: str, run_id: str, last_event_id: str | None):
        headers = await self._headers()
        headers["Accept"] = "text/event-stream"
        if last_event_id is not None:
            if any(character in last_event_id for character in "\r\n\0"):
                raise ValueError("Last-Event-ID cannot contain line breaks or NUL")
            headers["Last-Event-ID"] = last_event_id
        path = self._tenant(tenant_id) + "/chat/runs/" + quote(run_id, safe="") + "/events"
        async with self._http.stream("GET", path, headers=headers) as response:
            await self._check(response)
            if response.headers.get("Content-Type", "").split(";")[0].strip() != "text/event-stream":
                raise ValueError("Expected a text/event-stream response")
            async for event in read_events(response):
                yield event

    async def profile(self) -> UserProfile:
        return UserProfile.model_validate(await self._request("GET", "profile"))

    async def update_profile(self, value: ProfileUpdate) -> UserProfile:
        return UserProfile.model_validate(
            await self._request("PATCH", "profile", json=value.model_dump(exclude_unset=True))
        )

    async def set_avatar(self, content: bytes, *, media_type: str) -> UserProfile:
        return UserProfile.model_validate(
            await self._request(
                "POST", "profile/avatar", content=content, headers={"Content-Type": media_type}
            )
        )

    async def delete_avatar(self) -> UserProfile:
        return UserProfile.model_validate(await self._request("DELETE", "profile/avatar"))

    async def avatar(self) -> bytes:
        response = await self._http.get("profile/avatar", headers=await self._headers())
        await self._check(response)
        if response.headers.get("Content-Type", "").split(";")[0].strip() != "image/jpeg":
            raise ValueError("Expected a sanitized image/jpeg avatar")
        return response.content

    async def people(
        self,
        tenant_id: str,
        *,
        workspace_id: str | None = None,
        q: str = "",
        limit: int = 20,
        after: str | None = None,
    ) -> Page[Person]:
        filters = {
            key: value
            for key, value in {"workspace_id": workspace_id, "q": q, "limit": limit, "after": after}.items()
            if value is not None
        }
        return Page[Person].model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/people", params=filters)
        )

    async def organization_presentation(
        self, tenant_id: str, *, workspace_id: str | None = None
    ) -> OrganizationPresentation:
        return OrganizationPresentation.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/organization/people/me/presentation",
                params={"workspace_id": workspace_id} if workspace_id is not None else {},
            )
        )

    async def update_organization_presentation(
        self, tenant_id: str, value: OrganizationPresentationInput, *, workspace_id: str | None = None
    ) -> OrganizationPresentation:
        return OrganizationPresentation.model_validate(
            await self._request(
                "PATCH",
                self._tenant(tenant_id) + "/organization/people/me/presentation",
                json=value.model_dump(mode="json", exclude_unset=True),
                params={"workspace_id": workspace_id} if workspace_id is not None else {},
            )
        )

    async def refresh_organization_profile(
        self,
        tenant_id: str,
        value: CorporateProfileRefreshInput | None = None,
        *,
        workspace_id: str | None = None,
    ) -> CorporateProfileRefresh:
        return CorporateProfileRefresh.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/organization/people/me/profile-refresh",
                json=(value or CorporateProfileRefreshInput()).model_dump(mode="json", exclude_unset=True),
                params={"workspace_id": workspace_id} if workspace_id is not None else {},
            )
        )

    async def refresh_organization_person_profile(
        self,
        tenant_id: str,
        person_id: str,
        value: CorporateProfileRefreshInput | None = None,
        *,
        workspace_id: str | None = None,
    ) -> CorporateProfileRefresh:
        return CorporateProfileRefresh.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/organization/people/"
                + quote(person_id, safe="")
                + "/profile-refresh",
                json=(value or CorporateProfileRefreshInput()).model_dump(mode="json", exclude_unset=True),
                params={"workspace_id": workspace_id} if workspace_id is not None else {},
            )
        )

    async def organization_person_self(
        self, tenant_id: str, *, workspace_id: str | None = None
    ) -> OrganizationPerson:
        return OrganizationPerson.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/organization/people/me",
                params={"workspace_id": workspace_id} if workspace_id is not None else {},
            )
        )

    async def organization_people(
        self, tenant_id: str, **filters: Unpack[OrganizationPeopleFilter]
    ) -> OrganizationPersonPage:
        return OrganizationPersonPage.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/organization/people", params=filters)
        )

    async def create_organization_person(
        self, tenant_id: str, value: OrganizationPersonCreate
    ) -> OrganizationPerson:
        return OrganizationPerson.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/organization/people",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def organization_person(
        self, tenant_id: str, person_id: str, *, workspace_id: str | None = None
    ) -> OrganizationPerson:
        return OrganizationPerson.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/organization/people/" + quote(person_id, safe=""),
                params={"workspace_id": workspace_id} if workspace_id is not None else {},
            )
        )

    async def update_organization_person(
        self, tenant_id: str, person_id: str, value: OrganizationPersonPatch
    ) -> OrganizationPerson:
        return OrganizationPerson.model_validate(
            await self._request(
                "PATCH",
                self._tenant(tenant_id) + "/organization/people/" + quote(person_id, safe=""),
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def organization_person_avatar(
        self,
        tenant_id: str,
        person_id: str,
        *,
        workspace_id: str | None = None,
        if_none_match: str | None = None,
    ) -> BinaryDownload:
        return await self._download(
            self._tenant(tenant_id) + "/organization/people/" + quote(person_id, safe="") + "/avatar",
            params={"workspace_id": workspace_id} if workspace_id is not None else None,
            if_none_match=if_none_match,
        )

    async def organization_person_reports(
        self, tenant_id: str, person_id: str, **filters: Unpack[OrganizationReportsFilter]
    ) -> OrganizationPersonPage:
        return OrganizationPersonPage.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/organization/people/" + quote(person_id, safe="") + "/reports",
                params=filters,
            )
        )

    async def organization_units(
        self, tenant_id: str, **filters: Unpack[OrganizationUnitFilter]
    ) -> OrganizationUnitPage:
        return OrganizationUnitPage.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/organization/units", params=filters)
        )

    async def create_organization_unit(
        self, tenant_id: str, value: OrganizationUnitInput
    ) -> OrganizationUnit:
        return OrganizationUnit.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/organization/units",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def update_organization_unit(
        self, tenant_id: str, unit_id: str, value: OrganizationUnitPatch
    ) -> OrganizationUnit:
        return OrganizationUnit.model_validate(
            await self._request(
                "PATCH",
                self._tenant(tenant_id) + "/organization/units/" + quote(unit_id, safe=""),
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def delete_organization_unit(self, tenant_id: str, unit_id: str, *, expected_revision: int) -> None:
        await self._request(
            "DELETE",
            self._tenant(tenant_id) + "/organization/units/" + quote(unit_id, safe=""),
            params={"expected_revision": expected_revision},
        )

    async def organization_directory_settings(self, tenant_id: str) -> OrganizationDirectorySettings:
        return OrganizationDirectorySettings.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/organization/directory-settings")
        )

    async def update_organization_directory_settings(
        self, tenant_id: str, value: OrganizationDirectorySettingsInput
    ) -> OrganizationDirectorySettings:
        return OrganizationDirectorySettings.model_validate(
            await self._request(
                "PATCH",
                self._tenant(tenant_id) + "/organization/directory-settings",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def organization_profile_mapping(
        self, tenant_id: str, provider_id: str
    ) -> OrganizationProfileMapping:
        return OrganizationProfileMapping.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/organization/profile-mappings/" + quote(provider_id, safe=""),
            )
        )

    async def update_organization_profile_mapping(
        self, tenant_id: str, provider_id: str, value: OrganizationProfileMappingInput
    ) -> OrganizationProfileMapping:
        return OrganizationProfileMapping.model_validate(
            await self._request(
                "PUT",
                self._tenant(tenant_id) + "/organization/profile-mappings/" + quote(provider_id, safe=""),
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def branding_defaults(self) -> BrandingValues:
        return BrandingValues.model_validate(await self._request("GET", "branding/defaults"))

    async def organization_branding(self, tenant_id: str) -> OrganizationBranding:
        return OrganizationBranding.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/branding")
        )

    async def update_organization_branding(
        self, tenant_id: str, value: OrganizationBrandingInput
    ) -> OrganizationBranding:
        return OrganizationBranding.model_validate(
            await self._request(
                "PUT",
                self._tenant(tenant_id) + "/branding",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def reset_organization_branding(
        self, tenant_id: str, value: BrandingResetInput
    ) -> OrganizationBranding:
        return OrganizationBranding.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/branding/reset",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def organization_knowledge_settings(self, tenant_id: str) -> OrganizationKnowledgeSettings:
        return OrganizationKnowledgeSettings.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/knowledge/settings")
        )

    async def update_organization_knowledge_settings(
        self, tenant_id: str, value: OrganizationKnowledgeSettingsInput
    ) -> OrganizationKnowledgeSettings:
        return OrganizationKnowledgeSettings.model_validate(
            await self._request(
                "PUT",
                self._tenant(tenant_id) + "/knowledge/settings",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def organization_chat_settings(
        self, tenant_id: str, *, workspace_id: str | None = None, project_id: str | None = None
    ) -> OrganizationChatSettings:
        filters = {
            key: value
            for key, value in {"workspace_id": workspace_id, "project_id": project_id}.items()
            if value is not None
        }
        return OrganizationChatSettings.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/chat/settings", params=filters)
        )

    async def update_organization_chat_settings(
        self, tenant_id: str, value: OrganizationChatSettingsInput
    ) -> OrganizationChatSettings:
        return OrganizationChatSettings.model_validate(
            await self._request(
                "PUT",
                self._tenant(tenant_id) + "/chat/settings",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def authorized_applications(
        self, **filters: Unpack[AuthorizedApplicationFilter]
    ) -> Page[AuthorizedApplication]:
        return Page[AuthorizedApplication].model_validate(
            await self._request("GET", "authorized-applications", params=filters)
        )

    async def authorized_application(self, application_id: str) -> AuthorizedApplication:
        return AuthorizedApplication.model_validate(
            await self._request("GET", "authorized-applications/" + quote(application_id, safe=""))
        )

    async def revoke_authorized_application(self, application_id: str) -> None:
        await self._request("DELETE", "authorized-applications/" + quote(application_id, safe=""))

    async def tokens(self, **filters: Unpack[StatusFilter]) -> Page[PersonalToken]:
        return Page[PersonalToken].model_validate(await self._request("GET", "tokens", params=filters))

    async def create_token(self, value: TokenInput) -> TokenCreated:
        return TokenCreated.model_validate(
            await self._request("POST", "tokens", json=value.model_dump(mode="json", exclude_unset=True))
        )

    async def revoke_token(self, token_id: str) -> None:
        await self._request("DELETE", "tokens/" + quote(token_id, safe=""))

    async def token_scopes(self, tenant_id: str, *, workspace_id: str | None = None) -> TokenScopeOptions:
        filters = {"tenant_id": tenant_id}
        if workspace_id is not None:
            filters["workspace_id"] = workspace_id
        return TokenScopeOptions.model_validate(await self._request("GET", "tokens/scopes", params=filters))

    async def knowledge_indexes(self, tenant_id: str, **filters: Unpack[IndexFilter]) -> IndexPage:
        return IndexPage.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/knowledge-indexes", params=filters)
        )

    async def native_index_choices(self, tenant_id: str, **filters: Unpack[IndexFilter]) -> NativeIndexPage:
        return NativeIndexPage.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/knowledge-index-choices", params=filters)
        )

    async def native_index_choice(
        self, tenant_id: str, index_id: str, **filters: Unpack[IndexScope]
    ) -> NativeIndexChoice:
        return NativeIndexChoice.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + f"/knowledge-index-choices/{quote(index_id, safe='')}",
                params=filters,
            )
        )

    async def knowledge_index(self, tenant_id: str, index_id: str) -> KnowledgeIndexView:
        return KnowledgeIndexView.model_validate(
            await self._request(
                "GET", self._tenant(tenant_id) + f"/knowledge-indexes/{quote(index_id, safe='')}"
            )
        )

    async def plan_knowledge_index(self, tenant_id: str, value: IndexPlanInput) -> IndexPlanView:
        return IndexPlanView.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/knowledge-indexes/plan", json=self._input(value)
            )
        )

    async def create_knowledge_index(
        self, tenant_id: str, value: IndexCreateInput, idempotency_key: str
    ) -> IndexJobView:
        return IndexJobView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/knowledge-indexes",
                json=self._input(value),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def activate_knowledge_index(
        self, tenant_id: str, index_id: str, value: IndexActivateInput
    ) -> KnowledgeIndexView:
        return KnowledgeIndexView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + f"/knowledge-indexes/{quote(index_id, safe='')}/activate",
                json=self._input(value),
            )
        )

    async def cancel_knowledge_index(
        self, tenant_id: str, index_id: str, value: IndexRevisionInput
    ) -> KnowledgeIndexView:
        return KnowledgeIndexView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + f"/knowledge-indexes/{quote(index_id, safe='')}/cancel",
                json=self._input(value),
            )
        )

    async def resume_knowledge_index(
        self, tenant_id: str, index_id: str, value: IndexRevisionInput, idempotency_key: str
    ) -> IndexJobView:
        return IndexJobView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + f"/knowledge-indexes/{quote(index_id, safe='')}/resume",
                json=self._input(value),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def identity_providers(
        self, tenant_id: str, **filters: Unpack[IdentityFilter]
    ) -> IdentityProviderPage:
        return IdentityProviderPage.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/identity/providers", params=filters)
        )

    async def create_identity_provider(
        self, tenant_id: str, value: IdentityProviderInput
    ) -> IdentityProvider:
        return IdentityProvider.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/identity/providers", json=self._input(value)
            )
        )

    async def identity_provider(self, tenant_id: str, provider_id: str) -> IdentityProvider:
        return IdentityProvider.model_validate(
            await self._request(
                "GET", self._tenant(tenant_id) + f"/identity/providers/{quote(provider_id, safe='')}"
            )
        )

    async def update_identity_provider(
        self, tenant_id: str, provider_id: str, value: IdentityProviderPatch
    ) -> IdentityProvider:
        return IdentityProvider.model_validate(
            await self._request(
                "PATCH",
                self._tenant(tenant_id) + f"/identity/providers/{quote(provider_id, safe='')}",
                json=self._input(value),
            )
        )

    async def test_identity_provider(
        self, tenant_id: str, provider_id: str, value: IdentityRevision
    ) -> IdentityValidation:
        return IdentityValidation.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + f"/identity/providers/{quote(provider_id, safe='')}/test",
                json=self._input(value),
            )
        )

    async def identity_test_status(
        self, tenant_id: str, provider_id: str, validation_id: str
    ) -> IdentityValidation:
        return IdentityValidation.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id)
                + f"/identity/providers/{quote(provider_id, safe='')}/tests/{quote(validation_id, safe='')}",
            )
        )

    async def identity_groups(
        self, tenant_id: str, provider_id: str, **filters: Unpack[IdentityGroupFilter]
    ) -> IdentityGroupPage:
        return IdentityGroupPage.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + f"/identity/providers/{quote(provider_id, safe='')}/groups",
                params=filters,
            )
        )

    async def identity_mappings(
        self, tenant_id: str, provider_id: str, **filters: Unpack[IdentityMappingFilter]
    ) -> IdentityMappingPage:
        return IdentityMappingPage.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + f"/identity/providers/{quote(provider_id, safe='')}/mappings",
                params=filters,
            )
        )

    async def create_identity_mapping(
        self, tenant_id: str, provider_id: str, value: IdentityMappingInput
    ) -> IdentityMapping:
        return IdentityMapping.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + f"/identity/providers/{quote(provider_id, safe='')}/mappings",
                json=self._input(value),
            )
        )

    async def update_identity_mapping(
        self, tenant_id: str, provider_id: str, mapping_id: str, value: IdentityMappingInput
    ) -> IdentityMapping:
        return IdentityMapping.model_validate(
            await self._request(
                "PATCH",
                self._tenant(tenant_id)
                + f"/identity/providers/{quote(provider_id, safe='')}/mappings/{quote(mapping_id, safe='')}",
                json=self._input(value),
            )
        )

    async def remove_identity_mapping(
        self, tenant_id: str, provider_id: str, mapping_id: str, *, expected_revision: int
    ) -> None:
        await self._request(
            "DELETE",
            self._tenant(tenant_id)
            + f"/identity/providers/{quote(provider_id, safe='')}/mappings/{quote(mapping_id, safe='')}",
            params={"expected_revision": expected_revision},
        )

    async def activate_identity_provider(
        self, tenant_id: str, provider_id: str, value: IdentityActivation
    ) -> IdentityProvider:
        return IdentityProvider.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + f"/identity/providers/{quote(provider_id, safe='')}/activate",
                json=self._input(value),
            )
        )

    async def disable_identity_provider(
        self, tenant_id: str, provider_id: str, value: IdentityRevision
    ) -> IdentityProvider:
        return IdentityProvider.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + f"/identity/providers/{quote(provider_id, safe='')}/disable",
                json=self._input(value),
            )
        )

    @staticmethod
    def _attachment_path(tenant_id: str, thread_id: str, attachment_id: str | None = None) -> str:
        path = KoinonClient._tenant(tenant_id) + "/chat/threads/" + quote(thread_id, safe="") + "/attachments"
        return path + "/" + quote(attachment_id, safe="") if attachment_id is not None else path

    async def upload_attachment(
        self, tenant_id: str, thread_id: str, *, filename: str, content: bytes, idempotency_key: str
    ) -> AttachmentView:
        return AttachmentView.model_validate(
            await self._request(
                "POST",
                self._attachment_path(tenant_id, thread_id),
                files={"file": (filename, content)},
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def attachments(
        self, tenant_id: str, thread_id: str, **filters: Unpack[AttachmentFilter]
    ) -> AttachmentPage:
        return AttachmentPage.model_validate(
            await self._request("GET", self._attachment_path(tenant_id, thread_id), params=filters)
        )

    async def attachment_capabilities(self, tenant_id: str, thread_id: str) -> AttachmentCapabilities:
        return AttachmentCapabilities.model_validate(
            await self._request("GET", self._attachment_path(tenant_id, thread_id) + "/capabilities")
        )

    async def attachment(self, tenant_id: str, thread_id: str, attachment_id: str) -> AttachmentView:
        return AttachmentView.model_validate(
            await self._request("GET", self._attachment_path(tenant_id, thread_id, attachment_id))
        )

    async def attachment_chunks(
        self, tenant_id: str, thread_id: str, attachment_id: str, **filters: Unpack[AttachmentChunkFilter]
    ) -> PrivateChunkPage:
        return PrivateChunkPage.model_validate(
            await self._request(
                "GET", self._attachment_path(tenant_id, thread_id, attachment_id) + "/chunks", params=filters
            )
        )

    async def cancel_attachment(
        self, tenant_id: str, thread_id: str, attachment_id: str, value: AttachmentRevision
    ) -> AttachmentView:
        return AttachmentView.model_validate(
            await self._request(
                "POST",
                self._attachment_path(tenant_id, thread_id, attachment_id) + "/cancel",
                json=self._input(value),
            )
        )

    async def retry_attachment(
        self,
        tenant_id: str,
        thread_id: str,
        attachment_id: str,
        value: AttachmentRevision,
        idempotency_key: str,
    ) -> AttachmentView:
        return AttachmentView.model_validate(
            await self._request(
                "POST",
                self._attachment_path(tenant_id, thread_id, attachment_id) + "/retry",
                json=self._input(value),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def remove_attachment(
        self, tenant_id: str, thread_id: str, attachment_id: str, *, expected_revision: int
    ) -> None:
        await self._request(
            "DELETE",
            self._attachment_path(tenant_id, thread_id, attachment_id),
            params={"expected_revision": expected_revision},
        )

    async def attachment_original(self, tenant_id: str, thread_id: str, attachment_id: str) -> BinaryDownload:
        return await self._download(self._attachment_path(tenant_id, thread_id, attachment_id) + "/original")

    async def promote_attachment(
        self,
        tenant_id: str,
        thread_id: str,
        attachment_id: str,
        value: AttachmentPromotionInput,
        idempotency_key: str,
    ) -> AttachmentPromotionView:
        return AttachmentPromotionView.model_validate(
            await self._request(
                "POST",
                self._attachment_path(tenant_id, thread_id, attachment_id) + "/knowledge",
                json=self._input(value),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def run_audit(self, tenant_id: str, run_id: str) -> AnswerAudit:
        return AnswerAudit.model_validate(
            await self._request(
                "GET", self._tenant(tenant_id) + "/chat/runs/" + quote(run_id, safe="") + "/audit"
            )
        )

    async def run_activities(
        self, tenant_id: str, run_id: str, *, page: int = 1, page_size: int = 25
    ) -> Page[ToolActivity]:
        return Page[ToolActivity].model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/chat/runs/" + quote(run_id, safe="") + "/activity",
                params={"page": page, "page_size": page_size},
            )
        )

    async def review_export(self, tenant_id: str, value: ExportReviewInput) -> ExportReview:
        return ExportReview.model_validate(
            await self._request("POST", self._tenant(tenant_id) + "/exports/reviews", json=self._input(value))
        )

    async def create_export(self, tenant_id: str, value: ExportCreate) -> Export:
        return Export.model_validate(
            await self._request("POST", self._tenant(tenant_id) + "/exports", json=self._input(value))
        )

    async def exports(self, tenant_id: str, **filters: Unpack[ExportFilter]) -> ExportPage:
        return ExportPage.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/exports", params=filters)
        )

    async def export(self, tenant_id: str, export_id: str) -> Export:
        return Export.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/exports/" + quote(export_id, safe=""))
        )

    async def export_download(self, tenant_id: str, export_id: str) -> BinaryDownload:
        return await self._download(
            self._tenant(tenant_id) + "/exports/" + quote(export_id, safe="") + "/download"
        )

    async def cancel_export(self, tenant_id: str, export_id: str) -> None:
        await self._request("DELETE", self._tenant(tenant_id) + "/exports/" + quote(export_id, safe=""))

    async def review_share(self, tenant_id: str, value: ShareReviewInput) -> ShareReview:
        return ShareReview.model_validate(
            await self._request("POST", self._tenant(tenant_id) + "/shares/reviews", json=self._input(value))
        )

    async def create_share(self, tenant_id: str, value: ShareCreate) -> Share:
        return Share.model_validate(
            await self._request("POST", self._tenant(tenant_id) + "/shares", json=self._input(value))
        )

    async def shares(self, tenant_id: str, **filters: Unpack[ShareFilter]) -> SharePage:
        return SharePage.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/shares", params=filters)
        )

    async def share(self, tenant_id: str, share_id: str) -> SharedConversation:
        return SharedConversation.model_validate(
            await self._request("GET", self._tenant(tenant_id) + "/shares/" + quote(share_id, safe=""))
        )

    async def revoke_share(self, tenant_id: str, share_id: str) -> None:
        await self._request("DELETE", self._tenant(tenant_id) + "/shares/" + quote(share_id, safe=""))

    async def conversation_evidence(self, tenant_id: str, value: MessageSelection) -> EvidenceManifest:
        return EvidenceManifest.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/evidence/conversations", json=self._input(value)
            )
        )

    async def proposal(self, tenant_id: str, run_id: str, proposal_id: str) -> CatalogProposal:
        return CatalogProposal.model_validate(
            await self._request("GET", self._proposal_path(tenant_id, run_id, proposal_id))
        )

    def _proposal_path(self, tenant_id: str, run_id: str, proposal_id: str) -> str:
        return (
            self._tenant(tenant_id)
            + "/chat/runs/"
            + quote(run_id, safe="")
            + "/proposals/"
            + quote(proposal_id, safe="")
        )

    async def confirm_proposal(
        self, tenant_id: str, run_id: str, proposal_id: str, value: ProposalConfirmation
    ) -> CatalogProposal:
        return CatalogProposal.model_validate(
            await self._request(
                "POST",
                self._proposal_path(tenant_id, run_id, proposal_id) + "/confirm",
                json=self._input(value),
            )
        )

    async def cancel_proposal(
        self, tenant_id: str, run_id: str, proposal_id: str, value: ProposalRevision
    ) -> CatalogProposal:
        return CatalogProposal.model_validate(
            await self._request(
                "POST",
                self._proposal_path(tenant_id, run_id, proposal_id) + "/cancel",
                json=self._input(value),
            )
        )

    @staticmethod
    def _glossary_path(term_id: str | None = None, *, agent: bool = False) -> str:
        return (
            "/structured/"
            + ("agent/" if agent else "")
            + "glossary"
            + ("/" + quote(term_id, safe="") if term_id is not None else "")
        )

    @staticmethod
    def _glossary_headers(
        tenant_id: str, workspace_id: str, expected_updated_at: str | None = None
    ) -> dict[str, str]:
        headers = {"X-Tenant-ID": tenant_id, "X-Workspace-ID": workspace_id}
        if expected_updated_at is not None:
            if not expected_updated_at or any(char in expected_updated_at for char in '"\r\n\x00'):
                raise ValueError("Supply the exact unquoted updated_at timestamp")
            headers["If-Match"] = '"' + expected_updated_at + '"'
        return headers

    async def create_glossary_term(
        self, tenant_id: str, workspace_id: str, value: GlossaryTermCreate, *, agent: bool = False
    ) -> GlossaryTermRead:
        return GlossaryTermRead.model_validate(
            await self._request(
                "POST",
                self._glossary_path(agent=agent),
                json=self._input(value),
                headers=self._glossary_headers(tenant_id, workspace_id),
            )
        )

    async def update_glossary_term(
        self,
        tenant_id: str,
        workspace_id: str,
        term_id: str,
        value: GlossaryTermUpdate,
        *,
        expected_updated_at: str,
        agent: bool = False,
    ) -> GlossaryTermRead:
        return GlossaryTermRead.model_validate(
            await self._request(
                "PUT",
                self._glossary_path(term_id, agent=agent),
                json=self._input(value),
                headers=self._glossary_headers(tenant_id, workspace_id, expected_updated_at),
            )
        )

    async def delete_glossary_term(
        self,
        tenant_id: str,
        workspace_id: str,
        term_id: str,
        *,
        expected_updated_at: str,
        agent: bool = False,
    ) -> None:
        await self._request(
            "DELETE",
            self._glossary_path(term_id, agent=agent),
            headers=self._glossary_headers(tenant_id, workspace_id, expected_updated_at),
        )

    async def glossary_terms(
        self, tenant_id: str, workspace_id: str, *, limit: int = 100, offset: int = 0, agent: bool = False
    ) -> GlossaryPage:
        return GlossaryPage.model_validate(
            await self._request(
                "GET",
                self._glossary_path(agent=agent),
                params={"limit": limit, "offset": offset},
                headers=self._glossary_headers(tenant_id, workspace_id),
            )
        )

    async def glossary_term(
        self, tenant_id: str, workspace_id: str, term_id: str, *, agent: bool = False
    ) -> GlossaryTermRead:
        return GlossaryTermRead.model_validate(
            await self._request(
                "GET",
                self._glossary_path(term_id, agent=agent),
                headers=self._glossary_headers(tenant_id, workspace_id),
            )
        )

    async def personal_activity(self, tenant_id: str, value: ActivityWindow) -> ActivitySummary:
        return ActivitySummary.model_validate(
            await self._request(
                "POST", self._tenant(tenant_id) + "/activity/personal", json=value.model_dump(mode="json")
            )
        )

    async def administrative_activity(self, tenant_id: str, value: ActivityWindow) -> ActivitySummary:
        return ActivitySummary.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/activity/administration",
                json=value.model_dump(mode="json"),
            )
        )
