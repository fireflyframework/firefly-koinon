// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical ShareReview contract. */
public record ShareReview(
    @JsonProperty("id") String id,
    @JsonProperty("revision") String revision,
    @JsonProperty("title") String title,
    @JsonProperty("message_count") Long messageCount,
    @JsonProperty("source_count") Long sourceCount,
    @JsonProperty("messages") List<ConversationMessage> messages,
    @JsonProperty("sources") List<SourceReference> sources,
    @JsonProperty("source_manifest_complete") Boolean sourceManifestComplete,
    @JsonProperty("recipient_policy") ShareRecipientPolicy recipientPolicy,
    @JsonProperty("omissions") List<String> omissions,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("identity") ConversationIdentity identity
) {
    public ShareReview(String id, String revision, String title, Long messageCount, Long sourceCount, List<ConversationMessage> messages, List<SourceReference> sources, Boolean sourceManifestComplete, ShareRecipientPolicy recipientPolicy, List<String> omissions, Instant expiresAt){this(id,revision,title,messageCount,sourceCount,messages,sources,sourceManifestComplete,recipientPolicy,omissions,expiresAt,null);}
    public ShareReview {
        messages=messages==null?null:List.copyOf(messages);
        sources=sources==null?null:List.copyOf(sources);
        omissions=omissions==null?null:List.copyOf(omissions);
    }

}
