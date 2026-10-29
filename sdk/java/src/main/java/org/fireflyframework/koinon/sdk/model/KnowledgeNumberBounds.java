// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;



/** Typed canonical KnowledgeNumberBounds contract. */
public record KnowledgeNumberBounds(
    @JsonProperty("minimum") BigDecimal minimum,
    @JsonProperty("maximum") BigDecimal maximum
) {

    public static KnowledgeNumberBounds empty(){return new KnowledgeNumberBounds(null,null);}
    public KnowledgeNumberBounds withMinimum(BigDecimal value){return new KnowledgeNumberBounds(value,maximum);}
    public KnowledgeNumberBounds withMaximum(BigDecimal value){return new KnowledgeNumberBounds(minimum,value);}
}
