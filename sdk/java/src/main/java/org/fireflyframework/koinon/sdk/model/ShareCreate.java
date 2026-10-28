// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ShareCreate contract. */
public record ShareCreate(
    @JsonProperty("review_id") String reviewId,
    @JsonProperty("expected_revision") String expectedRevision,
    @JsonProperty("expires_in_hours") Integer expiresInHours,
    @JsonProperty("recipient_policy") ShareRecipientPolicy recipientPolicy
) {

    public static ShareCreate empty(){return new ShareCreate(null,null,null,null);}
    public ShareCreate withReviewId(String value){return new ShareCreate(value,expectedRevision,expiresInHours,recipientPolicy);}
    public ShareCreate withExpectedRevision(String value){return new ShareCreate(reviewId,value,expiresInHours,recipientPolicy);}
    public ShareCreate withExpiresInHours(Integer value){return new ShareCreate(reviewId,expectedRevision,value,recipientPolicy);}
    public ShareCreate withRecipientPolicy(ShareRecipientPolicy value){return new ShareCreate(reviewId,expectedRevision,expiresInHours,value);}
}
