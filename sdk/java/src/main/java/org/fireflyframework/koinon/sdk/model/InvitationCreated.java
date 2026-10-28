// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical InvitationCreated contract. */
public record InvitationCreated(
    @JsonProperty("invitation") Invitation invitation,
    @JsonProperty("token") String token
) {

    @Override public String toString(){return "InvitationCreated[token=<redacted>]";}
}
