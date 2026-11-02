// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical AnswerSelectionValidation contract. */
public record AnswerSelectionValidation(
    @JsonProperty("repairs") Long repairs,
    @JsonProperty("errors") List<String> errors
) {
    public AnswerSelectionValidation {
        errors=errors==null?null:List.copyOf(errors);
    }

}
