// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical WelcomeRecoveryAcknowledgement contract. */
public record WelcomeRecoveryAcknowledgement(
    @JsonProperty("original_delivery_id") String originalDeliveryId,
    @JsonProperty("delivery_id") String deliveryId,
    @JsonProperty("status") DeliveryRecordStatus status,
    @JsonProperty("possible_original_late_arrival") Boolean possibleOriginalLateArrival
) {

}
