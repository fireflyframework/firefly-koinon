// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical ActivityWindow contract. */
public record ActivityWindow(
    @JsonProperty("start_at") Instant startAt,
    @JsonProperty("end_at") Instant endAt,
    @JsonProperty("time_zone") String timeZone
) {

    public static ActivityWindow empty(){return new ActivityWindow(null,null,null);}
    public ActivityWindow withStartAt(Instant value){return new ActivityWindow(value,endAt,timeZone);}
    public ActivityWindow withEndAt(Instant value){return new ActivityWindow(startAt,value,timeZone);}
    public ActivityWindow withTimeZone(String value){return new ActivityWindow(startAt,endAt,value);}
}
