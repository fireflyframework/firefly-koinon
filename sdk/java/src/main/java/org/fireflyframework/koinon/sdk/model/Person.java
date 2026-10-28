// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical Person contract. */
public record Person(
    @JsonProperty("profile_id") String profileId,
    @JsonProperty("subject") String subject,
    @JsonProperty("display_name") String displayName,
    @JsonProperty("avatar_url") String avatarUrl,
    @JsonProperty("avatar_version") String avatarVersion
) {

}
