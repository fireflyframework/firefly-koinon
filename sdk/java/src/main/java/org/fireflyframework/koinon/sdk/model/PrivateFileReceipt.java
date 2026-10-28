// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical PrivateFileReceipt contract. */
public record PrivateFileReceipt(
    @JsonProperty("id") String id,
    @JsonProperty("filename") String filename,
    @JsonProperty("media_type") String mediaType,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("used_revision") Long usedRevision,
    @JsonProperty("availability") PrivateFileReceiptAvailability availability
) {

}
