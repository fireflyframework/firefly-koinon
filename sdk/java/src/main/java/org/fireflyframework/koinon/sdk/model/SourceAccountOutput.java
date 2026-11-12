// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceAccountOutput contract. */
public record SourceAccountOutput(
    @JsonProperty("provider") ReaderSourceSelectionProvider provider,
    @JsonProperty("subject") String subject,
    @JsonProperty("tenant_id") String tenantId
) {

}
