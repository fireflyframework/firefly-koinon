// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ProposalRevision contract. */
public record ProposalRevision(
    @JsonProperty("expected_revision") Long expectedRevision
) {

    public static ProposalRevision empty(){return new ProposalRevision(null);}
    public ProposalRevision withExpectedRevision(Long value){return new ProposalRevision(value);}
}
