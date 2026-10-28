// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ProposalConfirmation contract. */
public record ProposalConfirmation(
    @JsonProperty("confirm") Boolean confirm,
    @JsonProperty("expected_revision") Long expectedRevision
) {

    public static ProposalConfirmation empty(){return new ProposalConfirmation(null,null);}
    public ProposalConfirmation withConfirm(Boolean value){return new ProposalConfirmation(value,expectedRevision);}
    public ProposalConfirmation withExpectedRevision(Long value){return new ProposalConfirmation(confirm,value);}
}
