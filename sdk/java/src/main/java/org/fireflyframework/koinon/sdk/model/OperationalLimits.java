// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OperationalLimits contract. */
public record OperationalLimits(
    @JsonProperty("worker_concurrency") Long workerConcurrency,
    @JsonProperty("max_queued_per_subject") Long maxQueuedPerSubject,
    @JsonProperty("job_lease_seconds") Long jobLeaseSeconds,
    @JsonProperty("max_index_workspaces") Long maxIndexWorkspaces
) {

}
