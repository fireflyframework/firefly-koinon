// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical RecipientProvider contract. */
public record RecipientProvider(
    @JsonProperty("id") String id,
    @JsonProperty("display_name") String displayName
) {

}
