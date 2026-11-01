// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SystemInformationCopyright {
    COPYRIGHT_2026_FIREFLY_SOFTWARE_FOUNDATION("Copyright 2026 Firefly Software Foundation");
    private final String value;
    SystemInformationCopyright(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SystemInformationCopyright from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SystemInformationCopyright value: "+value);}
}
