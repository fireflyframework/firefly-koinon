// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ExternalReviewDecision contract. */
public record ExternalReviewDecision(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("authorization_digest") String authorizationDigest,
    @JsonProperty("nonce") String nonce
) {

    public static ExternalReviewDecision empty(){return new ExternalReviewDecision(null,null,null);}
    public ExternalReviewDecision withExpectedRevision(Long value){return new ExternalReviewDecision(value,authorizationDigest,nonce);}
    public ExternalReviewDecision withAuthorizationDigest(String value){return new ExternalReviewDecision(expectedRevision,value,nonce);}
    public ExternalReviewDecision withNonce(String value){return new ExternalReviewDecision(expectedRevision,authorizationDigest,value);}
}
