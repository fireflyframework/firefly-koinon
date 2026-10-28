// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum PendingKnowledgeCommitStatus {
    PENDING("pending");
    private final String value;
    PendingKnowledgeCommitStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static PendingKnowledgeCommitStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown PendingKnowledgeCommitStatus value: "+value);}
}
