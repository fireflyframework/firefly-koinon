// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationDirectorySettings contract. */
public record OrganizationDirectorySettings(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("visibility") OrganizationDirectoryVisibility visibility,
    @JsonProperty("revision") Integer revision
) {

}
