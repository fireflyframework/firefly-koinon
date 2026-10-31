// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical MemoryReceipt contract. */
public record MemoryReceipt(
    @JsonProperty("validation_mode") MemoryReceiptValidationMode validationMode,
    @JsonProperty("generation_id") String generationId,
    @JsonProperty("policy_version") Long policyVersion,
    @JsonProperty("mode") MemoryReceiptMode mode,
    @JsonProperty("folder_id") String folderId,
    @JsonProperty("folder_revision") Integer folderRevision,
    @JsonProperty("scope_sha256") String scopeSha256,
    @JsonProperty("manifest_sha256") String manifestSha256,
    @JsonProperty("organization_policy_revision") Integer organizationPolicyRevision,
    @JsonProperty("effective_policy") OrganizationMemoryPolicy effectivePolicy,
    @JsonProperty("turns") List<MemoryTurnReference> turns,
    @JsonProperty("dependency_count") Integer dependencyCount,
    @JsonProperty("context_available") Boolean contextAvailable,
    @JsonProperty("unavailable_dependency_count") Integer unavailableDependencyCount,
    @JsonProperty("created_at") Instant createdAt
) {
    public MemoryReceipt {
        turns=turns==null?null:List.copyOf(turns);
    }

}
