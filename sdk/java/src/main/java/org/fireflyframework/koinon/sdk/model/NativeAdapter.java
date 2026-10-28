// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical NativeAdapter contract. */
public record NativeAdapter(
    @JsonProperty("ownership") DeploymentConfigurationOwnership ownership,
    @JsonProperty("read_only") Boolean readOnly,
    @JsonProperty("model_class") String modelClass,
    @JsonProperty("provider_identity") String providerIdentity,
    @JsonProperty("profile_status") NativeAdapterProfileStatus profileStatus,
    @JsonProperty("reason") String reason
) {

}
