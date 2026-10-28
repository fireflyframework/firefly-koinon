// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical UserProfile contract. */
public record UserProfile(
    @JsonProperty("subject") String subject,
    @JsonProperty("display_name") String displayName,
    @JsonProperty("locale") String locale,
    @JsonProperty("time_zone") String timeZone,
    @JsonProperty("response_language") String responseLanguage,
    @JsonProperty("avatar_url") String avatarUrl,
    @JsonProperty("avatar_version") String avatarVersion
) {

}
