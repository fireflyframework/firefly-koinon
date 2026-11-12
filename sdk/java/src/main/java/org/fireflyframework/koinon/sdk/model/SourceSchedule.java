// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;


@JsonTypeInfo(use=JsonTypeInfo.Id.NAME,include=JsonTypeInfo.As.EXISTING_PROPERTY,property="kind",visible=true)
@JsonSubTypes({@JsonSubTypes.Type(value=ManualSchedule.class,name="manual"),@JsonSubTypes.Type(value=IntervalSchedule.class,name="interval"),@JsonSubTypes.Type(value=CalendarSchedule.class,name="calendar")})
public sealed interface SourceSchedule permits ManualSchedule,IntervalSchedule,CalendarSchedule {}
