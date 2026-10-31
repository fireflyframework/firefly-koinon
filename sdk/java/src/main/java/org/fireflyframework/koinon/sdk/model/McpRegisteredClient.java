// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical McpRegisteredClient contract. */
public record McpRegisteredClient(
    @JsonProperty("client_id") String clientId,
    @JsonProperty("name") String name,
    @JsonProperty("scopes") List<String> scopes,
    @JsonProperty("client_auth") McpRegisteredClientClientAuth clientAuth
) {
    public McpRegisteredClient {
        scopes=scopes==null?null:List.copyOf(scopes);
    }

}
