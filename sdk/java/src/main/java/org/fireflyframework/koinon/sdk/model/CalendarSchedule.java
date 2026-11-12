// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical CalendarSchedule contract. */
public record CalendarSchedule(
    @JsonProperty("kind") CalendarScheduleKind kind,
    @JsonProperty("timezone") String timezone,
    @JsonProperty("time") String time,
    @JsonProperty("weekdays") List<Integer> weekdays
) implements SourceSchedule {
    public CalendarSchedule {
        weekdays=weekdays==null?null:List.copyOf(weekdays);
    }

    public static CalendarSchedule empty(){return new CalendarSchedule(null,null,null,null);}
    public CalendarSchedule withKind(CalendarScheduleKind value){return new CalendarSchedule(value,timezone,time,weekdays);}
    public CalendarSchedule withTimezone(String value){return new CalendarSchedule(kind,value,time,weekdays);}
    public CalendarSchedule withTime(String value){return new CalendarSchedule(kind,timezone,value,weekdays);}
    public CalendarSchedule withWeekdays(List<Integer> value){return new CalendarSchedule(kind,timezone,time,value);}
}
