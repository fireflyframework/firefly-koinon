// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ModelConnection contract. */
public record ModelConnection(
    @JsonProperty("id") String id,
    @JsonProperty("ownership") DeploymentConfigurationOwnership ownership,
    @JsonProperty("read_only") Boolean readOnly,
    @JsonProperty("provider") String provider,
    @JsonProperty("model_id") String modelId,
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("available") Boolean available,
    @JsonProperty("status") CheckStatus status,
    @JsonProperty("reason") String reason
) {

}
