// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ManualSchedule contract. */
public record ManualSchedule(
    @JsonProperty("kind") ManualScheduleKind kind
) implements SourceSchedule {

    public static ManualSchedule empty(){return new ManualSchedule(null);}
    public ManualSchedule withKind(ManualScheduleKind value){return new ManualSchedule(value);}
}
