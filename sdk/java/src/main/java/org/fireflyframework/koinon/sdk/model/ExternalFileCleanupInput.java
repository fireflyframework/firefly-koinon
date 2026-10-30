// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ExternalFileCleanupInput contract. */
public record ExternalFileCleanupInput(
    @JsonProperty("review_ids") List<String> reviewIds,
    @JsonProperty("max_objects") Integer maxObjects
) {
    public ExternalFileCleanupInput {
        reviewIds=reviewIds==null?null:List.copyOf(reviewIds);
    }

    public static ExternalFileCleanupInput empty(){return new ExternalFileCleanupInput(null,null);}
    public ExternalFileCleanupInput withReviewIds(List<String> value){return new ExternalFileCleanupInput(value,maxObjects);}
    public ExternalFileCleanupInput withMaxObjects(Integer value){return new ExternalFileCleanupInput(reviewIds,value);}
}
