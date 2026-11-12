// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceScheduleCapability contract. */
public record SourceScheduleCapability(
    @JsonProperty("min_interval_seconds") Long minIntervalSeconds,
    @JsonProperty("max_interval_seconds") Long maxIntervalSeconds,
    @JsonProperty("calendar_timezones") SourceScheduleCapabilityCalendarTimezones calendarTimezones,
    @JsonProperty("max_calendar_weekdays") Long maxCalendarWeekdays
) {

}
