// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DigestSchedule contract. */
public record DigestSchedule(
    @JsonProperty("local_time") String localTime,
    @JsonProperty("weekday") Integer weekday,
    @JsonProperty("day_of_month") Integer dayOfMonth
) {

    public static DigestSchedule empty(){return new DigestSchedule(null,null,null);}
    public DigestSchedule withLocalTime(String value){return new DigestSchedule(value,weekday,dayOfMonth);}
    public DigestSchedule withWeekday(Integer value){return new DigestSchedule(localTime,value,dayOfMonth);}
    public DigestSchedule withDayOfMonth(Integer value){return new DigestSchedule(localTime,weekday,value);}
}
