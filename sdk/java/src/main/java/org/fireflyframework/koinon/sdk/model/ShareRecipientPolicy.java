// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ShareRecipientPolicy {
    ORGANIZATION_CURRENT_ACL("organization_current_acl");
    private final String value;
    ShareRecipientPolicy(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ShareRecipientPolicy from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ShareRecipientPolicy value: "+value);}
}
