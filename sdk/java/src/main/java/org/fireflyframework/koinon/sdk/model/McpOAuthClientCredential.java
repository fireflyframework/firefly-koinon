// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical McpOAuthClientCredential contract. */
public record McpOAuthClientCredential(
    @JsonProperty("client") McpOAuthClient client,
    @JsonProperty("client_secret") String clientSecret
) {

    @Override public String toString(){return "McpOAuthClientCredential[credentials=<redacted>]";}
}
