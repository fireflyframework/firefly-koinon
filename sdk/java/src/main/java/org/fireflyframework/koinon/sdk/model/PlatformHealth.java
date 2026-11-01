// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical PlatformHealth contract. */
public record PlatformHealth(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("checked_at") Instant checkedAt,
    @JsonProperty("summary") HealthSummary summary,
    @JsonProperty("components") List<HealthComponent> components
) {
    public PlatformHealth {
        components=components==null?null:List.copyOf(components);
    }

}
