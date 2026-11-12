// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourcePolicyReceipt contract. */
public record SourcePolicyReceipt(
    @JsonProperty("kind") SourcePolicyReceiptKind kind,
    @JsonProperty("receipt") SourcePolicyOperationOutput receipt
) implements SourceOperationReceipt {

}
