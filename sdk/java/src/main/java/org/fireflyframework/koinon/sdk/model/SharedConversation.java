// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SharedConversation contract. */
public record SharedConversation(
    @JsonProperty("share") Share share,
    @JsonProperty("messages") List<ConversationMessage> messages,
    @JsonProperty("sources") List<SourceReference> sources,
    @JsonProperty("source_manifest_complete") Boolean sourceManifestComplete,
    @JsonProperty("identity") ConversationIdentity identity
) {
    public SharedConversation(Share share, List<ConversationMessage> messages, List<SourceReference> sources, Boolean sourceManifestComplete){this(share,messages,sources,sourceManifestComplete,null);}
    public SharedConversation {
        messages=messages==null?null:List.copyOf(messages);
        sources=sources==null?null:List.copyOf(sources);
    }

}
