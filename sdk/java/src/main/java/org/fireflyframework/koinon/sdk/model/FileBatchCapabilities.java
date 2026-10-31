// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical FileBatchCapabilities contract. */
public record FileBatchCapabilities(
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("modes") List<AddKnowledgeMode> modes,
    @JsonProperty("processing_policy") FileBatchCapabilitiesProcessingPolicy processingPolicy,
    @JsonProperty("staging_backend") FileBatchCapabilitiesStagingBackend stagingBackend,
    @JsonProperty("staging_topology") FileBatchCapabilitiesStagingTopology stagingTopology,
    @JsonProperty("writer_fence") FileBatchCapabilitiesWriterFence writerFence,
    @JsonProperty("worker") FileBatchCapabilitiesWorker worker,
    @JsonProperty("automatic_unknown_replay") Boolean automaticUnknownReplay,
    @JsonProperty("max_files") Long maxFiles,
    @JsonProperty("max_file_bytes") Long maxFileBytes,
    @JsonProperty("max_batch_bytes") Long maxBatchBytes,
    @JsonProperty("max_active_batches_per_subject") Long maxActiveBatchesPerSubject
) {
    public FileBatchCapabilities {
        modes=modes==null?null:List.copyOf(modes);
    }

}
