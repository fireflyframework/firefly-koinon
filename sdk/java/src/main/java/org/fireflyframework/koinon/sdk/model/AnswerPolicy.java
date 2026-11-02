// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AnswerPolicy contract. */
public record AnswerPolicy(
    @JsonProperty("outcome") AnswerPolicyOutcome outcome,
    @JsonProperty("code") String code,
    @JsonProperty("reason") String reason,
    @JsonProperty("validation") AnswerSelectionValidation validation,
    @JsonProperty("publication") AnswerPublication publication
) {
    public AnswerPolicy(AnswerPolicyOutcome outcome, String code, String reason){this(outcome,code,reason,null,null);}

}
