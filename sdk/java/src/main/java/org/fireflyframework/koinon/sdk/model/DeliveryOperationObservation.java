// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical DeliveryOperationObservation contract. */
public record DeliveryOperationObservation(
    @JsonProperty("id") String id,
    @JsonProperty("delivery_id") String deliveryId,
    @JsonProperty("source") DeliveryOperationObservationSource source,
    @JsonProperty("operation_state") DeliveryOperationObservationOperationState operationState,
    @JsonProperty("recipient_state") DeliveryOperationObservationRecipientState recipientState,
    @JsonProperty("checked_at") Instant checkedAt,
    @JsonProperty("reason_code") String reasonCode
) {

}
