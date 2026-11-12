// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceControlReceipt contract. */
public record SourceControlReceipt(
    @JsonProperty("kind") SourceControlReceiptKind kind,
    @JsonProperty("receipt") SourceControlOutput receipt
) implements SourceOperationReceipt {

}
