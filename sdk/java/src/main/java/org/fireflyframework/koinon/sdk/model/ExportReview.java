// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical ExportReview contract. */
public record ExportReview(
    @JsonProperty("id") String id,
    @JsonProperty("revision") String revision,
    @JsonProperty("kind") ExportKind kind,
    @JsonProperty("format") ExportFormat format,
    @JsonProperty("title") String title,
    @JsonProperty("message_count") Integer messageCount,
    @JsonProperty("source_count") Integer sourceCount,
    @JsonProperty("row_count") Long rowCount,
    @JsonProperty("row_cap") Long rowCap,
    @JsonProperty("truncated") Boolean truncated,
    @JsonProperty("completeness") ExportCompleteness completeness,
    @JsonProperty("messages") List<ConversationMessage> messages,
    @JsonProperty("sources") List<SourceReference> sources,
    @JsonProperty("source_manifest_complete") Boolean sourceManifestComplete,
    @JsonProperty("result") StoredResult result,
    @JsonProperty("omissions") List<String> omissions,
    @JsonProperty("expires_at") Instant expiresAt
) {
    public ExportReview {
        messages=messages==null?null:List.copyOf(messages);
        sources=sources==null?null:List.copyOf(sources);
        omissions=omissions==null?null:List.copyOf(omissions);
    }

}
