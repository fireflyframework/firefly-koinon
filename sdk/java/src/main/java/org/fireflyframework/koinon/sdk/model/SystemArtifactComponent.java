// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SystemArtifactComponent {
    BACKEND("backend"),
    DOCUMENTS("documents"),
    STRUCTURED("structured"),
    STORAGE("storage"),
    PYTHON_SDK("python-sdk"),
    FRAMEWORK("framework");
    private final String value;
    SystemArtifactComponent(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SystemArtifactComponent from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SystemArtifactComponent value: "+value);}
}
