// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationPersonReference contract. */
public record OrganizationPersonReference(
    @JsonProperty("id") String id,
    @JsonProperty("display_name") String displayName
) {

}
