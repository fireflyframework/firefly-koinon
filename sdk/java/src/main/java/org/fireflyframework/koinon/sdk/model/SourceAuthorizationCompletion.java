// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceAuthorizationCompletion contract. */
public record SourceAuthorizationCompletion(
    @JsonProperty("challenge_id") String challengeId,
    @JsonProperty("state") String state,
    @JsonProperty("code") String code
) {

    public static SourceAuthorizationCompletion empty(){return new SourceAuthorizationCompletion(null,null,null);}
    public SourceAuthorizationCompletion withChallengeId(String value){return new SourceAuthorizationCompletion(value,state,code);}
    public SourceAuthorizationCompletion withState(String value){return new SourceAuthorizationCompletion(challengeId,value,code);}
    public SourceAuthorizationCompletion withCode(String value){return new SourceAuthorizationCompletion(challengeId,state,value);}
    @Override public String toString(){return "SourceAuthorizationCompletion[credentials=<redacted>]";}
}
