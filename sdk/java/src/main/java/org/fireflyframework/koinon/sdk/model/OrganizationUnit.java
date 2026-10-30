// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical OrganizationUnit contract. */
public record OrganizationUnit(
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("kind") OrganizationUnitKind kind,
    @JsonProperty("updated_at") Instant updatedAt,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("parent_id") String parentId,
    @JsonProperty("revision") Integer revision,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("has_children") Boolean hasChildren
) {

}
