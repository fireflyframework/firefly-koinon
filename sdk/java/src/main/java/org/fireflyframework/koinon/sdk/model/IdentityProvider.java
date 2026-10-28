// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical IdentityProvider contract. */
public record IdentityProvider(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("kind") IdentityProviderKind kind,
    @JsonProperty("name") String name,
    @JsonProperty("canonical_issuer") String canonicalIssuer,
    @JsonProperty("broker_alias") String brokerAlias,
    @JsonProperty("ownership") IdentityProviderOwnership ownership,
    @JsonProperty("revision") Long revision,
    @JsonProperty("policy_revision") Long policyRevision,
    @JsonProperty("status") IdentityProviderStatus status,
    @JsonProperty("credential_configured") Boolean credentialConfigured,
    @JsonProperty("settings") IdentityProviderSettings settings,
    @JsonProperty("checks") List<IdentityCheck> checks,
    @JsonProperty("capabilities") List<String> capabilities,
    @JsonProperty("observed_at") Instant observedAt,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("updated_at") Instant updatedAt,
    @JsonProperty("created_by") String createdBy,
    @JsonProperty("updated_by") String updatedBy
) {
    public IdentityProvider {
        checks=checks==null?null:List.copyOf(checks);
        capabilities=capabilities==null?null:List.copyOf(capabilities);
    }

}
