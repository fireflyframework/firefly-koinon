// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AttachmentLimits contract. */
public record AttachmentLimits(
    @JsonProperty("max_file_bytes") Long maxFileBytes,
    @JsonProperty("max_image_bytes") Long maxImageBytes,
    @JsonProperty("max_selected") Long maxSelected,
    @JsonProperty("max_thread_files") Long maxThreadFiles,
    @JsonProperty("max_thread_bytes") Long maxThreadBytes,
    @JsonProperty("max_model_text_chars") Long maxModelTextChars,
    @JsonProperty("max_model_binary_bytes") Long maxModelBinaryBytes,
    @JsonProperty("extraction_timeout_seconds") Long extractionTimeoutSeconds,
    @JsonProperty("ttl_seconds") Long ttlSeconds
) {

}
