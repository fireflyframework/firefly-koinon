# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.assistants.proposal_dtos import ProposalConfirmation, ProposalRevision
from koinon.assistants.proposals import CatalogProposals
from koinon.evidence.http import private_json
from koinon.security.identity import identity_from_request


@rest_controller(name="assistants.proposal-controller")
@request_mapping("/api/v1/tenants/{tenant_id}/chat/runs/{run_id}/proposals")
class CatalogProposalController:
    def __init__(self, proposals: CatalogProposals):
        self.proposals = proposals

    @get_mapping("/{proposal_id}")
    async def get(
        self, tenant_id: PathVar[str], run_id: PathVar[str], proposal_id: PathVar[str], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.proposals.get(identity_from_request(request).subject, tenant_id, run_id, proposal_id)
        )

    @post_mapping("/{proposal_id}/confirm")
    async def confirm(
        self,
        tenant_id: PathVar[str],
        run_id: PathVar[str],
        proposal_id: PathVar[str],
        body: Valid[Body[ProposalConfirmation]],
        request: Request,
    ) -> JSONResponse:
        return private_json(
            await self.proposals.confirm(
                identity_from_request(request).subject, tenant_id, run_id, proposal_id, body
            )
        )

    @post_mapping("/{proposal_id}/cancel")
    async def cancel(
        self,
        tenant_id: PathVar[str],
        run_id: PathVar[str],
        proposal_id: PathVar[str],
        body: Valid[Body[ProposalRevision]],
        request: Request,
    ) -> JSONResponse:
        return private_json(
            await self.proposals.cancel(
                identity_from_request(request).subject,
                tenant_id,
                run_id,
                proposal_id,
                expected_revision=body.expected_revision,
            )
        )
