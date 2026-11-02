// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical WelcomeRecoveryInput contract. */
public record WelcomeRecoveryInput(
    @JsonProperty("expected_generation") Long expectedGeneration,
    @JsonProperty("contact_id") String contactId,
    @JsonProperty("expected_contact_revision") Long expectedContactRevision,
    @JsonProperty("reason") WelcomeRecoveryInputReason reason,
    @JsonProperty("acknowledge_possible_duplicate") Boolean acknowledgePossibleDuplicate
) {

    public static WelcomeRecoveryInput empty(){return new WelcomeRecoveryInput(null,null,null,null,null);}
    public WelcomeRecoveryInput withExpectedGeneration(Long value){return new WelcomeRecoveryInput(value,contactId,expectedContactRevision,reason,acknowledgePossibleDuplicate);}
    public WelcomeRecoveryInput withContactId(String value){return new WelcomeRecoveryInput(expectedGeneration,value,expectedContactRevision,reason,acknowledgePossibleDuplicate);}
    public WelcomeRecoveryInput withExpectedContactRevision(Long value){return new WelcomeRecoveryInput(expectedGeneration,contactId,value,reason,acknowledgePossibleDuplicate);}
    public WelcomeRecoveryInput withReason(WelcomeRecoveryInputReason value){return new WelcomeRecoveryInput(expectedGeneration,contactId,expectedContactRevision,value,acknowledgePossibleDuplicate);}
    public WelcomeRecoveryInput withAcknowledgePossibleDuplicate(Boolean value){return new WelcomeRecoveryInput(expectedGeneration,contactId,expectedContactRevision,reason,value);}
}
