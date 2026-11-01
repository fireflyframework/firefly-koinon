// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DirectoryRecipient contract. */
public record DirectoryRecipient(
    @JsonProperty("recipient_ref") String recipientRef,
    @JsonProperty("display_name") String displayName,
    @JsonProperty("email") String email,
    @JsonProperty("provider_label") String providerLabel,
    @JsonProperty("delivery_address_status") DirectoryRecipientDeliveryAddressStatus deliveryAddressStatus,
    @JsonProperty("eligibility") DirectoryRecipientEligibility eligibility,
    @JsonProperty("eligibility_reason") String eligibilityReason
) {

}
