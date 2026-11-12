// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceProviderCapability contract. */
public record SourceProviderCapability(
    @JsonProperty("provider") ReaderSourceSelectionProvider provider,
    @JsonProperty("display_name") String displayName,
    @JsonProperty("consent_available") Boolean consentAvailable,
    @JsonProperty("unavailable_reason") SourceProviderCapabilityUnavailableReason unavailableReason
) {

}
