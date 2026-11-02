// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical BulkRecoveryAction contract. */
public record BulkRecoveryAction(
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("operation") BulkRecoveryActionOperation operation
) {

    public static BulkRecoveryAction empty(){return new BulkRecoveryAction(null,null);}
    public BulkRecoveryAction withExpectedRevision(Integer value){return new BulkRecoveryAction(value,operation);}
    public BulkRecoveryAction withOperation(BulkRecoveryActionOperation value){return new BulkRecoveryAction(expectedRevision,value);}
}
