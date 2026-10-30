// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical McpReadReceipt contract. */
public record McpReadReceipt(
    @JsonProperty("status") AnswerAuditProvenanceStatus status,
    @JsonProperty("id") String id,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("sources") List<SourceReference> sources,
    @JsonProperty("reason") McpReadReceiptReason reason
) {
    public McpReadReceipt {
        sources=sources==null?null:List.copyOf(sources);
    }

}
