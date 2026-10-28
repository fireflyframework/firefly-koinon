// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ValidationResult contract. */
public record ValidationResult(
    @JsonProperty("connected") Boolean connected,
    @JsonProperty("discovered") Boolean discovered,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("revision") Long revision,
    @JsonProperty("status") ValidationResultStatus status,
    @JsonProperty("checks") List<SetupCheck> checks
) {
    public ValidationResult {
        checks=checks==null?null:List.copyOf(checks);
    }

}
