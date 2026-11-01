// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical NotificationDetails contract. */
public record NotificationDetails(
    @JsonProperty("label") String label,
    @JsonProperty("scopes") List<String> scopes,
    @JsonProperty("expires_at") Instant expiresAt
) {
    public NotificationDetails {
        scopes=scopes==null?null:List.copyOf(scopes);
    }

}
