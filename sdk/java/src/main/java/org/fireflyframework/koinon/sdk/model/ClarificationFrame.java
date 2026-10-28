// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ClarificationFrame contract. */
public record ClarificationFrame(
    @JsonProperty("questions") List<String> questions,
    @JsonProperty("reasons") List<String> reasons
) {
    public ClarificationFrame {
        questions=questions==null?null:List.copyOf(questions);
        reasons=reasons==null?null:List.copyOf(reasons);
    }

}
