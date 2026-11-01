// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum EmailInvitationActionReasons {
    CLOSED("closed"),
    COOLDOWN("cooldown"),
    SEND_LIMIT("send_limit"),
    DELIVERY_OUTCOME_UNKNOWN("delivery_outcome_unknown"),
    INVITER_AUTHORITY_LOST("inviter_authority_lost"),
    ORIGIN_TOKEN_REVOKED("origin_token_revoked"),
    ORIGIN_TOKEN_EXPIRED("origin_token_expired"),
    ORIGIN_SCOPE_CHANGED("origin_scope_changed"),
    RECIPIENT_CONNECTION_CHANGED("recipient_connection_changed");
    private final String value;
    EmailInvitationActionReasons(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static EmailInvitationActionReasons from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown EmailInvitationActionReasons value: "+value);}
}
