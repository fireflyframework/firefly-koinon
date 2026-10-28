// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SetupCheckCapability {
    CHAT("chat"),
    STREAMING("streaming"),
    TOOLS("tools"),
    IMAGE_INPUT("image_input"),
    AUDIO_INPUT("audio_input");
    private final String value;
    SetupCheckCapability(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SetupCheckCapability from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SetupCheckCapability value: "+value);}
}
