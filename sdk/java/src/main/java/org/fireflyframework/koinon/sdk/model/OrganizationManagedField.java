// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum OrganizationManagedField {
    JOB_TITLE("job_title"),
    UNIT_ID("unit_id"),
    MANAGER_ID("manager_id");
    private final String value;
    OrganizationManagedField(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static OrganizationManagedField from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown OrganizationManagedField value: "+value);}
}
