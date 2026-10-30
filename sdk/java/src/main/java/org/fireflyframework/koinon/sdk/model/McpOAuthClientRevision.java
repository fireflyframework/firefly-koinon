// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical McpOAuthClientRevision contract. */
public record McpOAuthClientRevision(
    @JsonProperty("expected_revision") Integer expectedRevision
) {

    public static McpOAuthClientRevision empty(){return new McpOAuthClientRevision(null);}
    public McpOAuthClientRevision withExpectedRevision(Integer value){return new McpOAuthClientRevision(value);}
}
