// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;



/** Typed canonical AuditEvent contract. */
public record AuditEvent(
    @JsonProperty("id") String id,
    @JsonProperty("subject") String subject,
    @JsonProperty("action") String action,
    @JsonProperty("resource_id") String resourceId,
    @JsonProperty("details") JsonNode details,
    @JsonProperty("created_at") Instant createdAt
) {
    public AuditEvent {
        details=ModelValues.json(details);
    }
    @Override public JsonNode details(){return ModelValues.json(details);}
}
