// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DocumentHistoryIdentity contract. */
public record DocumentHistoryIdentity(
    @JsonProperty("document_id") String documentId,
    @JsonProperty("catalog_source_id") String catalogSourceId,
    @JsonProperty("native_source_id") String nativeSourceId
) {

}
