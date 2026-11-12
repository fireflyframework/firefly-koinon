// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceConnectionOutput contract. */
public record SourceConnectionOutput(
    @JsonProperty("id") String id,
    @JsonProperty("provider") ReaderSourceSelectionProvider provider,
    @JsonProperty("status") SourceConnectionOutputStatus status,
    @JsonProperty("revision") Long revision,
    @JsonProperty("account") SourceAccountOutput account,
    @JsonProperty("display_name") String displayName,
    @JsonProperty("display_address") String displayAddress,
    @JsonProperty("display_address_verified") Boolean displayAddressVerified,
    @JsonProperty("synchronization_available") Boolean synchronizationAvailable
) {

}
