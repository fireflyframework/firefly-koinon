// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical InvitationToken contract. */
public record InvitationToken(
    @JsonProperty("token") String token
) {

    public static InvitationToken empty(){return new InvitationToken(null);}
    public InvitationToken withToken(String value){return new InvitationToken(value);}
    @Override public String toString(){return "InvitationToken[token=<redacted>]";}
}
