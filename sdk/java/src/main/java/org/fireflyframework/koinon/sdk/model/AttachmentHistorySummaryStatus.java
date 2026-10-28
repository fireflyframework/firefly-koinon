// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum AttachmentHistorySummaryStatus {
    STORING("storing"),
    QUEUED("queued"),
    EXTRACTING("extracting"),
    READY("ready"),
    FAILED("failed"),
    CANCELLED("cancelled"),
    EXPIRED("expired"),
    DELETED("deleted");
    private final String value;
    AttachmentHistorySummaryStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static AttachmentHistorySummaryStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown AttachmentHistorySummaryStatus value: "+value);}
}
