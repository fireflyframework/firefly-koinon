// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical ProvenanceArtifact contract. */
public record ProvenanceArtifact(
    @JsonProperty("id") String id,
    @JsonProperty("original_filename") String originalFilename,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("byte_size") Long byteSize,
    @JsonProperty("file_format") String fileFormat,
    @JsonProperty("compression") String compression,
    @JsonProperty("actor") String actor,
    @JsonProperty("admitted_at") Instant admittedAt
) {

}
