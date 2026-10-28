// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ExportCreate contract. */
public record ExportCreate(
    @JsonProperty("review_id") String reviewId,
    @JsonProperty("expected_revision") String expectedRevision
) {

    public static ExportCreate empty(){return new ExportCreate(null,null);}
    public ExportCreate withReviewId(String value){return new ExportCreate(value,expectedRevision);}
    public ExportCreate withExpectedRevision(String value){return new ExportCreate(reviewId,value);}
}
