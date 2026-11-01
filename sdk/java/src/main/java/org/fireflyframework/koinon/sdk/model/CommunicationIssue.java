// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical CommunicationIssue contract. */
public record CommunicationIssue(
    @JsonProperty("code") String code,
    @JsonProperty("explanation") String explanation
) {

}
