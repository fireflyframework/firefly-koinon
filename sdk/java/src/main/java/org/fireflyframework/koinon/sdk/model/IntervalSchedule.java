// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IntervalSchedule contract. */
public record IntervalSchedule(
    @JsonProperty("kind") IntervalScheduleKind kind,
    @JsonProperty("seconds") Integer seconds
) implements SourceSchedule {

    public static IntervalSchedule empty(){return new IntervalSchedule(null,null);}
    public IntervalSchedule withKind(IntervalScheduleKind value){return new IntervalSchedule(value,seconds);}
    public IntervalSchedule withSeconds(Integer value){return new IntervalSchedule(kind,value);}
}
