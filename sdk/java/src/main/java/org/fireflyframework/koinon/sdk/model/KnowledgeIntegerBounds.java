// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KnowledgeIntegerBounds contract. */
public record KnowledgeIntegerBounds(
    @JsonProperty("minimum") Long minimum,
    @JsonProperty("maximum") Long maximum
) {

    public static KnowledgeIntegerBounds empty(){return new KnowledgeIntegerBounds(null,null);}
    public KnowledgeIntegerBounds withMinimum(Long value){return new KnowledgeIntegerBounds(value,maximum);}
    public KnowledgeIntegerBounds withMaximum(Long value){return new KnowledgeIntegerBounds(minimum,value);}
}
