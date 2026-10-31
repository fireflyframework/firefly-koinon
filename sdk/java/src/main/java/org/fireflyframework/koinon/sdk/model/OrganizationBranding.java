// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationBranding contract. */
public record OrganizationBranding(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("schema_version") Long schemaVersion,
    @JsonProperty("revision") Integer revision,
    @JsonProperty("origin") KnowledgeSettingsOrigin origin,
    @JsonProperty("branding") BrandingValues branding
) {

}
