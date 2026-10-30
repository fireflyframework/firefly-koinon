// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationProfileMapping contract. */
public record OrganizationProfileMapping(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("revision") Integer revision,
    @JsonProperty("enabled") Boolean enabled,
    @JsonProperty("fields") OrganizationProfileFields fields,
    @JsonProperty("source") OrganizationMappingSource source
) {

}
