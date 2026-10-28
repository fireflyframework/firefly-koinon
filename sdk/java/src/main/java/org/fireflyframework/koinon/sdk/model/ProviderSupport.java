// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ProviderSupport contract. */
public record ProviderSupport(
    @JsonProperty("id") String id,
    @JsonProperty("native_supported") Boolean nativeSupported,
    @JsonProperty("exposed") Boolean exposed,
    @JsonProperty("kind") String kind,
    @JsonProperty("api") String api,
    @JsonProperty("model_class") String modelClass,
    @JsonProperty("reason") String reason
) {

}
