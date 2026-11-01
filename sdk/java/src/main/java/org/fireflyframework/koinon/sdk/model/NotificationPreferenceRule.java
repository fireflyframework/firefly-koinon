// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical NotificationPreferenceRule contract. */
public record NotificationPreferenceRule(
    @JsonProperty("kind") DeliveryRecordKind kind,
    @JsonProperty("required") Boolean required,
    @JsonProperty("inbox") Boolean inbox,
    @JsonProperty("email") Boolean email,
    @JsonProperty("email_available") Boolean emailAvailable
) {

}
