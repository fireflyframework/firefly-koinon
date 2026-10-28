// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ProposalUpdate contract. */
public record ProposalUpdate(
    @JsonProperty("id") String id,
    @JsonProperty("status") ProposalUpdateStatus status,
    @JsonProperty("revision") Long revision
) {

}
