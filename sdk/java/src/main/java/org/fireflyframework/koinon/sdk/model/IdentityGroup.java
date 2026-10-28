// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IdentityGroup contract. */
public record IdentityGroup(
    @JsonProperty("id") String id,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("name") String name,
    @JsonProperty("path") String path,
    @JsonProperty("membership_mode") EntraSettingsMembershipMode membershipMode
) {

}
