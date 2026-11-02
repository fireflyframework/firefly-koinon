// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DeliveryRecoveryOptions contract. */
public record DeliveryRecoveryOptions(
    @JsonProperty("delivery_id") String deliveryId,
    @JsonProperty("generation") Long generation,
    @JsonProperty("submission_status") DeliveryRecordStatus submissionStatus,
    @JsonProperty("attempt_count") Long attemptCount,
    @JsonProperty("can_inspect") Boolean canInspect,
    @JsonProperty("inspection_reason") String inspectionReason,
    @JsonProperty("provider_binding_state") DeliveryRecoveryOptionsProviderBindingState providerBindingState,
    @JsonProperty("can_recover_welcome") Boolean canRecoverWelcome,
    @JsonProperty("recovery_reason") String recoveryReason,
    @JsonProperty("contact_id") String contactId,
    @JsonProperty("contact_revision") Long contactRevision,
    @JsonProperty("possible_original_late_arrival") Boolean possibleOriginalLateArrival
) {

}
