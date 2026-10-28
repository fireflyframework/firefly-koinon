// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IndexJobView contract. */
public record IndexJobView(
    @JsonProperty("index") KnowledgeIndexView index,
    @JsonProperty("job_id") String jobId
) {

}
