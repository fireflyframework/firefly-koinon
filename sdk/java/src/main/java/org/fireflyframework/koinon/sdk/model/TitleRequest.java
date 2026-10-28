// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical TitleRequest contract. */
public record TitleRequest(
    @JsonProperty("agent_id") String agentId,
    @JsonProperty("expected_revision") Long expectedRevision
) {

    public static TitleRequest empty(){return new TitleRequest(null,null);}
    public TitleRequest withAgentId(String value){return new TitleRequest(value,expectedRevision);}
    public TitleRequest withExpectedRevision(Long value){return new TitleRequest(agentId,value);}
}
