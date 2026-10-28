// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical KnowledgeContent contract. */
public record KnowledgeContent(
    @JsonProperty("title") String title,
    @JsonProperty("body") String body,
    @JsonProperty("summary") String summary,
    @JsonProperty("domain") KnowledgeContentDomain domain,
    @JsonProperty("tags") List<String> tags
) {
    public KnowledgeContent {
        tags=tags==null?null:List.copyOf(tags);
    }

}
