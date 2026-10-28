// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical CatalogProposal contract. */
public record CatalogProposal(
    @JsonProperty("id") String id,
    @JsonProperty("run_id") String runId,
    @JsonProperty("kind") CatalogProposalKind kind,
    @JsonProperty("status") CatalogProposalStatus status,
    @JsonProperty("revision") Long revision,
    @JsonProperty("asset_id") String assetId,
    @JsonProperty("before") CatalogProposalBefore before,
    @JsonProperty("changes") CatalogProposalPatch changes,
    @JsonProperty("expected_catalog_digest") String expectedCatalogDigest,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("applied_at") Instant appliedAt,
    @JsonProperty("cancelled_at") Instant cancelledAt
) {

}
